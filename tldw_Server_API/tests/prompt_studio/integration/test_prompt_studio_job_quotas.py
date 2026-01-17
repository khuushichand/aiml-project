import asyncio
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.quota_config import (
    apply_prompt_studio_quota_defaults,
)
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.services import jobs_worker


def test_prompt_studio_inflight_quota_blocks_second_acquire(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPT_STUDIO_MAX_CONCURRENT_JOBS", "1")
    monkeypatch.delenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO", raising=False)
    apply_prompt_studio_quota_defaults()

    jm = JobManager(db_path=Path(tmp_path / "ps_jobs.db"))
    jm.create_job(
        domain="prompt_studio",
        queue="default",
        job_type="optimization",
        payload={},
        owner_user_id="user-1",
    )
    jm.create_job(
        domain="prompt_studio",
        queue="default",
        job_type="optimization",
        payload={},
        owner_user_id="user-1",
    )

    first = jm.acquire_next_job(
        domain="prompt_studio",
        queue="default",
        lease_seconds=30,
        worker_id="worker-1",
        owner_user_id="user-1",
    )
    assert first is not None

    second = jm.acquire_next_job(
        domain="prompt_studio",
        queue="default",
        lease_seconds=30,
        worker_id="worker-2",
        owner_user_id="user-1",
    )
    assert second is None


@pytest.mark.asyncio
async def test_prompt_studio_shared_worker_guard_requeues(tmp_path, monkeypatch):
    async def fake_apply_policy(_user_id):
        return {}

    monkeypatch.setenv("TEST_MODE", "false")
    monkeypatch.setenv("JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO_USER_1", "1")
    monkeypatch.setattr(jobs_worker, "apply_prompt_studio_quota_policy", fake_apply_policy, raising=True)

    jm = JobManager(db_path=Path(tmp_path / "ps_jobs_guard.db"))
    for _ in range(2):
        jm.create_job(
            domain="prompt_studio",
            queue="default",
            job_type="optimization",
            payload={},
            owner_user_id="1",
        )

    first = jm.acquire_next_job(
        domain="prompt_studio",
        queue="default",
        lease_seconds=30,
        worker_id="worker-1",
        owner_user_id="1",
    )
    assert first is not None

    cfg = WorkerConfig(
        domain="prompt_studio",
        queue="default",
        worker_id="worker-2",
        lease_seconds=10,
        renew_jitter_seconds=0,
        renew_threshold_seconds=1,
    )
    sdk = WorkerSDK(jm, cfg)

    async def guard(job):
        ok = await jobs_worker._inflight_quota_guard(job, jm)
        sdk.stop()
        return ok

    async def handler(_job):
        sdk.stop()
        return {}

    await asyncio.wait_for(sdk.run(handler=handler, acquire_guard=guard), timeout=2)

    queued = jm.list_jobs(domain="prompt_studio", queue="default", status="queued", owner_user_id="1")
    processing = jm.list_jobs(domain="prompt_studio", queue="default", status="processing", owner_user_id="1")
    assert len(queued) == 1
    assert len(processing) == 1
