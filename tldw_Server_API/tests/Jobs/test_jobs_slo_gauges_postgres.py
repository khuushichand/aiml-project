import os
import asyncio
import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
from tldw_Server_API.app.services.jobs_metrics_service import run_jobs_metrics_gauges


pytestmark = pytest.mark.pg_jobs


async def _run_once():
    stop = asyncio.Event()
    async def stopper():
        await asyncio.sleep(0.05)
        stop.set()
    task = asyncio.create_task(run_jobs_metrics_gauges(stop_event=stop))
    await stopper()
    await task


def test_slo_gauges_postgres(monkeypatch):
    dsn = os.getenv("JOBS_DB_URL")
    if not dsn:
        pytest.skip("JOBS_DB_URL not set")
    monkeypatch.setenv("JOBS_SLO_ENABLE", "true")
    monkeypatch.setenv("JOBS_SLO_WINDOW_HOURS", "24")
    monkeypatch.setenv("JOBS_SLO_MAX_GROUPS", "10")
    monkeypatch.setenv("JOBS_METRICS_INTERVAL_SEC", "0.01")

    jm = JobManager(backend="postgres", db_url=dsn)

    for owner in ("o1", "o2"):
        for i in range(2):
            j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id=owner, priority=1)
            acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=1, worker_id="w")
            assert acq
            jm.complete_job(int(acq["id"]))

    asyncio.run(_run_once())

    reg = get_metrics_registry()
    vals = list(reg.values.get("jobs.queue_latency_p50_seconds", []))
    assert vals, "Expected SLO gauges to be set on PG"
    assert "owner_user_id" in vals[-1].labels
