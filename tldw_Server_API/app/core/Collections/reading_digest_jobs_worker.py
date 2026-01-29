"""
Reading digest Jobs worker.

Consumes core Jobs entries for reading digest generation.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.Collections.reading_digest_jobs import (
    READING_DIGEST_DOMAIN,
    handle_reading_digest_job,
    reading_digest_queue,
)
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK
from tldw_Server_API.app.core.Jobs.worker_utils import coerce_int as _coerce_int
from tldw_Server_API.app.core.Jobs.worker_utils import jobs_manager_from_env as _jobs_manager


async def run_reading_digest_jobs_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    """Run the reading digest jobs worker loop.

    Args:
        stop_event: Optional asyncio.Event used to request graceful shutdown.
    """
    worker_id = (os.getenv("READING_DIGEST_JOBS_WORKER_ID") or f"reading-digest-{os.getpid()}").strip()
    queue = reading_digest_queue()
    lease_seconds = _coerce_int(os.getenv("READING_DIGEST_JOBS_LEASE_SECONDS") or os.getenv("JOBS_LEASE_SECONDS"), 60)
    renew_jitter = _coerce_int(os.getenv("READING_DIGEST_JOBS_RENEW_JITTER_SECONDS") or os.getenv("JOBS_LEASE_RENEW_JITTER_SECONDS"), 5)
    renew_threshold = _coerce_int(os.getenv("READING_DIGEST_JOBS_RENEW_THRESHOLD_SECONDS") or os.getenv("JOBS_LEASE_RENEW_THRESHOLD_SECONDS"), 10)
    cfg = WorkerConfig(
        domain=READING_DIGEST_DOMAIN,
        queue=queue,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        renew_jitter_seconds=renew_jitter,
        renew_threshold_seconds=renew_threshold,
    )
    sdk = WorkerSDK(_jobs_manager(), cfg)
    _stop_watcher_task: Optional[asyncio.Task[None]] = None

    if stop_event is not None:
        async def _watch_stop() -> None:
            await stop_event.wait()
            sdk.stop()

        _stop_watcher_task = asyncio.create_task(_watch_stop())

    logger.info("Reading digest worker starting: queue={} worker_id={}", queue, worker_id)
    try:
        await sdk.run(handler=handle_reading_digest_job)
    finally:
        if _stop_watcher_task is not None and not _stop_watcher_task.done():
            _stop_watcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _stop_watcher_task


if __name__ == "__main__":
    asyncio.run(run_reading_digest_jobs_worker())
