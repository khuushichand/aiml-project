"""
Workflows Scheduler service

Provides a lightweight recurring scheduler (cron-based) that enqueues
`workflow_run` tasks into the core Scheduler and persists definitions
in the Workflows Scheduler DB.

Env:
  WORKFLOWS_SCHEDULER_ENABLED=true   -> start service at app startup
  WORKFLOWS_SCHEDULER_TZ=<IANA>      -> default timezone (e.g., UTC)
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional, List
from loguru import logger

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from tldw_Server_API.app.core.Scheduler import create_scheduler, Scheduler
from tldw_Server_API.app.core.Scheduler.handlers import workflows as _ensure_handlers  # noqa: F401  # register workflow_run
from tldw_Server_API.app.core.Scheduler.base.registry import get_registry
from tldw_Server_API.app.core.DB_Management.Workflows_Scheduler_DB import (
    WorkflowsSchedulerDB,
    WorkflowSchedule,
)


class _WFRecurringScheduler:
    def __init__(self) -> None:
        self._core_scheduler: Optional[Scheduler] = None
        self._aps: Optional[AsyncIOScheduler] = None
        self._db = WorkflowsSchedulerDB()
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            # Start core job scheduler (workers)
            self._core_scheduler = await create_scheduler()
            # Start APScheduler for cron
            tz = os.getenv("WORKFLOWS_SCHEDULER_TZ", "UTC")
            self._aps = AsyncIOScheduler(timezone=tz)
            self._aps.start()
            # Load existing schedules
            await self._load_all()
            self._started = True
            logger.info("Workflows recurring scheduler started")

    async def stop(self) -> None:
        async with self._lock:
            try:
                if self._aps:
                    self._aps.shutdown(wait=False)
            except Exception:
                pass
            try:
                if self._core_scheduler:
                    await self._core_scheduler.stop()
            except Exception:
                pass
            self._aps = None
            self._core_scheduler = None
            self._started = False
            logger.info("Workflows recurring scheduler stopped")

    async def _load_all(self) -> None:
        # Load enabled schedules and (re)register
        try:
            # Without tenant filter here; jobs are per-tenant but service runs centrally
            # Call list twice: once without user filter; DB may grow, so keep bounded
            items = self._db.list_schedules(tenant_id="default", user_id=None, limit=1000, offset=0)
            # For multi-tenant, consider scanning all tenants
        except Exception:
            items = []
        for s in items:
            if s.enabled:
                self._add_job(s)

    def _add_job(self, schedule: WorkflowSchedule) -> None:
        if not self._aps:
            return
        try:
            # Remove existing job with same id
            try:
                self._aps.remove_job(schedule.id)
            except Exception:
                pass
            tz = schedule.timezone or os.getenv("WORKFLOWS_SCHEDULER_TZ", "UTC")
            # Validate cron; provide feedback via logs on errors
            try:
                trigger = CronTrigger.from_crontab(schedule.cron, timezone=tz)
            except Exception as e:
                logger.warning(f"Invalid cron for schedule {schedule.id}: {e}")
                return

            # Per-job concurrency: skip vs queue
            # - skip: max_instances=1, coalesce=True
            # - queue: allow overlap (max_instances>1), coalesce=False
            if (schedule.concurrency_mode or "skip").lower() == "queue":
                max_instances = 3
                coalesce = False if schedule.coalesce is None else bool(schedule.coalesce)
            else:
                max_instances = 1
                coalesce = True if schedule.coalesce is None else bool(schedule.coalesce)

            misfire_grace_time = int(schedule.misfire_grace_sec or 300)
            self._aps.add_job(
                self._run_schedule,
                trigger=trigger,
                id=schedule.id,
                args=[schedule.id],
                max_instances=max_instances,
                coalesce=coalesce,
                misfire_grace_time=misfire_grace_time,
            )

            # Compute and persist next run time
            try:
                now = datetime.now(trigger.timezone)
                nxt = trigger.get_next_fire_time(None, now)
                next_iso = nxt.isoformat() if nxt else None
                self._db.set_history(schedule.id, next_run_at=next_iso)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Failed to add schedule job {schedule.id}: {e}")

    async def _run_schedule(self, schedule_id: str) -> None:
        # Fetch latest schedule in case it was modified
        s = self._db.get_schedule(schedule_id)
        if not s or not s.enabled:
            return
        # Record last_run_at and pending status
        try:
            self._db.set_history(schedule_id, last_run_at=datetime.utcnow().isoformat(), last_status="pending")
        except Exception:
            pass
        payload = {
            "workflow_id": s.workflow_id,
            "inputs": __import__("json").loads(s.inputs_json or "{}"),
            "user_id": s.user_id,
            "tenant_id": s.tenant_id,
            "mode": s.run_mode,
            "validation_mode": s.validation_mode,
        }
        try:
            if self._core_scheduler is None:
                logger.warning("Core Scheduler not initialized; skipping schedule run")
                return
            task_id = await self._core_scheduler.submit(
                handler="workflow_run",
                payload=payload,
                queue_name="workflows",
                metadata={"user_id": s.user_id},
            )
            logger.info(f"Scheduled workflow_run submitted: task_id={task_id} schedule_id={s.id}")
            try:
                self._db.set_history(schedule_id, last_status="queued")
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Failed to submit scheduled workflow_run: {e}")
            try:
                self._db.set_history(schedule_id, last_status="error")
            except Exception:
                pass

    # CRUD wrappers
    def create(self, *, tenant_id: str, user_id: str, workflow_id: Optional[int], name: Optional[str], cron: str, timezone: Optional[str], inputs: Dict[str, Any], run_mode: str, validation_mode: str, enabled: bool, concurrency_mode: str = "skip", misfire_grace_sec: int = 300, coalesce: bool = True) -> str:
        sid = __import__("uuid").uuid4().hex
        self._db.create_schedule(
            id=sid,
            tenant_id=tenant_id,
            user_id=user_id,
            workflow_id=workflow_id,
            name=name,
            cron=cron,
            timezone=timezone,
            inputs=inputs,
            run_mode=run_mode,
            validation_mode=validation_mode,
            enabled=enabled,
            concurrency_mode=concurrency_mode,
            misfire_grace_sec=int(misfire_grace_sec),
            coalesce=bool(coalesce),
        )
        s = self._db.get_schedule(sid)
        if s and s.enabled:
            self._add_job(s)
        return sid

    def update(self, schedule_id: str, update: Dict[str, Any]) -> bool:
        ok = self._db.update_schedule(schedule_id, update)
        s = self._db.get_schedule(schedule_id)
        if s:
            if s.enabled:
                self._add_job(s)
            else:
                try:
                    if self._aps:
                        self._aps.remove_job(schedule_id)
                except Exception:
                    pass
        return ok

    def delete(self, schedule_id: str) -> bool:
        try:
            if self._aps:
                self._aps.remove_job(schedule_id)
        except Exception:
            pass
        return self._db.delete_schedule(schedule_id)

    def get(self, schedule_id: str) -> Optional[WorkflowSchedule]:
        return self._db.get_schedule(schedule_id)

    def list(self, *, tenant_id: str, user_id: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[WorkflowSchedule]:
        return self._db.list_schedules(tenant_id=tenant_id, user_id=user_id, limit=limit, offset=offset)


_INSTANCE: Optional[_WFRecurringScheduler] = None


def get_workflows_scheduler() -> _WFRecurringScheduler:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = _WFRecurringScheduler()
    return _INSTANCE


async def start_workflows_scheduler() -> Optional[asyncio.Task]:
    enabled = os.getenv("WORKFLOWS_SCHEDULER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    svc = get_workflows_scheduler()
    await svc.start()
    # return a dummy task to integrate with lifespan management
    async def _noop():
        while True:
            await asyncio.sleep(60)
    task = asyncio.create_task(_noop(), name="workflows_recurring_scheduler")
    return task


async def stop_workflows_scheduler(task: Optional[asyncio.Task]) -> None:
    try:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    except Exception:
        pass
    try:
        await get_workflows_scheduler().stop()
    except Exception:
        pass
