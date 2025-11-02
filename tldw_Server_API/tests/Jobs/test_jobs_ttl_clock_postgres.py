import os
import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup as _pg_schema_and_cleanup
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg


pytestmark = pytest.mark.skipif(
    not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"
)


def _set_pg_times(job_id: int, *, created_epoch: int | None = None, started_epoch: int | None = None):
    """Set created_at/updated_at and started/acquired times to specific epoch-based times."""
    conn = psycopg.connect(pg_dsn)
    try:
        with conn, conn.cursor() as cur:
            if created_epoch is not None:
                cur.execute(
                    "UPDATE jobs SET created_at = to_timestamp(%s), updated_at = to_timestamp(%s) WHERE id = %s",
                    (int(created_epoch), int(created_epoch), int(job_id)),
                )
            if started_epoch is not None:
                cur.execute(
                    "UPDATE jobs SET started_at = to_timestamp(%s), acquired_at = to_timestamp(%s) WHERE id = %s",
                    (int(started_epoch), int(started_epoch), int(job_id)),
                )
    finally:
        conn.close()


def test_jobs_ttl_with_clock_pg(monkeypatch):
    # Deterministic clock value
    test_now = 1700000000  # arbitrary fixed epoch
    monkeypatch.setenv("JOBS_TEST_NOW_EPOCH", str(test_now))
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)

    ensure_jobs_tables_pg(pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)

    # Seed one queued job aged 2h at test_now, one processing with runtime 3h
    j1 = jm.create_job(domain="clocktest", queue="default", job_type="export", payload={}, owner_user_id="u1")
    _set_pg_times(int(j1["id"]), created_epoch=(test_now - 2 * 3600))

    got = jm.acquire_next_job(domain="clocktest", queue="default", lease_seconds=30, worker_id="w1")
    assert got is not None
    _set_pg_times(int(got["id"]), started_epoch=(test_now - 3 * 3600))

    # TTL with age/runtime 1h should cancel both deterministically under the fixed clock
    affected = jm.apply_ttl_policies(age_seconds=3600, runtime_seconds=3600, action="cancel", domain="clocktest", queue="default", job_type="export")
    assert affected >= 2

    j1r = jm.get_job(int(j1["id"]))
    j2r = jm.get_job(int(got["id"]))
    assert j1r and j1r["status"] == "cancelled"
    assert j2r and j2r["status"] == "cancelled"
