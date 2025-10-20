import asyncio
import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_manager import JobManager, JobType


class _StubMetricsManager:
    def __init__(self):
        self.set_gauge_calls = []  # tuples: (name, value, labels)
        self.observe_calls = []    # tuples: (name, value, labels)

    def set_gauge(self, name: str, value: float, labels=None):
        self.set_gauge_calls.append((name, value, labels or {}))

    def observe(self, name: str, value: float, labels=None):
        self.observe_calls.append((name, value, labels or {}))


class _StubMetrics:
    def __init__(self):
        self.metrics_manager = _StubMetricsManager()
        self.queued_updates = []  # tuples: (job_type, queued_count)

    def update_job_queue_size(self, job_type: str, queued_count: int):
        self.queued_updates.append((job_type, queued_count))


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_metrics_update_on_job_lifecycle(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db

    jm = JobManager(db)
    stub = _StubMetrics()
    # Inject stub metrics collector for JobManager-level metrics
    jm._metrics = stub  # type: ignore[attr-defined]
    # Also patch global Prompt Studio metrics used by DB-layer observations (e.g., queue latency)
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import monitoring as mon
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(mon, "prompt_studio_metrics", stub, raising=True)

    # 1) Create job => queued gauge should update for this type
    job = jm.create_job(JobType.OPTIMIZATION, entity_id=0, payload={})
    assert stub.queued_updates, f"no queued gauge updates captured (backend={label})"
    types_recorded = {jt for jt, _ in stub.queued_updates}
    assert "optimization" in types_recorded, f"queued gauge missing for 'optimization' (backend={label})"

    # 2) Acquire job => processing gauge and queue latency should update
    picked = jm.get_next_job()
    assert picked is not None and picked.get("id") == job.get("id")

    proc_calls = [c for c in stub.metrics_manager.set_gauge_calls if c[0] == "jobs.processing"]
    assert proc_calls, f"no processing gauge set calls captured (backend={label})"
    assert any((c[2] or {}).get("job_type") == "optimization" for c in proc_calls), "processing gauge labels missing job_type=optimization"

    # Queue latency observation should be recorded with non-negative value
    qlat_calls = [c for c in stub.metrics_manager.observe_calls if c[0] == "jobs.queue_latency_seconds"]
    assert qlat_calls, f"no queue latency observation recorded (backend={label})"
    assert all(c[1] >= 0 for c in qlat_calls), "queue latency must be non-negative"

    # 3) Process job => duration histogram observed and gauges refreshed
    async def handler(payload, entity_id):
        await asyncio.sleep(0.01)
        return {"ok": True}

    jm.register_handler(JobType.OPTIMIZATION, handler)
    await jm.process_job(picked)

    duration_calls = [c for c in stub.metrics_manager.observe_calls if c[0] == "jobs.duration_seconds"]
    assert duration_calls, f"no job duration observation recorded (backend={label})"
    assert any((c[2] or {}).get("job_type") == "optimization" for c in duration_calls), "duration histogram labels missing job_type=optimization"
