import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.fixture(autouse=True)
def _setup(jobs_pg_dsn):
    return


def test_completion_idempotent_postgres(monkeypatch, jobs_pg_dsn):


    jm = JobManager(None, backend="postgres", db_url=jobs_pg_dsn)
    j = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u")
    acq = jm.acquire_next_job(domain="test", queue="default", lease_seconds=10, worker_id="w1")
    assert acq and acq.get("id") == j["id"]
    token = str(acq.get("lease_id"))
    ok1 = jm.complete_job(int(j["id"]), worker_id="w1", lease_id=token, completion_token=token)
    assert ok1 is True
    ok2 = jm.complete_job(int(j["id"]), worker_id="w1", lease_id=token, completion_token=token)
    assert ok2 is True
    ok3 = jm.complete_job(int(j["id"]), worker_id="w1", lease_id=token, completion_token="other-token")
    assert ok3 is False
