import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg


class StubRegistry:
    def __init__(self):
        self.increments = []

    def register_metric(self, *_args, **_kwargs):
        return None

    def increment(self, name, value, labels):
        self.increments.append((name, value, dict(labels)))

    def observe(self, *args, **kwargs):
        return None

    def set_gauge(self, *args, **kwargs):
        return None


pytestmark = pytest.mark.skipif(
    not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"
)


@pytest.fixture(scope="module", autouse=True)
def _setup(pg_schema_and_cleanup):
    yield


def test_structured_error_fields_and_metrics_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    ensure_jobs_tables_pg(pg_dsn)
    # Patch metrics registry
    from tldw_Server_API.app.core.Jobs import metrics as jobs_metrics
    stub = StubRegistry()
    monkeypatch.setattr(jobs_metrics, "get_metrics_registry", lambda: stub, raising=False)
    monkeypatch.setattr(jobs_metrics, "JOBS_METRICS_REGISTERED", False, raising=False)

    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    j = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="d", queue="default", lease_seconds=5, worker_id="w")
    assert acq is not None
    ok = jm.fail_job(int(acq["id"]), error="trace", retryable=False, error_code="E42", error_class="ValueError", error_stack={"where": "pg"})
    assert ok is True
    got = jm.get_job(int(acq["id"]))
    assert got.get("error_code") == "E42"
    assert got.get("error_class") == "ValueError"
    # PG stores JSONB; expect dict
    es = got.get("error_stack")
    if isinstance(es, dict):
        assert es.get("where") == "pg"

    # Check metric increment
    names = [name for (name, _v, _l) in stub.increments]
    assert "jobs.failures_by_code_total" in names
