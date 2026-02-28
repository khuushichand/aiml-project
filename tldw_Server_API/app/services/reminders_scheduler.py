"""
Reminders scheduler service.

Cron/date scheduler that enqueues due reminder task jobs into the core Jobs
pipeline and persists next-run bookkeeping in the per-user Collections DB.

Env:
  REMINDERS_SCHEDULER_ENABLED=true -> start service at app startup
  REMINDERS_SCHEDULER_TZ=<IANA>    -> default timezone (e.g., UTC)
  REMINDERS_SCHEDULER_RESCAN_SEC   -> periodic task rescan interval
  REMINDER_JOBS_QUEUE              -> queue name for reminder jobs (default: default)
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger

from tldw_Server_API.app.core.config import settings as core_settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase, ReminderTaskRow
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.testing import env_flag_enabled

REMINDERS_DOMAIN = "notifications"
REMINDER_JOB_TYPE = "reminder_due"
_MIN_RESCAN_SECONDS = 30
_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


def reminders_jobs_queue() -> str:
    queue = (os.getenv("REMINDER_JOBS_QUEUE") or "default").strip()
    return queue or "default"


def _parse_iso_datetime(value: str | None, *, timezone_name: str | None = None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        if timezone_name:
            try:
                parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
            except _NONCRITICAL_EXCEPTIONS:
                parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_slot_to_utc_iso(slot: datetime, *, timezone_name: str | None = None) -> str:
    if slot.tzinfo is None:
        if timezone_name:
            try:
                slot = slot.replace(tzinfo=ZoneInfo(timezone_name))
            except _NONCRITICAL_EXCEPTIONS:
                slot = slot.replace(tzinfo=timezone.utc)
        else:
            slot = slot.replace(tzinfo=timezone.utc)
    return slot.astimezone(timezone.utc).isoformat()


class _RemindersScheduler:
    def __init__(self) -> None:
        self._aps: AsyncIOScheduler | None = None
        self._db_cache: dict[int, CollectionsDatabase] = {}
        self._lock = asyncio.Lock()
        self._started = False
        self._rescan_task: asyncio.Task | None = None
        self._jobs = JobManager()

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            tz = os.getenv("REMINDERS_SCHEDULER_TZ", "UTC")
            self._aps = AsyncIOScheduler(timezone=tz)
            self._aps.start()
            await self._load_all()
            try:
                interval = int(os.getenv("REMINDERS_SCHEDULER_RESCAN_SEC", "300") or 300)
            except _NONCRITICAL_EXCEPTIONS:
                interval = 300
            interval = max(_MIN_RESCAN_SECONDS, interval)

            async def _rescan_loop() -> None:
                while True:
                    try:
                        await asyncio.sleep(interval)
                        await self._rescan_once()
                    except asyncio.CancelledError:
                        break
                    except _NONCRITICAL_EXCEPTIONS as exc:
                        logger.debug("Reminders scheduler rescan error: {}", exc)

            self._rescan_task = asyncio.create_task(_rescan_loop(), name="reminders_scheduler_rescan")
            self._started = True
            logger.info("Reminders scheduler started")

    async def stop(self) -> None:
        async with self._lock:
            try:
                if self._aps:
                    self._aps.shutdown(wait=False)
            except _NONCRITICAL_EXCEPTIONS:
                pass
            self._aps = None
            try:
                if self._rescan_task:
                    self._rescan_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await self._rescan_task
            except _NONCRITICAL_EXCEPTIONS:
                pass
            self._rescan_task = None
            self._started = False
            for db in self._db_cache.values():
                with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
                    db.close()
            self._db_cache.clear()
            logger.info("Reminders scheduler stopped")

    def _get_db(self, user_id: int) -> CollectionsDatabase:
        if user_id not in self._db_cache:
            self._db_cache[user_id] = CollectionsDatabase.for_user(user_id)
        return self._db_cache[user_id]

    def _enumerate_user_ids(self) -> set[int]:
        user_ids: set[int] = set()
        try:
            base = DatabasePaths.get_user_db_base_dir()
            for entry in base.iterdir():
                if entry.is_dir():
                    with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
                        user_ids.add(int(entry.name))
        except _NONCRITICAL_EXCEPTIONS as exc:
            logger.debug("Reminders scheduler: failed to enumerate user dirs: {}", exc)
        with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
            user_ids.add(int(core_settings.get("SINGLE_USER_FIXED_ID", 1)))
        return user_ids

    async def _load_all(self) -> None:
        loaded = 0
        for uid in sorted(self._enumerate_user_ids()):
            try:
                rows = self._get_db(uid).list_reminder_tasks(include_disabled=False)
            except _NONCRITICAL_EXCEPTIONS:
                rows = []
            for task in rows:
                if task.enabled:
                    self._add_job(task, uid)
                    loaded += 1
        if loaded:
            logger.info("Reminders scheduler registered {} task(s)", loaded)

    async def _rescan_once(self) -> None:
        if not self._aps:
            return
        desired: set[str] = set()
        for uid in sorted(self._enumerate_user_ids()):
            try:
                rows = self._get_db(uid).list_reminder_tasks(include_disabled=True)
            except _NONCRITICAL_EXCEPTIONS:
                rows = []
            for task in rows:
                if task.enabled:
                    desired.add(task.id)
                    self._add_job(task, uid)
        try:
            current_ids = {job.id for job in (self._aps.get_jobs() or [])}
            for stale_id in list(current_ids - desired):
                with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
                    self._aps.remove_job(stale_id)
        except _NONCRITICAL_EXCEPTIONS:
            pass

    async def reconcile_task(self, *, task_id: str, user_id: int) -> None:
        """Immediately sync one reminder task into APS state."""
        async with self._lock:
            if not self._started or not self._aps:
                return
            db = self._get_db(int(user_id))
            try:
                task = db.get_reminder_task(task_id)
            except KeyError:
                with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
                    self._aps.remove_job(task_id)
                return
            if not task.enabled:
                with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
                    self._aps.remove_job(task_id)
                return
            self._add_job(task, int(user_id))

    async def unschedule_task(self, *, task_id: str) -> None:
        """Immediately unschedule one reminder task from APS state."""
        async with self._lock:
            if not self._started or not self._aps:
                return
            with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
                self._aps.remove_job(task_id)

    def _add_job(self, task: ReminderTaskRow, user_id: int | None = None) -> None:
        if not self._aps:
            return
        try:
            with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
                self._aps.remove_job(task.id)
            effective_uid = user_id if user_id is not None else int(task.user_id)
            db = self._get_db(effective_uid)
            scheduler_tz = os.getenv("REMINDERS_SCHEDULER_TZ", "UTC")
            if task.schedule_kind == "one_time":
                run_dt = _parse_iso_datetime(task.run_at, timezone_name=task.timezone or scheduler_tz)
                if run_dt is None:
                    logger.warning("Reminders scheduler invalid run_at for task {}", task.id)
                    return
                trigger = DateTrigger(run_date=run_dt)
                self._aps.add_job(
                    self._run_task_schedule,
                    trigger=trigger,
                    id=task.id,
                    args=[task.id, effective_uid],
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=300,
                )
                with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
                    db.update_reminder_task(task.id, {"next_run_at": run_dt.isoformat()})
                return

            tz_name = task.timezone or scheduler_tz
            try:
                trigger = CronTrigger.from_crontab(task.cron or "", timezone=tz_name)
            except _NONCRITICAL_EXCEPTIONS as exc:
                logger.warning("Reminders scheduler invalid cron for {}: {}", task.id, exc)
                return

            self._aps.add_job(
                self._run_task_schedule,
                trigger=trigger,
                id=task.id,
                args=[task.id, effective_uid],
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300,
            )
            try:
                now_local = datetime.now(trigger.timezone)
                nxt = trigger.get_next_fire_time(None, now_local)
                db.update_reminder_task(task.id, {"next_run_at": nxt.isoformat() if nxt else None})
            except _NONCRITICAL_EXCEPTIONS:
                pass
        except _NONCRITICAL_EXCEPTIONS as exc:
            logger.warning("Reminders scheduler failed to add task {}: {}", task.id, exc)

    async def _run_task_schedule(self, task_id: str, user_id: int | None = None) -> None:
        if user_id is None:
            return
        db = self._get_db(int(user_id))
        try:
            task = db.get_reminder_task(task_id)
        except KeyError:
            return
        if not task.enabled:
            return

        expected_next_raw = task.next_run_at
        scheduler_tz = os.getenv("REMINDERS_SCHEDULER_TZ", "UTC")
        now_utc = datetime.now(timezone.utc)

        try:
            if task.schedule_kind == "one_time":
                scheduled_dt = _parse_iso_datetime(
                    expected_next_raw or task.run_at,
                    timezone_name=task.timezone or scheduler_tz,
                )
                next_iso = None
            else:
                tz_name = task.timezone or scheduler_tz
                trigger = CronTrigger.from_crontab(task.cron or "", timezone=tz_name)
                now_local = datetime.now(trigger.timezone)
                scheduled_dt = _parse_iso_datetime(expected_next_raw, timezone_name=tz_name)
                if scheduled_dt is None:
                    scheduled_dt = trigger.get_next_fire_time(None, now_local)
                if scheduled_dt is None:
                    logger.warning("Reminders scheduler could not determine due slot for {}", task_id)
                    return
                now_for_next = max(now_local, scheduled_dt + timedelta(seconds=1))
                next_dt = trigger.get_next_fire_time(scheduled_dt, now_for_next)
                next_iso = next_dt.isoformat() if next_dt else None
        except _NONCRITICAL_EXCEPTIONS as exc:
            logger.warning("Reminders scheduler schedule parse failed for {}: {}", task_id, exc)
            return

        if scheduled_dt is None:
            return
        scheduled_utc = _parse_iso_datetime(_normalize_slot_to_utc_iso(scheduled_dt))
        if scheduled_utc and scheduled_utc > (now_utc + timedelta(minutes=1)):
            logger.debug("Reminders scheduler skipping early trigger for {}", task_id)
            return

        claimed = False
        try:
            claimed = db.try_claim_reminder_task_slot(
                task_id,
                expected_next_run_at=expected_next_raw,
                next_run_at=next_iso,
                last_run_at=now_utc.isoformat(),
                last_status="queued",
                disallow_statuses=("queued", "running"),
            )
        except _NONCRITICAL_EXCEPTIONS as exc:
            logger.debug("Reminders scheduler claim failed for {}: {}", task_id, exc)
        if not claimed:
            logger.info("Reminder task slot already claimed: task_id={}", task_id)
            return

        run_slot_utc = _normalize_slot_to_utc_iso(scheduled_dt, timezone_name=task.timezone or scheduler_tz)
        payload = {
            "task_id": task.id,
            "user_id": int(task.user_id),
            "scheduled_for": run_slot_utc,
        }
        idempotency_key = f"task:{task.id}:{run_slot_utc}"
        try:
            job = self._jobs.create_job(
                domain=REMINDERS_DOMAIN,
                queue=reminders_jobs_queue(),
                job_type=REMINDER_JOB_TYPE,
                payload=payload,
                owner_user_id=int(task.user_id),
                idempotency_key=idempotency_key,
            )
            logger.info("Reminder task queued: task_id={} job_id={}", task_id, job.get("id"))
        except _NONCRITICAL_EXCEPTIONS as exc:
            logger.warning("Reminder task enqueue failed for {}: {}", task_id, exc)
            with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
                db.update_reminder_task(
                    task_id,
                    {
                        "next_run_at": expected_next_raw,
                        "last_status": "error",
                    },
                )


_INSTANCE: _RemindersScheduler | None = None


def get_reminders_scheduler() -> _RemindersScheduler:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = _RemindersScheduler()
    return _INSTANCE


async def start_reminders_scheduler(enabled: bool | None = None) -> asyncio.Task | None:
    if enabled is None:
        enabled = env_flag_enabled("REMINDERS_SCHEDULER_ENABLED")
    if not enabled:
        return None
    scheduler = get_reminders_scheduler()
    await scheduler.start()

    async def _noop() -> None:
        while True:
            await asyncio.sleep(60)

    return asyncio.create_task(_noop(), name="reminders_scheduler")


async def stop_reminders_scheduler(task: asyncio.Task | None) -> None:
    try:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    except _NONCRITICAL_EXCEPTIONS:
        pass
    with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
        await get_reminders_scheduler().stop()


__all__ = [
    "REMINDERS_DOMAIN",
    "REMINDER_JOB_TYPE",
    "_RemindersScheduler",
    "_normalize_slot_to_utc_iso",
    "get_reminders_scheduler",
    "reminders_jobs_queue",
    "start_reminders_scheduler",
    "stop_reminders_scheduler",
]
