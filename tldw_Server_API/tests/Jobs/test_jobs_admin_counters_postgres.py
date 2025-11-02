import os
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.pg_jobs


def _headers(app):
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    return {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}


def _stats(client, domain="chatbooks", queue="default", job_type="export"):
    r = client.get("/api/v1/jobs/stats", params={"domain": domain, "queue": queue, "job_type": job_type})
    assert r.status_code == 200
    rows = r.json(); assert len(rows) == 1
    return rows[0]


def _require_pg(monkeypatch):
    dsn = os.getenv("JOBS_DB_URL")
    if not dsn:
        pytest.skip("JOBS_DB_URL not configured")
    monkeypatch.setenv("JOBS_COUNTERS_ENABLED", "true")
    monkeypatch.setenv("JOBS_PG_SINGLE_UPDATE_ACQUIRE", "true")
    monkeypatch.setenv("JOBS_GAUGES_DEBOUNCE_MS", "0")
    return dsn


def test_pg_batch_cancel_updates_counters(monkeypatch):
    dsn = _require_pg(monkeypatch)
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app
    jm = JobManager(backend="postgres", db_url=dsn)
    domain = "chatbooks"; queue = "default"; jt = "export"
    jm.create_job(domain=domain, queue=queue, job_type=jt, payload={}, owner_user_id="1")
    jm.create_job(domain=domain, queue=queue, job_type=jt, payload={}, owner_user_id="1", available_at=datetime.now(tz=timezone.utc) + timedelta(seconds=60))
    t = jm.create_job(domain=domain, queue=queue, job_type=jt, payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=30, worker_id="w")
    assert acq and acq["id"] == t["id"]
    headers = _headers(app)
    with TestClient(app, headers=headers) as client:
        s0 = _stats(client, domain, queue, jt)
        assert s0["processing"] == 1
        r = client.post("/api/v1/jobs/batch/cancel", json={"domain": domain, "queue": queue, "job_type": jt, "dry_run": False}, headers={**headers, "X-Confirm": "true"})
        assert r.status_code == 200
        s1 = _stats(client, domain, queue, jt)
        assert s1["queued"] == 0 and s1["processing"] == 0
    conn = jm._connect()
    try:
        with jm._pg_cursor(conn) as cur:
            cur.execute("SELECT ready_count, scheduled_count, processing_count FROM job_counters WHERE domain=%s AND queue=%s AND job_type=%s", (domain, queue, jt))
            row = cur.fetchone(); assert row is not None
            assert int(row[0] or 0) == 0 and int(row[1] or 0) == 0 and int(row[2] or 0) == 0
    finally:
        conn.close()


def test_pg_batch_reschedule_moves_ready_to_scheduled(monkeypatch):
    dsn = _require_pg(monkeypatch)
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app
    jm = JobManager(backend="postgres", db_url=dsn)
    domain = "chatbooks"; queue = "default"; jt = "export"
    for _ in range(4):
        jm.create_job(domain=domain, queue=queue, job_type=jt, payload={}, owner_user_id="1")
    headers = _headers(app)
    with TestClient(app, headers=headers) as client:
        r = client.post("/api/v1/jobs/batch/reschedule", json={"domain": domain, "queue": queue, "job_type": jt, "delay_seconds": 30, "dry_run": False}, headers={**headers, "X-Confirm": "true"})
        assert r.status_code == 200
        s = _stats(client, domain, queue, jt)
        assert s["queued"] == 0
    conn = jm._connect()
    try:
        with jm._pg_cursor(conn) as cur:
            cur.execute("SELECT ready_count, scheduled_count FROM job_counters WHERE domain=%s AND queue=%s AND job_type=%s", (domain, queue, jt))
            row = cur.fetchone(); assert row is not None
            assert int(row[0] or 0) == 0 and int(row[1] or 0) >= 4
    finally:
        conn.close()


def test_pg_batch_requeue_quarantined_adjusts_counters(monkeypatch):
    dsn = _require_pg(monkeypatch)
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app
    jm = JobManager(backend="postgres", db_url=dsn)
    domain = "chatbooks"; queue = "default"; jt = "export"
    j = jm.create_job(domain=domain, queue=queue, job_type=jt, payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=30, worker_id="w")
    token1 = str(acq.get("lease_id"))
    jm.fail_job(int(j["id"]), error="boom", retryable=True, worker_id="w", lease_id=str(acq.get("lease_id")), completion_token=token1)
    acq2 = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=30, worker_id="w")
    token2 = str(acq2.get("lease_id"))
    jm.fail_job(int(j["id"]), error="boom", retryable=True, worker_id="w", lease_id=str(acq2.get("lease_id")), completion_token=token2)
    headers = _headers(app)
    with TestClient(app, headers=headers) as client:
        r = client.post("/api/v1/jobs/batch/requeue-quarantined", json={"domain": domain, "queue": queue, "job_type": jt, "dry_run": False}, headers={**headers, "X-Confirm": "true"})
        assert r.status_code == 200
        s = _stats(client, domain, queue, jt)
        assert s["quarantined"] == 0 and s["queued"] >= 1
    conn = jm._connect()
    try:
        with jm._pg_cursor(conn) as cur:
            cur.execute("SELECT ready_count, quarantined_count FROM job_counters WHERE domain=%s AND queue=%s AND job_type=%s", (domain, queue, jt))
            row = cur.fetchone(); assert row is not None
            assert int(row[0] or 0) >= 1 and int(row[1] or 0) == 0
    finally:
        conn.close()
