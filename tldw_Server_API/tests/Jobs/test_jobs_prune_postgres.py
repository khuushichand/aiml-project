import os
from datetime import timedelta

import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup


pytestmark = pytest.mark.skipif(
    not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"
)

@pytest.fixture(scope="module", autouse=True)
def _setup(pg_schema_and_cleanup):
    # Alias the shared PG schema/cleanup fixture for autouse
    yield


def _backdate_pg(job_id: int, days: int = 2):
    conn = psycopg.connect(pg_dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET completed_at = NOW() - (%s || ' days')::interval WHERE id = %s",
                (int(days), int(job_id)),
            )
    finally:
        conn.close()


def test_jobs_prune_dry_run_and_filters_postgres(monkeypatch):
    # Set env so endpoint manager uses PG
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)

    ensure_jobs_tables_pg(pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    # Seed: 1 completed (old), 1 failed (old), 1 failed (recent)
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    jm.complete_job(int(j1["id"]))
    _backdate_pg(int(j1["id"]))

    j2 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    jm.fail_job(int(j2["id"]), error="x", retryable=False)
    _backdate_pg(int(j2["id"]))

    j3 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    jm.fail_job(int(j3["id"]), error="x", retryable=False)

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


def test_jobs_prune_filters_scope_postgres(monkeypatch):
    # Configure PG and single-user test mode
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)

    ensure_jobs_tables_pg(pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    # Seed a job in a different domain/queue
    jx = jm.create_job(domain="other", queue="low", job_type="export", payload={}, owner_user_id="1")
    jm.complete_job(int(jx["id"]))
    _backdate_pg(int(jx["id"]))

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
