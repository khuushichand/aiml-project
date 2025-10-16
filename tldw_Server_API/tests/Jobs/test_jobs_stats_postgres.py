import os
from typing import Dict, Tuple

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
    # Ensure schema exists and table is truncated before this module runs
    yield


def _map_by_key(rows):
    out: Dict[Tuple[str, str, str], Dict] = {}
    for r in rows:
        out[(r["domain"], r["queue"], r["job_type"])] = r
    return out


def test_jobs_stats_shape_and_filters_postgres(monkeypatch):
    # Configure env for single-user and Postgres backend
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)

    ensure_jobs_tables_pg(pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)

    # Seed chatbooks/default/export: 2 queued -> acquire 1 (processing)
    jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    got = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w1")
    assert got is not None

    # Seed chatbooks/high/export: 1 queued
    jm.create_job(domain="chatbooks", queue="high", job_type="export", payload={}, owner_user_id="1")

    # Seed other/default/import: 1 queued -> acquire 1 (processing)
    jm.create_job(domain="other", queue="default", job_type="import", payload={}, owner_user_id="2")
    got2 = jm.acquire_next_job(domain="other", queue="default", lease_seconds=30, worker_id="w2")
    assert got2 is not None

    # Completed job should not count
    jc = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    jm.complete_job(int(jc["id"]))

    from fastapi.testclient import TestClient
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        # No filters
        r = client.get("/api/v1/jobs/stats")
        assert r.status_code == 200, r.text
        m = _map_by_key(r.json())
        g = m[("chatbooks", "default", "export")]
        assert g["queued"] == 1  # 2 created - 1 acquired
        assert g["processing"] == 1
        g2 = m[("chatbooks", "high", "export")]
        assert g2["queued"] == 1
        assert g2["processing"] == 0
        g3 = m[("other", "default", "import")]
        assert g3["queued"] == 0
        assert g3["processing"] == 1

        # Filters
        r_dom = client.get("/api/v1/jobs/stats", params={"domain": "chatbooks"})
        assert r_dom.status_code == 200
        assert {row["domain"] for row in r_dom.json()} == {"chatbooks"}

        r_q = client.get("/api/v1/jobs/stats", params={"queue": "high"})
        assert r_q.status_code == 200
        items = r_q.json()
        assert len(items) == 1
        assert items[0]["queue"] == "high"

        r_t = client.get("/api/v1/jobs/stats", params={"job_type": "export"})
        assert r_t.status_code == 200
        assert {row["job_type"] for row in r_t.json()} == {"export"}

        r_all = client.get(
            "/api/v1/jobs/stats",
            params={"domain": "chatbooks", "queue": "default", "job_type": "export"},
        )
        assert r_all.status_code == 200
        rows = r_all.json()
        assert len(rows) == 1
        only = rows[0]
        assert only["domain"] == "chatbooks"
        assert only["queue"] == "default"
        assert only["job_type"] == "export"
