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


def test_jobs_stats_includes_scheduled_postgres(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)

    ensure_jobs_tables_pg(pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)

    future = datetime.utcnow() + timedelta(hours=1)
    jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="1",
        available_at=future,
    )

    from fastapi.testclient import TestClient
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        r = client.get(
            "/api/v1/jobs/stats",
            params={"domain": "chatbooks", "queue": "default", "job_type": "export"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body) == 1
        row = body[0]
        assert row["queued"] == 0  # ready queued
        assert row["scheduled"] >= 1
        assert row["processing"] == 0
