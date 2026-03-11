from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.Ingestion_Sources.jobs import enqueue_ingestion_source_job
from tldw_Server_API.app.core.Ingestion_Sources.service import list_sources_for_scheduler
from tldw_Server_API.app.core.testing import env_flag_enabled

_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


def _scan_interval_seconds() -> int:
    try:
        value = int(os.getenv("INGESTION_SOURCES_SCHEDULER_SCAN_SEC", "300") or "300")
    except _NONCRITICAL_EXCEPTIONS:
        value = 300
    return max(30, value)


class _IngestionSourcesScheduler:
    def __init__(self) -> None:
        self._aps: AsyncIOScheduler | None = None
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            self._aps = AsyncIOScheduler(timezone="UTC")
            self._aps.start()
            self._aps.add_job(
                self._scan_once,
                trigger=IntervalTrigger(seconds=_scan_interval_seconds(), timezone="UTC"),
                id="ingestion_sources_scan",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=_scan_interval_seconds(),
            )
            self._started = True
            logger.info("Ingestion sources scheduler started")

    async def stop(self) -> None:
        async with self._lock:
            try:
                if self._aps:
                    self._aps.shutdown(wait=False)
            except _NONCRITICAL_EXCEPTIONS:
                pass
            self._aps = None
            self._started = False
            logger.info("Ingestion sources scheduler stopped")

    async def _scan_once(self) -> None:
        pool = await get_db_pool()
        async with pool.transaction() as db:
            rows = await list_sources_for_scheduler(db)

        for source in rows:
            if str(source.get("active_job_id") or "").strip():
                continue
            source_id = int(source["id"])
            user_id = int(source["user_id"])
            try:
                await asyncio.to_thread(
                    enqueue_ingestion_source_job,
                    user_id=user_id,
                    source_id=source_id,
                    job_type="scheduled_sync",
                    idempotency_key=f"ingestion_source_schedule:{source_id}",
                )
            except _NONCRITICAL_EXCEPTIONS as exc:
                logger.warning(
                    "Ingestion sources scheduler enqueue failed for source_id={}: {}",
                    source_id,
                    exc,
                )


_INSTANCE: _IngestionSourcesScheduler | None = None


def get_ingestion_sources_scheduler() -> _IngestionSourcesScheduler:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = _IngestionSourcesScheduler()
    return _INSTANCE


async def start_ingestion_sources_scheduler() -> asyncio.Task | None:
    if not env_flag_enabled("INGESTION_SOURCES_SCHEDULER_ENABLED"):
        return None
    scheduler = get_ingestion_sources_scheduler()
    await scheduler.start()

    async def _noop() -> None:
        while True:
            await asyncio.sleep(60)

    return asyncio.create_task(_noop(), name="ingestion-sources-scheduler")


async def stop_ingestion_sources_scheduler(task: asyncio.Task | None) -> None:
    try:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    except _NONCRITICAL_EXCEPTIONS:
        pass
    with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
        await get_ingestion_sources_scheduler().stop()
