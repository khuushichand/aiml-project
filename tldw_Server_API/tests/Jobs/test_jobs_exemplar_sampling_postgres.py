import os
import pytest

pytestmark = pytest.mark.pg_jobs


def _env(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("JOBS_METRICS_EXEMPLARS", "true")
    monkeypatch.setenv("JOBS_METRICS_EXEMPLAR_SAMPLING", "1.0")


def test_exemplar_labels_propagate_postgres(monkeypatch):
    if not os.getenv("JOBS_DB_URL", "").startswith("postgres"):
        pytest.skip("JOBS_DB_URL not set to Postgres")
    _env(monkeypatch)
    # Force random sampling to always true
    import random as _rnd
    monkeypatch.setattr(_rnd, "random", lambda: 0.0)

    from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
    ensure_jobs_tables_pg(os.getenv("JOBS_DB_URL"))
    from tldw_Server_API.app.core.Jobs.manager import JobManager
    from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry

    jm = JobManager(backend="postgres", db_url=os.getenv("JOBS_DB_URL"))
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="u1", request_id="req-1", trace_id="trace-1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=1, worker_id="w")
    assert acq
    jm.complete_job(int(acq["id"]))

    reg = get_metrics_registry()
    ql = list(reg.values.get("jobs.queue_latency_seconds", []))
    dur = list(reg.values.get("jobs.duration_seconds", []))
    assert ql and dur
    assert ("trace_id" in ql[-1].labels) or ("request_id" in ql[-1].labels)
    assert ("trace_id" in dur[-1].labels) or ("request_id" in dur[-1].labels)
