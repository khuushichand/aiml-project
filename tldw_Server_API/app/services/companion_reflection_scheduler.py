from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Personalization.companion_reflection_jobs import (
    COMPANION_REFLECTION_DOMAIN,
    COMPANION_REFLECTION_JOB_TYPE,
    companion_reflection_queue,
)
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


class _CompanionReflectionScheduler:
    def __init__(self) -> None:
        self._aps: AsyncIOScheduler | None = None
        self._lock = asyncio.Lock()
        self._started = False
        self._jobs = JobManager()

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            tz = os.getenv("COMPANION_REFLECTION_SCHEDULER_TZ", "UTC")
            daily_cron = os.getenv("COMPANION_REFLECTION_DAILY_CRON", "0 9 * * *")
            weekly_cron = os.getenv("COMPANION_REFLECTION_WEEKLY_CRON", "0 9 * * 1")
            self._aps = AsyncIOScheduler(timezone=tz)
            self._aps.start()
            self._aps.add_job(
                self._enqueue_all_users,
                trigger=CronTrigger.from_crontab(daily_cron, timezone=tz),
                id="companion-reflection-daily",
                args=["daily"],
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300,
            )
            self._aps.add_job(
                self._enqueue_all_users,
                trigger=CronTrigger.from_crontab(weekly_cron, timezone=tz),
                id="companion-reflection-weekly",
                args=["weekly"],
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300,
            )
            self._started = True
            logger.info("Companion reflection scheduler started")

    async def stop(self) -> None:
        async with self._lock:
            try:
                if self._aps:
                    self._aps.shutdown(wait=False)
            except _NONCRITICAL_EXCEPTIONS:
                pass
            self._aps = None
            self._started = False
            logger.info("Companion reflection scheduler stopped")

    async def _enqueue_all_users(self, cadence: str) -> None:
        slot_time = datetime.now(timezone.utc).replace(microsecond=0)
        if cadence == "weekly":
            slot_key = f"{slot_time.isocalendar().year}-W{slot_time.isocalendar().week:02d}"
        else:
            slot_key = slot_time.date().isoformat()
        for user_id in sorted(self._enumerate_user_ids()):
            payload = {
                "user_id": user_id,
                "cadence": cadence,
                "scheduled_for": slot_time.isoformat(),
            }
            idempotency_key = f"companion_reflection:{cadence}:{user_id}:{slot_key}"
            try:
                job = self._jobs.create_job(
                    domain=COMPANION_REFLECTION_DOMAIN,
                    queue=companion_reflection_queue(),
                    job_type=COMPANION_REFLECTION_JOB_TYPE,
                    payload=payload,
                    owner_user_id=int(user_id),
                    idempotency_key=idempotency_key,
                )
                logger.info(
                    "Companion reflection queued: cadence={} user_id={} job_id={}",
                    cadence,
                    user_id,
                    job.get("id"),
                )
            except _NONCRITICAL_EXCEPTIONS as exc:
                logger.warning("Companion reflection enqueue failed user_id={} cadence={}: {}", user_id, cadence, exc)

    def _enumerate_user_ids(self) -> set[int]:
        user_ids: set[int] = set()
        try:
            base = DatabasePaths.get_user_db_base_dir()
            for path in base.iterdir():
                if not path.is_dir():
                    continue
                try:
                    user_ids.add(int(path.name))
                except _NONCRITICAL_EXCEPTIONS:
                    continue
        except _NONCRITICAL_EXCEPTIONS as exc:
            logger.debug("Companion reflection scheduler failed to enumerate users: {}", exc)
        with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
            user_ids.add(int(DatabasePaths.get_single_user_id()))
        return user_ids


_INSTANCE: _CompanionReflectionScheduler | None = None


def get_companion_reflection_scheduler() -> _CompanionReflectionScheduler:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = _CompanionReflectionScheduler()
    return _INSTANCE


async def start_companion_reflection_scheduler(enabled: bool | None = None) -> asyncio.Task | None:
    if enabled is None:
        enabled = env_flag_enabled("COMPANION_REFLECTION_SCHEDULER_ENABLED")
    if not enabled:
        return None
    scheduler = get_companion_reflection_scheduler()
    await scheduler.start()

    async def _noop() -> None:
        while True:
            await asyncio.sleep(60)

    return asyncio.create_task(_noop(), name="companion_reflection_scheduler")


async def stop_companion_reflection_scheduler(task: asyncio.Task | None) -> None:
    try:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    except _NONCRITICAL_EXCEPTIONS:
        pass
    with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
        await get_companion_reflection_scheduler().stop()


__all__ = [
    "get_companion_reflection_scheduler",
    "start_companion_reflection_scheduler",
    "stop_companion_reflection_scheduler",
]
