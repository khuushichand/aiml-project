from __future__ import annotations

import asyncio
import contextlib
import os

from loguru import logger

from tldw_Server_API.app.core.Ingestion_Sources.jobs import DOMAIN, ingestion_sources_queue
from tldw_Server_API.app.core.testing import env_flag_enabled

try:
    from tldw_Server_API.app.core.Jobs.manager import JobManager
except ImportError:  # pragma: no cover - optional
    JobManager = None  # type: ignore

_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


async def run_ingestion_sources_worker(stop_event: asyncio.Event | None = None) -> None:
    if JobManager is None:
        logger.warning("Jobs manager unavailable; ingestion sources worker disabled")
        return

    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.Ingestion_Sources.service import (
        finish_source_sync_job,
        start_source_sync_job,
    )

    jm = JobManager()
    worker_id = "ingestion-sources-worker"
    poll_sleep = float(os.getenv("INGESTION_SOURCES_POLL_INTERVAL_SECONDS", "1.0") or "1.0")
    queue_name = ingestion_sources_queue()

    logger.info("Starting ingestion sources worker")
    while True:
        if stop_event and stop_event.is_set():
            logger.info("Stopping ingestion sources worker on shutdown signal")
            return
        try:
            job = jm.acquire_next_job(
                domain=DOMAIN,
                queue=queue_name,
                lease_seconds=120,
                worker_id=worker_id,
            )
            if not job:
                await asyncio.sleep(poll_sleep)
                continue

            jid = int(job["id"])
            lease_id = str(job.get("lease_id") or "")
            payload = job.get("payload") or {}
            source_id = int(payload.get("source_id"))

            pool = await get_db_pool()
            try:
                async with pool.transaction() as db:
                    state = await start_source_sync_job(db, source_id=source_id, job_id=str(jid))
                if str(state.get("active_job_id") or "") != str(jid):
                    jm.fail_job(
                        jid,
                        error=f"Active sync job already exists for source {source_id}",
                        retryable=True,
                        backoff_seconds=30,
                        worker_id=worker_id,
                        lease_id=lease_id or None,
                        completion_token=lease_id or None,
                    )
                    continue

                async with pool.transaction() as db:
                    await finish_source_sync_job(
                        db,
                        source_id=source_id,
                        job_id=str(jid),
                        outcome="success",
                    )
                jm.complete_job(
                    jid,
                    result={"status": "completed", "source_id": source_id},
                    worker_id=worker_id,
                    lease_id=lease_id or None,
                    completion_token=lease_id or None,
                )
            except _NONCRITICAL_EXCEPTIONS as exc:
                with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
                    async with pool.transaction() as db:
                        await finish_source_sync_job(
                            db,
                            source_id=source_id,
                            job_id=str(jid),
                            outcome="failure",
                            error=str(exc),
                        )
                jm.fail_job(
                    jid,
                    error=str(exc),
                    retryable=False,
                    worker_id=worker_id,
                    lease_id=lease_id or None,
                    completion_token=lease_id or None,
                )
        except _NONCRITICAL_EXCEPTIONS:
            await asyncio.sleep(poll_sleep)


async def start_ingestion_sources_worker() -> asyncio.Task | None:
    if not env_flag_enabled("INGESTION_SOURCES_WORKER_ENABLED"):
        return None
    stop = asyncio.Event()
    return asyncio.create_task(run_ingestion_sources_worker(stop), name="ingestion-sources-worker")
