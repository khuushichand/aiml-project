import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg


pytestmark = pytest.mark.skipif(
    not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"
)


@pytest.fixture(scope="module", autouse=True)
def _setup(pg_schema_and_cleanup):
    yield


def test_idempotency_scoped_to_domain_queue_type_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    ensure_jobs_tables_pg(pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)

    key = "idem-key-123"
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1", idempotency_key=key)
    j2 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1", idempotency_key=key)
    assert int(j1["id"]) == int(j2["id"])  # same group -> idempotent

    j3 = jm.create_job(domain="chatbooks", queue="high", job_type="export", payload={}, owner_user_id="1", idempotency_key=key)
    assert int(j3["id"]) != int(j1["id"])  # different queue -> distinct

    j4 = jm.create_job(domain="chatbooks", queue="default", job_type="import", payload={}, owner_user_id="1", idempotency_key=key)
    assert int(j4["id"]) != int(j1["id"])  # different type -> distinct

    j5 = jm.create_job(domain="other", queue="default", job_type="export", payload={}, owner_user_id="2", idempotency_key=key)
    assert int(j5["id"]) != int(j1["id"])  # different domain -> distinct
