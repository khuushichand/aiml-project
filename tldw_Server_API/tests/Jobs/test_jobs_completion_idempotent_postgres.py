import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup


pytestmark = pytest.mark.skipif(
    not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"
)


@pytest.fixture(scope="module", autouse=True)
def _setup(pg_schema_and_cleanup):
    yield


def test_completion_idempotent_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
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
