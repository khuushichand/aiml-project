import asyncio
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerSDK, WorkerConfig


class DummySleep:
    """Async sleep stub that records durations and yields via original sleep.

    Important: pass the original asyncio.sleep to avoid recursive self-calls
    when tests monkeypatch asyncio.sleep to this stub.
    """
    def __init__(self, orig_sleep):
        self.calls = []
        self._orig_sleep = orig_sleep

    async def __call__(self, seconds: float):
        self.calls.append(seconds)
        # Yield control using the original sleep to avoid recursion
        await self._orig_sleep(0)


@pytest.mark.asyncio
async def test_auto_renew_jitter_and_progress(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs_wsdk.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    j = jm.create_job(domain="chatbooks", queue="default", job_type="t", payload={}, owner_user_id="u")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=20, worker_id="w1")
    assert acq is not None

    # Configure worker with no jitter for deterministic sleep
    cfg = WorkerConfig(domain="chatbooks", queue="default", worker_id="w1", lease_seconds=20, renew_threshold_seconds=5, renew_jitter_seconds=0)
    sdk = WorkerSDK(jm, cfg)

    # Capture renew calls and progress fields
    calls = []
    def fake_renew(**kwargs):
        calls.append(kwargs)
        return True

    # Capture original sleep; use it inside the stub and assign to sdk._sleep
    _orig_sleep = asyncio.sleep
    sleep_stub = DummySleep(_orig_sleep)
    monkeypatch.setattr(jm, "renew_job_lease", lambda **kwargs: fake_renew(**kwargs))
    sdk._sleep = sleep_stub

    # Provide a progress callback
    def progress_cb():
        return {"progress_percent": 12.5, "progress_message": "tick"}

    task = asyncio.create_task(sdk._auto_renew(acq, progress_cb=progress_cb))
    # Let it loop twice then stop
    await _orig_sleep(0)  # enter loop
    await _orig_sleep(0)
    sdk.stop()
    try:
        await asyncio.wait_for(task, timeout=1)
    except asyncio.TimeoutError:
        task.cancel()
        raise

    # Verify sleep durations are lease - threshold (no jitter)
    assert any(abs(s - 15) < 0.1 for s in sleep_stub.calls)
    # Verify renew_job_lease received progress args
    assert any("progress_percent" in c and c.get("progress_percent") == 12.5 for c in calls)
    assert any("progress_message" in c and c.get("progress_message") == "tick" for c in calls)


@pytest.mark.asyncio
async def test_run_retryable_exception_and_backoff(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs_wsdk2.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    j = jm.create_job(domain="chatbooks", queue="default", job_type="t", payload={}, owner_user_id="u")

    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id="w2")
    assert acq is not None

    cfg = WorkerConfig(domain="chatbooks", queue="default", worker_id="w2", lease_seconds=10, backoff_base_seconds=2, backoff_max_seconds=8)
    sdk = WorkerSDK(jm, cfg)

    # Acquire once then no more jobs
    acquires = {"count": 0}
    def fake_acquire(**kwargs):
        if acquires["count"] == 0:
            acquires["count"] += 1
            return acq
        return None

    class RetryErr(Exception):
        retryable = True
        backoff_seconds = 7

    fail_calls = []
    def fake_fail(job_id, **kwargs):
        fail_calls.append({"job_id": job_id, **kwargs})

    # Capture and use original sleep inside the stub
    _orig_sleep = asyncio.sleep
    sleep_stub = DummySleep(_orig_sleep)
    monkeypatch.setattr(jm, "acquire_next_job", lambda **kwargs: fake_acquire(**kwargs))
    monkeypatch.setattr(jm, "fail_job", lambda job_id, **kwargs: fake_fail(job_id, **kwargs))
    sdk._sleep = sleep_stub

    async def handler(job):
        raise RetryErr("boom")

    run_task = asyncio.create_task(sdk.run(handler=handler))
    # Allow a few loop iterations then stop
    await _orig_sleep(0)
    await _orig_sleep(0)
    sdk.stop()
    await asyncio.wait_for(run_task, timeout=1)

    # Verify fail_job was called with retryable True and backoff_seconds from exception
    assert any(c.get("retryable") is True and int(c.get("backoff_seconds")) == 7 for c in fail_calls)
    # Verify backoff sleeps used exponential sequence up to max
    # After job handled and no further jobs, loop should sleep at least base once
    assert any(int(s) in (2, 4, 8) for s in sleep_stub.calls)


@pytest.mark.asyncio
async def test_run_cancellation_check(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs_wsdk3.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    j = jm.create_job(domain="chatbooks", queue="default", job_type="t", payload={}, owner_user_id="u")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id="w3")
    assert acq is not None

    cfg = WorkerConfig(domain="chatbooks", queue="default", worker_id="w3")
    sdk = WorkerSDK(jm, cfg)

    cancel_called = {"count": 0}
    def fake_cancel(job_id, **kwargs):
        cancel_called["count"] += 1

    monkeypatch.setattr(jm, "acquire_next_job", lambda **kwargs: acq)
    monkeypatch.setattr(jm, "cancel_job", lambda job_id, **kwargs: fake_cancel(job_id, **kwargs))

    async def handler(job):
        pytest.fail("Handler should not run when cancel_check returns True")

    async def cancel_check(job):
        return True

    run_task = asyncio.create_task(sdk.run(handler=handler, cancel_check=cancel_check))
    await asyncio.sleep(0)
    sdk.stop()
    await asyncio.wait_for(run_task, timeout=1)

    assert cancel_called["count"] >= 1
