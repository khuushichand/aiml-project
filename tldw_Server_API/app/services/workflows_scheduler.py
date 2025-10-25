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
from typing import Any, Dict, Optional, List, Set
from loguru import logger

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import random

from tldw_Server_API.app.core.Scheduler import get_global_scheduler, Scheduler
from tldw_Server_API.app.core.Scheduler.handlers import workflows as _ensure_handlers  # noqa: F401  # register workflow_run
from tldw_Server_API.app.core.Scheduler.handlers import watchlists as _ensure_watchlists  # noqa: F401  # register watchlist_run
from tldw_Server_API.app.core.Scheduler.base.registry import get_registry
from tldw_Server_API.app.core.DB_Management.Workflows_Scheduler_DB import (
    WorkflowsSchedulerDB,
    WorkflowSchedule,
)
from tldw_Server_API.app.core.config import settings as core_settings
from pathlib import Path
from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager


class _WFRecurringScheduler:
    def __init__(self) -> None:
        self._core_scheduler: Optional[Scheduler] = None
        self._aps: Optional[AsyncIOScheduler] = None
        self._db = WorkflowsSchedulerDB()
        self._lock = asyncio.Lock()
        self._started = False
        # Cache of per-user scheduler DB handles
        self._db_cache: Dict[int, WorkflowsSchedulerDB] = {}
        self._rescan_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            # Start or reuse the global core job scheduler (workers)
            self._core_scheduler = await get_global_scheduler()
            # Start APScheduler for cron
            tz = os.getenv("WORKFLOWS_SCHEDULER_TZ", "UTC")
            self._aps = AsyncIOScheduler(timezone=tz)
            self._aps.start()
            # Load existing schedules
            await self._load_all()
            # Periodic rescan to pick up new/removed schedules
            try:
                interval = int(os.getenv("WORKFLOWS_SCHEDULER_RESCAN_SEC", "600") or 600)
            except Exception:
                interval = 600
            async def _rescan_loop():
                while True:
                    try:
                        await asyncio.sleep(interval)
                        await self._rescan_once()
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.debug(f"Workflows scheduler: rescan error: {e}")
            self._rescan_task = asyncio.create_task(_rescan_loop(), name="workflows_scheduler_rescan")
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
            try:
                if self._rescan_task:
                    self._rescan_task.cancel()
                    try:
                        await self._rescan_task
                    except asyncio.CancelledError:
                        pass
            except Exception:
                pass
            self._rescan_task = None
            self._started = False
            logger.info("Workflows recurring scheduler stopped")

    async def _load_all(self) -> None:
        """Scan all user directories and register their schedules."""
        loaded = 0
        try:
            base: Path = core_settings.get("USER_DB_BASE_DIR")
            user_ids: Set[int] = set()
            if base and isinstance(base, Path) and base.exists():
                for p in base.iterdir():
                    if p.is_dir():
                        try:
                            user_ids.add(int(p.name))
                        except Exception:
                            continue
            # Always include single-user fixed ID
            try:
                user_ids.add(int(core_settings.get("SINGLE_USER_FIXED_ID", 1)))
            except Exception:
                pass

            for uid in sorted(user_ids):
                try:
                    db = self._get_db(uid)
                    items = db.list_schedules(tenant_id="default", user_id=None, limit=1000, offset=0)
                except Exception:
                    items = []
                for s in items:
                    if s.enabled:
                        self._add_job(s, uid)
                        loaded += 1
        except Exception as e:
            logger.debug(f"Workflows scheduler load_all failed: {e}")
        if loaded:
            logger.info(f"Workflows scheduler: registered {loaded} schedule(s)")

    def _get_db(self, user_id: int) -> WorkflowsSchedulerDB:
        if user_id not in self._db_cache:
            self._db_cache[user_id] = WorkflowsSchedulerDB(user_id=user_id)
        return self._db_cache[user_id]

    async def _rescan_once(self) -> None:
        if not self._aps:
            return
        # Collect desired enabled schedule IDs from all users
        desired: Set[str] = set()
        base: Path = core_settings.get("USER_DB_BASE_DIR")
        user_ids: Set[int] = set()
        if base and isinstance(base, Path) and base.exists():
            for p in base.iterdir():
                if p.is_dir():
                    try:
                        user_ids.add(int(p.name))
                    except Exception:
                        continue
        try:
            user_ids.add(int(core_settings.get("SINGLE_USER_FIXED_ID", 1)))
        except Exception:
            pass
        for uid in sorted(user_ids):
            try:
                db = self._get_db(uid)
                items = db.list_schedules(tenant_id="default", user_id=None, limit=1000, offset=0)
            except Exception:
                items = []
            for s in items:
                if s.enabled:
                    desired.add(s.id)
                    # Ensure job exists/updated
                    self._add_job(s, uid)
        # Remove jobs that no longer exist or are disabled
        try:
            current_ids = {j.id for j in (self._aps.get_jobs() or [])}
            for jid in list(current_ids - desired):
                try:
                    self._aps.remove_job(jid)
                except Exception:
                    pass
        except Exception:
            pass

    def _add_job(self, schedule: WorkflowSchedule, user_id: Optional[int] = None) -> None:
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
            # Pass user_id so run handler can pick correct per-user DB
            effective_uid = user_id if user_id is not None else int(schedule.user_id)
            # Determine jitter: prefer enabling for watchlist jobs to avoid the "on the hour" thundering herd
            jitter_sec = 0
            try:
                raw_inputs = __import__("json").loads(schedule.inputs_json or "{}")
                is_watchlist = isinstance(raw_inputs, dict) and bool(raw_inputs.get("watchlist_job_id"))
                if is_watchlist:
                    try:
                        jitter_env = os.getenv("WATCHLISTS_SCHEDULER_JITTER_SEC", "90")
                        jitter_sec = int(jitter_env) if str(jitter_env).strip() else 90
                        if jitter_sec < 0:
                            jitter_sec = 0
                    except Exception:
                        jitter_sec = 90
            except Exception:
                jitter_sec = 0

            # Persist jitter metadata for watchlist schedules
            try:
                if jitter_sec > 0:
                    self._get_db(effective_uid).update_schedule(schedule.id, {"jitter_sec": jitter_sec})
            except Exception:
                pass

            self._aps.add_job(
                self._run_schedule,
                trigger=trigger,
                id=schedule.id,
                args=[schedule.id, effective_uid],
                max_instances=max_instances,
                coalesce=coalesce,
                misfire_grace_time=misfire_grace_time,
                jitter=jitter_sec if jitter_sec > 0 else None,
            )

            # Compute and persist next run time
            try:
                now = datetime.now(trigger.timezone)
                nxt = trigger.get_next_fire_time(None, now)
                # Mild UI jitter for watchlists to avoid synchronized display
                next_dt = nxt
                try:
                    if jitter_sec > 0:
                        ui_jitter = int(os.getenv("WATCHLISTS_NEXT_RUN_UI_JITTER_SEC", "60") or 60)
                        if ui_jitter > 0 and next_dt is not None:
                            delta = random.randint(-ui_jitter, ui_jitter)
                            next_dt = next_dt + timedelta(seconds=delta)
                except Exception:
                    pass
                next_iso = next_dt.isoformat() if next_dt else None
                self._get_db(effective_uid).set_history(schedule.id, next_run_at=next_iso)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Failed to add schedule job {schedule.id}: {e}")

    async def _run_schedule(self, schedule_id: str, user_id: Optional[int] = None) -> None:
        # Fetch latest schedule in case it was modified
        # Backward compatibility: determine user_id from stored schedule when not provided
        db = None
        if user_id is not None:
            db = self._get_db(int(user_id))
            s = db.get_schedule(schedule_id)
        else:
            s = self._db.get_schedule(schedule_id)
            if s is not None:
                try:
                    db = self._get_db(int(s.user_id))
                except Exception:
                    db = self._db
            else:
                db = self._db
                s = db.get_schedule(schedule_id)
        if not s or not s.enabled:
            return
        # Record last_run_at and pending status
        try:
            from datetime import timezone
            db.set_history(schedule_id, last_run_at=datetime.now(timezone.utc).isoformat(), last_status="pending")
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
        # Presence gating: optionally skip when user is offline
        try:
            if getattr(s, "require_online", False):
                sm = await get_session_manager()
                sessions = await sm.get_active_sessions(int(s.user_id))
                if not sessions:
                    # mark skipped and compute next run time
                    try:
                        tz = s.timezone or os.getenv("WORKFLOWS_SCHEDULER_TZ", "UTC")
                        trigger = CronTrigger.from_crontab(s.cron, timezone=tz)
                        now = datetime.now(trigger.timezone)
                        nxt = trigger.get_next_fire_time(None, now)
                        db.set_history(schedule_id, last_status="skipped_offline", next_run_at=(nxt.isoformat() if nxt else None))
                    except Exception:
                        db.set_history(schedule_id, last_status="skipped_offline")
                    return
        except Exception as _e:
            logger.debug(f"Presence gating check failed for schedule {schedule_id}: {_e}")
        # Optionally mint a short-lived, scoped bearer token and inject into run secrets
        try:
            use_vk = os.getenv("WORKFLOWS_MINT_VIRTUAL_KEYS", "").strip().lower() in {"1", "true", "yes", "on"}
            if use_vk:
                from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
                from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
                settings = _get_settings()
                jwt_svc = JWTService(settings)
                ttl = int(os.getenv("WORKFLOWS_VIRTUAL_KEY_TTL_MIN", "15") or 15)
                token = jwt_svc.create_virtual_access_token(
                    user_id=int(s.user_id),
                    username=str(s.user_id),
                    role="user",
                    scope="workflows",
                    ttl_minutes=ttl,
                    schedule_id=str(schedule_id),
                )
                payload["secrets"] = {"jwt": token}
        except Exception as _vk_e:
            logger.debug(f"Scheduler: virtual-key minting disabled/failed: {_vk_e}")
        try:
            if self._core_scheduler is None:
                logger.warning("Core Scheduler not initialized; skipping schedule run")
                return
            handler_name = "workflow_run"
            try:
                if isinstance(payload.get("inputs"), dict) and payload["inputs"].get("watchlist_job_id"):
                    handler_name = "watchlist_run"
            except Exception:
                pass
            task_id = await self._core_scheduler.submit(
                handler=handler_name,
                payload=payload,
                queue_name="workflows" if handler_name == "workflow_run" else "watchlists",
                metadata={"user_id": s.user_id},
            )
            logger.info(f"Scheduled workflow_run submitted: task_id={task_id} schedule_id={s.id}")
            try:
                db.set_history(schedule_id, last_status="queued")
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Failed to submit scheduled workflow_run: {e}")
            try:
                db.set_history(schedule_id, last_status="error")
            except Exception:
                pass

    # CRUD wrappers
    def create(self, *, tenant_id: str, user_id: str, workflow_id: Optional[int], name: Optional[str], cron: str, timezone: Optional[str], inputs: Dict[str, Any], run_mode: str, validation_mode: str, enabled: bool, concurrency_mode: str = "skip", misfire_grace_sec: int = 300, coalesce: bool = True, require_online: bool = False) -> str:
        sid = __import__("uuid").uuid4().hex
        db = self._get_db(int(user_id))
        db.create_schedule(
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
            require_online=require_online,
            concurrency_mode=concurrency_mode,
            misfire_grace_sec=int(misfire_grace_sec),
            coalesce=bool(coalesce),
        )
        s = db.get_schedule(sid)
        if s and s.enabled:
            self._add_job(s, int(user_id))
        return sid

    def update(self, schedule_id: str, update: Dict[str, Any]) -> bool:
        # Resolve correct DB by locating the schedule first
        s = self.get(schedule_id)
        if not s:
            return False
        db = self._get_db(int(s.user_id))
        ok = db.update_schedule(schedule_id, update)
        s = db.get_schedule(schedule_id)
        if s:
            if s.enabled:
                self._add_job(s, int(s.user_id))
            else:
                try:
                    if self._aps:
                        self._aps.remove_job(schedule_id)
                except Exception:
                    pass
        return ok

    def delete(self, schedule_id: str) -> bool:
        s = self.get(schedule_id)
        if not s:
            return False
        try:
            if self._aps:
                self._aps.remove_job(schedule_id)
        except Exception:
            pass
        db = self._get_db(int(s.user_id))
        return db.delete_schedule(schedule_id)

    def get(self, schedule_id: str) -> Optional[WorkflowSchedule]:
        # Check default DB first
        found = self._db.get_schedule(schedule_id)
        if found:
            return found
        # Scan per-user DBs
        try:
            base: Path = core_settings.get("USER_DB_BASE_DIR")
            if base and isinstance(base, Path) and base.exists():
                for p in base.iterdir():
                    if not p.is_dir():
                        continue
                    try:
                        uid = int(p.name)
                    except Exception:
                        continue
                    db = self._get_db(uid)
                    s = db.get_schedule(schedule_id)
                    if s:
                        return s
        except Exception:
            pass
        return None

    def list(self, *, tenant_id: str, user_id: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[WorkflowSchedule]:
        # Require user_id to select correct per-user DB
        if not user_id:
            return []
        try:
            db = self._get_db(int(user_id))
            return db.list_schedules(tenant_id=tenant_id, user_id=user_id, limit=limit, offset=offset)
        except Exception:
            return []


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
