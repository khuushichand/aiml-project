import os
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


def _env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))
    monkeypatch.setenv("JOBS_METRICS_EXEMPLARS", "true")
    monkeypatch.setenv("JOBS_METRICS_EXEMPLAR_SAMPLING", "1.0")


def test_exemplar_labels_propagate_sqlite(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    # Force random path to always sample
    import random as _rnd
    monkeypatch.setattr(_rnd, "random", lambda: 0.0)

    jm = JobManager()
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="u1", request_id="req-1", trace_id="trace-1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=1, worker_id="w")
    assert acq
    jm.complete_job(int(acq["id"]))

    reg = get_metrics_registry()
    ql = list(reg.values.get("jobs.queue_latency_seconds", []))
    dur = list(reg.values.get("jobs.duration_seconds", []))
    # At least one observation and labels should include correlation IDs
    assert ql, "Expected queue latency observations"
    assert dur, "Expected duration observations"
    assert ("trace_id" in ql[-1].labels) or ("request_id" in ql[-1].labels)
    assert ("trace_id" in dur[-1].labels) or ("request_id" in dur[-1].labels)
