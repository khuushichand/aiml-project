import os
from datetime import timedelta

import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
from tldw_Server_API.app.core.Jobs.manager import JobManager


def _backdate_pg(dsn: str, job_id: int, days: int = 2):
    conn = psycopg.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET completed_at = NOW() - (%s || ' days')::interval WHERE id = %s",
                (int(days), int(job_id)),
            )
    finally:
        conn.close()


def test_jobs_prune_dry_run_and_filters_postgres(monkeypatch, jobs_pg_dsn):


     # Set env so endpoint manager uses PG
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_URL", jobs_pg_dsn)
    monkeypatch.setenv("JOBS_ADMIN_COMPLETE_QUEUED_ALLOW_DOMAINS", "chatbooks")

    ensure_jobs_tables_pg(jobs_pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=jobs_pg_dsn)
    # Seed: 1 completed (old), 1 failed (old), 1 failed (recent)
    jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq1 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id="w1")
    assert acq1 is not None
    assert jm.complete_job(int(acq1["id"]), worker_id="w1", lease_id=str(acq1.get("lease_id")), enforce=True)
    _backdate_pg(jobs_pg_dsn, int(acq1["id"]))

    jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq2 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id="w2")
    assert acq2 is not None
    assert jm.fail_job(
        int(acq2["id"]),
        error="x",
        retryable=False,
        worker_id="w2",
        lease_id=str(acq2.get("lease_id")),
        enforce=True,
    )
    _backdate_pg(jobs_pg_dsn, int(acq2["id"]))

    jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq3 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id="w3")
    assert acq3 is not None
    assert jm.fail_job(
        int(acq3["id"]),
        error="x",
        retryable=False,
        worker_id="w3",
        lease_id=str(acq3.get("lease_id")),
        enforce=True,
    )

    from fastapi.testclient import TestClient
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app
    try:
        app.dependency_overrides.clear()
    except Exception:
        pass

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        body = {
            "statuses": ["completed", "failed"],
            "older_than_days": 1,
            "domain": "chatbooks",
            "queue": "default",
            "job_type": "export",
            "dry_run": True,
        }
        r = client.post("/api/v1/jobs/prune", json=body)
        assert r.status_code == 200, r.text
        assert r.json()["deleted"] == 2

        body["dry_run"] = False
        r2 = client.post("/api/v1/jobs/prune", json=body)
        assert r2.status_code == 200
        assert r2.json()["deleted"] == 2


def test_jobs_prune_filters_scope_postgres(monkeypatch, jobs_pg_dsn):


     # Configure PG and single-user test mode
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_URL", jobs_pg_dsn)
    monkeypatch.setenv("JOBS_ADMIN_COMPLETE_QUEUED_ALLOW_DOMAINS", "chatbooks")

    ensure_jobs_tables_pg(jobs_pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=jobs_pg_dsn)
    # Seed a job in a different domain/queue
    jm.create_job(domain="other", queue="low", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="other", queue="low", lease_seconds=10, worker_id="w4")
    assert acq is not None
    assert jm.complete_job(int(acq["id"]), worker_id="w4", lease_id=str(acq.get("lease_id")), enforce=True)
    _backdate_pg(jobs_pg_dsn, int(acq["id"]))

    from fastapi.testclient import TestClient
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app
    try:
        app.dependency_overrides.clear()
    except Exception:
        pass

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        body = {
            "statuses": ["completed"],
            "older_than_days": 1,
            "domain": "chatbooks",
            "queue": "default",
            "job_type": "export",
            "dry_run": True,
        }
        r = client.post("/api/v1/jobs/prune", json=body)
        assert r.status_code == 200
        assert r.json()["deleted"] == 0
