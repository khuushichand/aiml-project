import os
import asyncio

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
from tldw_Server_API.app.services.jobs_metrics_service import run_jobs_metrics_gauges


def _env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))
    monkeypatch.setenv("JOBS_SLO_ENABLE", "true")
    monkeypatch.setenv("JOBS_SLO_WINDOW_HOURS", "24")
    monkeypatch.setenv("JOBS_SLO_MAX_GROUPS", "10")
    monkeypatch.setenv("JOBS_METRICS_INTERVAL_SEC", "0.01")


async def _run_once():
    # Run the gauges loop briefly, then stop
    stop = asyncio.Event()
    async def stopper():
        await asyncio.sleep(0.05)
        stop.set()
    task = asyncio.create_task(run_jobs_metrics_gauges(stop_event=stop))
    await stopper()
    await task


def test_slo_gauges_sqlite(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    jm = JobManager()

    # Create and complete a few jobs for two owners
    for owner in ("o1", "o2"):
        for i in range(3):
            j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id=owner, priority=1)
            acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=1, worker_id="w")
            assert acq
            jm.complete_job(int(acq["id"]))

    # Run one iteration of the metrics loop
    asyncio.run(_run_once())

    reg = get_metrics_registry()
    # Verify percentile gauges were produced (at least one sample)
    names = [
        "jobs.queue_latency_p50_seconds",
        "jobs.queue_latency_p90_seconds",
        "jobs.queue_latency_p99_seconds",
        "jobs.duration_p50_seconds",
        "jobs.duration_p90_seconds",
        "jobs.duration_p99_seconds",
    ]
    seen_any = False
    for n in names:
        vals = list(reg.values.get(n, []))
        if vals:
            seen_any = True
            assert "owner_user_id" in vals[-1].labels
    assert seen_any, "Expected SLO percentile gauges to be set"
