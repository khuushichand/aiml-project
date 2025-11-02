import os
from datetime import datetime, timedelta

import pytest

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup


pytestmark = [
    pytest.mark.pg_jobs,
    pytest.mark.skipif(not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping PG tests"),
]


def test_pg_single_update_acquire_toggle(monkeypatch, pg_schema_and_cleanup):
    # Enable single-update SKIP LOCKED acquire path
    monkeypatch.setenv("JOBS_PG_SINGLE_UPDATE_ACQUIRE", "true")

    jm = JobManager(None, backend="postgres", db_url=pg_dsn)

    # Seed two jobs with different priorities and availability
    j1 = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"k": 1},
        owner_user_id="1",
        priority=3,
    )
    j2 = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"k": 2},
        owner_user_id="1",
        priority=7,
    )

    # Acquire should return the lower priority value (3) first
    got = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id="W1")
    assert got is not None
    assert int(got["id"]) == int(j1["id"])  # priority ASC ordering

    # Second acquire while lease active should not return the same job
    got2 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id="W2")
    assert got2 is not None
    assert int(got2["id"]) == int(j2["id"])  # the other job

    # Ensure both are in processing now
    g1 = jm.get_job(int(j1["id"]))
    g2 = jm.get_job(int(j2["id"]))
    assert g1["status"] == "processing"
    assert g2["status"] == "processing"
