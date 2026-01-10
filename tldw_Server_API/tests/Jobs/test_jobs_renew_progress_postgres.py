import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.fixture(autouse=True)
def _setup(jobs_pg_dsn):
    return


def test_renew_progress_persists_without_enforcement_postgres(monkeypatch, jobs_pg_dsn):


    jm = JobManager(None, backend="postgres", db_url=jobs_pg_dsn)

    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w1")
    assert acq and str(acq.get("status")) == "processing"

    ok = jm.renew_job_lease(int(acq["id"]), seconds=15, progress_percent=33.3, progress_message="third")
    assert ok is True

    got = jm.get_job(int(acq["id"]))
    assert got.get("status") == "processing"
    assert float(got.get("progress_percent")) == pytest.approx(33.3)
    assert got.get("progress_message") == "third"


def test_renew_progress_persists_with_enforcement_postgres(monkeypatch, jobs_pg_dsn):


    monkeypatch.setenv("JOBS_ENFORCE_LEASE_ACK", "true")
    jm = JobManager(None, backend="postgres", db_url=jobs_pg_dsn)

    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w1")
    assert acq and str(acq.get("status")) == "processing"

    ok = jm.renew_job_lease(
        int(acq["id"]),
        seconds=20,
        worker_id="w1",
        lease_id=str(acq.get("lease_id")),
        progress_percent=90.0,
        progress_message="almost",
    )
    assert ok is True

    got = jm.get_job(int(acq["id"]))
    assert float(got.get("progress_percent")) == pytest.approx(90.0)
    assert got.get("progress_message") == "almost"
