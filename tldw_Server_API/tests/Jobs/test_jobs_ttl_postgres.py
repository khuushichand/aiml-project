import os
from datetime import datetime, timedelta

import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
from tldw_Server_API.app.core.Jobs.manager import JobManager


pg_dsn = os.getenv("JOBS_DB_URL") or os.getenv("POSTGRES_TEST_DSN")

pytestmark = pytest.mark.skipif(
    not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"
)

@pytest.fixture(scope="module", autouse=True)
def _pg_schema_and_cleanup():
    os.environ.setdefault("TEST_MODE", "true")
    os.environ.setdefault("AUTH_MODE", "single_user")
    try:
        base = pg_dsn.rsplit("/", 1)[0] + "/postgres"
        db_name = pg_dsn.rsplit("/", 1)[1].split("?")[0]
        with psycopg.connect(base, autocommit=True) as _conn:
            with _conn.cursor() as _cur:
                _cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db_name,))
                if _cur.fetchone() is None:
                    _cur.execute(f"CREATE DATABASE {db_name}")
    except Exception:
        pass
    ensure_jobs_tables_pg(pg_dsn)
    with psycopg.connect(pg_dsn) as conn:
        with conn, conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE jobs RESTART IDENTITY")
    yield


def _backdate_pg_fields(job_id: int, *, created_delta_s: int = 0, runtime_delta_s: int = 0):
    conn = psycopg.connect(pg_dsn)
    try:
        with conn, conn.cursor() as cur:
            if created_delta_s:
                cur.execute(
                    "UPDATE jobs SET created_at = NOW() - (%s || ' seconds')::interval, updated_at = NOW() - (%s || ' seconds')::interval WHERE id = %s",
                    (int(created_delta_s), int(created_delta_s), int(job_id)),
                )
            if runtime_delta_s:
                cur.execute(
                    "UPDATE jobs SET started_at = NOW() - (%s || ' seconds')::interval, acquired_at = NOW() - (%s || ' seconds')::interval WHERE id = %s",
                    (int(runtime_delta_s), int(runtime_delta_s), int(job_id)),
                )
    finally:
        conn.close()


def test_jobs_ttl_sweep_pg(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)

    ensure_jobs_tables_pg(pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)

    # Seed queued and processing, then backdate
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    _backdate_pg_fields(int(j1["id"]), created_delta_s=7200)

    got = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=60, worker_id="w1")
    assert got is not None
    _backdate_pg_fields(int(got["id"]), runtime_delta_s=10800)

    # Add a second queued job old enough to be hit by age TTL
    j_old = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    _backdate_pg_fields(int(j_old["id"]), created_delta_s=7200)

    from fastapi.testclient import TestClient
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        r = client.post(
            "/api/v1/jobs/ttl/sweep",
            json={
                "age_seconds": 3600,
                "runtime_seconds": 3600,
                "action": "cancel",
                "domain": "chatbooks",
                "queue": "default",
                "job_type": "export",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["affected"] >= 2

    j1r = jm.get_job(int(j1["id"]))
    j2r = jm.get_job(int(got["id"]))
    assert j1r and j1r["status"] == "cancelled"
    assert j2r and j2r["status"] == "cancelled"


def test_jobs_ttl_sweep_fail_pg(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)

    ensure_jobs_tables_pg(pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)

    # Seed queued and processing, then backdate
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    _backdate_pg_fields(int(j1["id"]), created_delta_s=7200)

    got = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=60, worker_id="w1")
    assert got is not None
    _backdate_pg_fields(int(got["id"]), runtime_delta_s=10800)

    # Add a second queued job old enough to be hit by age TTL
    j_old = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    _backdate_pg_fields(int(j_old["id"]), created_delta_s=7200)

    from fastapi.testclient import TestClient
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        r = client.post(
            "/api/v1/jobs/ttl/sweep",
            json={
                "age_seconds": 3600,
                "runtime_seconds": 3600,
                "action": "fail",
                "domain": "chatbooks",
                "queue": "default",
                "job_type": "export",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["affected"] >= 2

    j1r = jm.get_job(int(j1["id"]))
    j2r = jm.get_job(int(got["id"]))
    assert j1r and j1r["status"] == "failed"
    assert j2r and j2r["status"] == "failed"
