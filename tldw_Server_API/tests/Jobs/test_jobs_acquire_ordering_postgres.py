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


def test_acquire_ordering_priority_desc_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    j1 = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u", priority=1)
    j2 = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u", priority=5)
    j3 = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u", priority=10)
    acq1 = jm.acquire_next_job(domain="test", queue="default", lease_seconds=5, worker_id="w")
    assert acq1 and acq1.get("id") == j3["id"]  # priority 10 first
    # complete to release
    jm.complete_job(int(acq1["id"]), worker_id="w", lease_id=str(acq1.get("lease_id")), completion_token=str(acq1.get("lease_id")))
    acq2 = jm.acquire_next_job(domain="test", queue="default", lease_seconds=5, worker_id="w")
    assert acq2 and acq2.get("id") == j2["id"]
    jm.complete_job(int(acq2["id"]), worker_id="w", lease_id=str(acq2.get("lease_id")), completion_token=str(acq2.get("lease_id")))
    acq3 = jm.acquire_next_job(domain="test", queue="default", lease_seconds=5, worker_id="w")
    assert acq3 and acq3.get("id") == j1["id"]
