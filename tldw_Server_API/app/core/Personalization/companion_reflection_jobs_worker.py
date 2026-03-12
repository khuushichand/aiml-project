from __future__ import annotations

import asyncio
import contextlib
import os

from loguru import logger

from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK
from tldw_Server_API.app.core.Jobs.worker_utils import coerce_int as _coerce_int
from tldw_Server_API.app.core.Jobs.worker_utils import jobs_manager_from_env as _jobs_manager
from tldw_Server_API.app.core.Personalization.companion_reflection_jobs import (
    COMPANION_REFLECTION_DOMAIN,
    companion_reflection_queue,
    handle_companion_reflection_job,
)


async def run_companion_reflection_jobs_worker(stop_event: asyncio.Event | None = None) -> None:
    worker_id = (os.getenv("COMPANION_REFLECTION_JOBS_WORKER_ID") or f"companion-reflection-{os.getpid()}").strip()
    queue = companion_reflection_queue()
    lease_seconds = _coerce_int(
        os.getenv("COMPANION_REFLECTION_JOBS_LEASE_SECONDS") or os.getenv("JOBS_LEASE_SECONDS"),
        60,
    )
    renew_jitter = _coerce_int(
        os.getenv("COMPANION_REFLECTION_JOBS_RENEW_JITTER_SECONDS")
        or os.getenv("JOBS_LEASE_RENEW_JITTER_SECONDS"),
        5,
    )
    renew_threshold = _coerce_int(
        os.getenv("COMPANION_REFLECTION_JOBS_RENEW_THRESHOLD_SECONDS")
        or os.getenv("JOBS_LEASE_RENEW_THRESHOLD_SECONDS"),
        10,
    )
    cfg = WorkerConfig(
        domain=COMPANION_REFLECTION_DOMAIN,
        queue=queue,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        renew_jitter_seconds=renew_jitter,
        renew_threshold_seconds=renew_threshold,
    )
    sdk = WorkerSDK(_jobs_manager(), cfg)
    stop_watcher: asyncio.Task[None] | None = None

    if stop_event is not None:
        async def _watch_stop() -> None:
            await stop_event.wait()
            sdk.stop()

        stop_watcher = asyncio.create_task(_watch_stop())

    logger.info("Companion reflection worker starting: queue={} worker_id={}", queue, worker_id)
    try:
        await sdk.run(handler=handle_companion_reflection_job)
    finally:
        if stop_watcher is not None and not stop_watcher.done():
            stop_watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stop_watcher


__all__ = [
    "run_companion_reflection_jobs_worker",
]
