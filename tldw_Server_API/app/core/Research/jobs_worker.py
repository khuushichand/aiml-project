"""Worker entrypoint for deep research Jobs slices."""

from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path

from loguru import logger

from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK
from tldw_Server_API.app.core.Jobs.worker_utils import coerce_int as _coerce_int
from tldw_Server_API.app.core.Jobs.worker_utils import jobs_manager_from_env as _jobs_manager

from .jobs import RESEARCH_DOMAIN, RESEARCH_QUEUE, handle_research_phase_job


async def run_research_jobs_worker(
    stop_event: asyncio.Event | None = None,
    *,
    research_db_path: str | Path | None = None,
    outputs_dir: str | Path | None = None,
) -> None:
    """Run the deep research worker loop until stopped."""
    worker_id = (os.getenv("RESEARCH_JOBS_WORKER_ID") or f"research-jobs-{os.getpid()}").strip()
    lease_seconds = _coerce_int(os.getenv("RESEARCH_JOBS_LEASE_SECONDS") or os.getenv("JOBS_LEASE_SECONDS"), 60)
    renew_jitter = _coerce_int(os.getenv("RESEARCH_JOBS_RENEW_JITTER_SECONDS") or os.getenv("JOBS_LEASE_RENEW_JITTER_SECONDS"), 5)
    renew_threshold = _coerce_int(os.getenv("RESEARCH_JOBS_RENEW_THRESHOLD_SECONDS") or os.getenv("JOBS_LEASE_RENEW_THRESHOLD_SECONDS"), 10)
    cfg = WorkerConfig(
        domain=RESEARCH_DOMAIN,
        queue=RESEARCH_QUEUE,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        renew_jitter_seconds=renew_jitter,
        renew_threshold_seconds=renew_threshold,
    )
    sdk = WorkerSDK(_jobs_manager(), cfg)
    _stop_watcher_task: asyncio.Task[None] | None = None

    if stop_event is not None:
        async def _watch_stop() -> None:
            await stop_event.wait()
            sdk.stop()

        _stop_watcher_task = asyncio.create_task(_watch_stop())

    resolved_research_db_path = Path(research_db_path or os.getenv("RESEARCH_SESSIONS_DB_PATH") or "Databases/ResearchSessions.db")
    resolved_outputs_dir = Path(outputs_dir or os.getenv("RESEARCH_OUTPUTS_DIR") or "Databases/outputs")

    async def _handler(job: dict[str, object]) -> dict[str, object]:
        return await handle_research_phase_job(
            job,
            research_db_path=resolved_research_db_path,
            outputs_dir=resolved_outputs_dir,
        )

    logger.info("Research Jobs worker starting: queue={} worker_id={}", RESEARCH_QUEUE, worker_id)
    try:
        await sdk.run(handler=_handler)
    finally:
        if _stop_watcher_task is not None and not _stop_watcher_task.done():
            _stop_watcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _stop_watcher_task


if __name__ == "__main__":
    asyncio.run(run_research_jobs_worker())
