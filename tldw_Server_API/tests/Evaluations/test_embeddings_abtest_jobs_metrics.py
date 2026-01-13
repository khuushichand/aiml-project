import os

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


def test_abtest_job_metrics_emitted(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "jobs.db"))

    reg = get_metrics_registry()
    created_key = reg.normalize_metric_name("jobs.created_total")
    completed_key = reg.normalize_metric_name("jobs.completed_total")
    reg.values[created_key].clear()
    reg.values[completed_key].clear()

    jm = JobManager()
    from tldw_Server_API.app.core.Jobs.manager import JobManager as _JM
    _JM.set_acquire_gate(False)

    jm.create_job(
        domain="evaluations",
        queue="default",
        job_type="embeddings_abtest_run",
        payload={"test_id": "t1"},
        owner_user_id="u1",
    )
    created = list(reg.values.get(created_key, []))
    assert any(v.labels.get("job_type") == "embeddings_abtest_run" for v in created)

    job = jm.acquire_next_job(
        domain="evaluations",
        queue="default",
        lease_seconds=10,
        worker_id="w1",
    )
    assert job is not None
    ok = jm.complete_job(
        int(job["id"]),
        result={"ok": True},
        worker_id="w1",
        lease_id=str(job.get("lease_id")),
        enforce=False,
    )
    assert ok is True
    completed = list(reg.values.get(completed_key, []))
    assert any(v.labels.get("job_type") == "embeddings_abtest_run" for v in completed)
