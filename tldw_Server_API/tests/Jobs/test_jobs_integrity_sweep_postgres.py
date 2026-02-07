import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.fixture(autouse=True)
def _setup(jobs_pg_dsn):
    return


def test_integrity_sweep_clears_non_processing_lease_postgres(monkeypatch, jobs_pg_dsn):


    jm = JobManager(None, backend="postgres", db_url=jobs_pg_dsn)
    j_queued = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u")
    j_processing = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u")
    # Manually inject two invalid states:
    # 1) queued job carrying lease metadata
    # 2) processing job with expired lease
    import psycopg
    with psycopg.connect(jobs_pg_dsn) as conn:
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status='queued', lease_id=%s, worker_id=%s, leased_until=NOW() WHERE id = %s",
                ("L", "W", int(j_queued["id"])),
            )
            cur.execute(
                "UPDATE jobs SET status='processing', leased_until=NOW() - interval '10 minutes' WHERE id = %s",
                (int(j_processing["id"]),),
            )

    stats = jm.integrity_sweep(fix=True)
    assert stats["non_processing_with_lease"] == 1
    assert stats["processing_expired"] == 1
    assert stats["fixed"] == 2

    queued_after = jm.get_job(int(j_queued["id"]))
    processing_after = jm.get_job(int(j_processing["id"]))
    assert queued_after and not queued_after.get("lease_id") and not queued_after.get("worker_id")
    assert processing_after and processing_after.get("status") == "queued"
    assert not processing_after.get("lease_id") and not processing_after.get("worker_id")
