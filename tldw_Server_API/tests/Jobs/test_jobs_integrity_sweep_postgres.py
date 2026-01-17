import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.fixture(autouse=True)
def _setup(jobs_pg_dsn):
    return


def test_integrity_sweep_clears_non_processing_lease_postgres(monkeypatch, jobs_pg_dsn):


    jm = JobManager(None, backend="postgres", db_url=jobs_pg_dsn)
    j = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u")
    # Manually inject bad lease fields on a queued job
    import psycopg
    with psycopg.connect(jobs_pg_dsn) as conn:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE jobs SET lease_id=%s, worker_id=%s, leased_until=NOW() WHERE id = %s", ("L", "W", int(j["id"])) )
    stats = jm.integrity_sweep(fix=True)
    assert stats["fixed"] >= 1
    j2 = jm.get_job(int(j["id"]))
    assert j2 and not j2.get("lease_id") and not j2.get("worker_id")
