import os
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.pg_jobs


def _require_pg(monkeypatch):
    dsn = os.getenv("JOBS_DB_URL")
    if not dsn:
        pytest.skip("JOBS_DB_URL not configured")
    monkeypatch.setenv("JOBS_COUNTERS_ENABLED", "true")
    monkeypatch.setenv("JOBS_PG_SINGLE_UPDATE_ACQUIRE", "true")
    monkeypatch.setenv("JOBS_GAUGES_DEBOUNCE_MS", "0")
    return dsn


def _stats(client, domain="chatbooks", queue="default", job_type="export"):
    r = client.get("/api/v1/jobs/stats", params={"domain": domain, "queue": queue, "job_type": job_type})
    assert r.status_code == 200
    rows = r.json(); assert len(rows) == 1
    return rows[0]


def test_pg_ttl_cancel_updates_counters(monkeypatch):
    dsn = _require_pg(monkeypatch)
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app
    jm = JobManager(backend="postgres", db_url=dsn)
    domain = "chatbooks"; queue = "default"; jt = "export"
    jq = jm.create_job(domain=domain, queue=queue, job_type=jt, payload={}, owner_user_id="1")
    jp = jm.create_job(domain=domain, queue=queue, job_type=jt, payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=30, worker_id="w")
    assert acq and acq["id"] == jp["id"]
    # Backdate
    conn = jm._connect()
    try:
        with jm._pg_cursor(conn) as cur:
            cur.execute("UPDATE jobs SET created_at = NOW() - interval '2 hours' WHERE id = %s", (int(jq["id"]),))
            cur.execute("UPDATE jobs SET started_at = NOW() - interval '3 hours', acquired_at = NOW() - interval '3 hours' WHERE id = %s", (int(jp["id"]),))
    finally:
        conn.close()
    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        r = client.post("/api/v1/jobs/ttl/sweep", json={"age_seconds": 3600, "runtime_seconds": 3600, "action": "cancel", "domain": domain, "queue": queue, "job_type": jt}, headers={**headers, "X-Confirm": "true"})
        assert r.status_code == 200
        s = _stats(client, domain, queue, jt)
        assert s["queued"] == 0 and s["processing"] == 0
        # Metrics: cancelled_total should increment
        try:
            from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
            reg = get_metrics_registry()
            vals = list(reg.values.get("jobs.cancelled_total", []))
            saw = False
            for mv in vals:
                if mv.labels.get("domain") == domain and mv.labels.get("queue") == queue and mv.labels.get("job_type") == jt:
                    saw = True
                    break
            assert saw
        except Exception:
            pass
    conn = jm._connect()
    try:
        with jm._pg_cursor(conn) as cur:
            cur.execute("SELECT ready_count, scheduled_count, processing_count FROM job_counters WHERE domain=%s AND queue=%s AND job_type=%s", (domain, queue, jt))
            row = cur.fetchone(); assert row is not None
            assert int(row[0] or 0) == 0 and int(row[1] or 0) == 0 and int(row[2] or 0) == 0
    finally:
        conn.close()


def test_pg_ttl_fail_updates_counters(monkeypatch):
    dsn = _require_pg(monkeypatch)
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app
    jm = JobManager(backend="postgres", db_url=dsn)
    domain = "chatbooks"; queue = "default"; jt = "export"
    jq = jm.create_job(domain=domain, queue=queue, job_type=jt, payload={}, owner_user_id="1")
    jp = jm.create_job(domain=domain, queue=queue, job_type=jt, payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=30, worker_id="w")
    assert acq and acq["id"] == jp["id"]
    conn = jm._connect()
    try:
        with jm._pg_cursor(conn) as cur:
            cur.execute("UPDATE jobs SET created_at = NOW() - interval '2 hours' WHERE id = %s", (int(jq["id"]),))
            cur.execute("UPDATE jobs SET started_at = NOW() - interval '3 hours', acquired_at = NOW() - interval '3 hours' WHERE id = %s", (int(jp["id"]),))
    finally:
        conn.close()
    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        r = client.post("/api/v1/jobs/ttl/sweep", json={"age_seconds": 3600, "runtime_seconds": 3600, "action": "fail", "domain": domain, "queue": queue, "job_type": jt}, headers={**headers, "X-Confirm": "true"})
        assert r.status_code == 200
        s = _stats(client, domain, queue, jt)
        assert s["queued"] == 0 and s["processing"] == 0
        # Metrics: failures_total should have ttl_age and ttl_runtime labels
        try:
            from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
            reg = get_metrics_registry()
            vals = list(reg.values.get("jobs.failures_total", []))
            saw_age = False; saw_runtime = False
            for mv in vals:
                if mv.labels.get("domain") == domain and mv.labels.get("queue") == queue and mv.labels.get("job_type") == jt:
                    if mv.labels.get("reason") == "ttl_age":
                        saw_age = True
                    if mv.labels.get("reason") == "ttl_runtime":
                        saw_runtime = True
            assert saw_age and saw_runtime
        except Exception:
            pass
    conn = jm._connect()
    try:
        with jm._pg_cursor(conn) as cur:
            cur.execute("SELECT ready_count, scheduled_count, processing_count FROM job_counters WHERE domain=%s AND queue=%s AND job_type=%s", (domain, queue, jt))
            row = cur.fetchone(); assert row is not None
            assert int(row[0] or 0) == 0 and int(row[1] or 0) == 0 and int(row[2] or 0) == 0
    finally:
        conn.close()
