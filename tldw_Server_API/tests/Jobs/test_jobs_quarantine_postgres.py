import time
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


def test_poison_quarantine_on_retries_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    monkeypatch.setenv("JOBS_QUARANTINE_THRESHOLD", "2")
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    j = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u")
    acq = jm.acquire_next_job(domain="test", queue="default", lease_seconds=5, worker_id="w")
    assert acq and acq.get("id") == j["id"]
    lease_id = str(acq.get("lease_id"))
    ok1 = jm.fail_job(int(j["id"]), error="boom", retryable=True, backoff_seconds=0, worker_id="w", lease_id=lease_id, error_code="E1")
    assert ok1 is True
    time.sleep(1.0)
    acq2 = jm.acquire_next_job(domain="test", queue="default", lease_seconds=5, worker_id="w")
    assert acq2 and acq2.get("id") == j["id"]
    ok2 = jm.fail_job(int(j["id"]), error="boom", retryable=True, backoff_seconds=0, worker_id="w", lease_id=str(acq2.get("lease_id")), error_code="E1")
    assert ok2 is True
    row = jm.get_job(int(j["id"]))
    assert row and row.get("status") == "quarantined"
