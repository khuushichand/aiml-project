import json
import pytest

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


class StubRegistry:
    def __init__(self):
        self.increments = []
        self.observes = []
        self.gauges = []

    def register_metric(self, *_args, **_kwargs):
        return None

    def increment(self, name, value, labels):
        self.increments.append((name, value, dict(labels)))

    def observe(self, name, value, labels):
        self.observes.append((name, float(value), dict(labels)))

    def set_gauge(self, name, value, labels):
        self.gauges.append((name, float(value), dict(labels)))


@pytest.fixture()
def jobs_db(tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    yield db_path


def test_structured_error_fields_and_metrics_sqlite(monkeypatch, jobs_db):
    # Attach a stub metrics registry
    from tldw_Server_API.app.core.Jobs import metrics as jobs_metrics
    stub = StubRegistry()
    monkeypatch.setattr(jobs_metrics, "get_metrics_registry", lambda: stub, raising=False)
    # Permit metrics registration to proceed (optional)
    monkeypatch.setattr(jobs_metrics, "JOBS_METRICS_REGISTERED", False, raising=False)

    jm = JobManager(jobs_db)
    j = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="d", queue="default", lease_seconds=5, worker_id="w")
    assert acq is not None
    ok = jm.fail_job(int(acq["id"]), error="trace", retryable=False, error_code="E42", error_class="ValueError", error_stack={"where": "unit"})
    assert ok is True
    got = jm.get_job(int(acq["id"]))
    # Structured fields are present
    assert got.get("error_code") == "E42"
    assert got.get("error_class") == "ValueError"
    # error_stack stored as TEXT (JSON string) on SQLite
    stack_raw = got.get("error_stack")
    if isinstance(stack_raw, str) and stack_raw:
        stack = json.loads(stack_raw)
        assert stack.get("where") == "unit"

    # Metrics: verify failures_by_code_total incremented
    names = [name for (name, _v, _l) in stub.increments]
    assert "jobs.failures_by_code_total" in names
