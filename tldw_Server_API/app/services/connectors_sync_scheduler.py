"""
Recurring scheduler for external source sync and webhook renewal jobs.

Env:
  CONNECTORS_SYNC_SCHEDULER_ENABLED=true -> start service at app startup
  CONNECTORS_SYNC_SCHEDULER_SCAN_SEC     -> periodic scan interval (default: 300)
  CONNECTORS_SYNC_RENEWAL_LOOKAHEAD_SEC  -> renewal window before expiry (default: 3600)
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.External_Sources.connectors_service import (
    FILE_SYNC_PROVIDERS,
    create_import_job,
    list_sources_for_scheduler,
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
_MIN_SCAN_SECONDS = 30
_DEFAULT_SCAN_SECONDS = 300
_DEFAULT_RENEWAL_LOOKAHEAD_SECONDS = 3600


def _parse_utc_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except _NONCRITICAL_EXCEPTIONS:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _scan_interval_seconds() -> int:
    try:
        value = int(os.getenv("CONNECTORS_SYNC_SCHEDULER_SCAN_SEC", str(_DEFAULT_SCAN_SECONDS)) or _DEFAULT_SCAN_SECONDS)
    except _NONCRITICAL_EXCEPTIONS:
        value = _DEFAULT_SCAN_SECONDS
    return max(_MIN_SCAN_SECONDS, value)


def _renewal_lookahead_seconds() -> int:
    try:
        return max(0, int(os.getenv("CONNECTORS_SYNC_RENEWAL_LOOKAHEAD_SEC", str(_DEFAULT_RENEWAL_LOOKAHEAD_SECONDS)) or _DEFAULT_RENEWAL_LOOKAHEAD_SECONDS))
    except _NONCRITICAL_EXCEPTIONS:
        return _DEFAULT_RENEWAL_LOOKAHEAD_SECONDS


class _ConnectorsSyncScheduler:
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
                id="connectors_sync_scan",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=_scan_interval_seconds(),
            )
            self._started = True
            logger.info("Connectors sync scheduler started")

    async def stop(self) -> None:
        async with self._lock:
            try:
                if self._aps:
                    self._aps.shutdown(wait=False)
            except _NONCRITICAL_EXCEPTIONS:
                pass
            self._aps = None
            self._started = False
            logger.info("Connectors sync scheduler stopped")

    def _select_job_type(self, source: dict[str, Any], *, now: datetime) -> str | None:
        if not bool(source.get("enabled", True)):
            return None
        provider = str(source.get("provider") or "").strip().lower()
        if provider not in FILE_SYNC_PROVIDERS:
            return None
        if str(source.get("active_job_id") or "").strip():
            return None
        sync_mode = str(source.get("sync_mode") or "manual").strip().lower()
        renewal_due = False
        if source.get("webhook_status") == "active" and str(source.get("webhook_subscription_id") or "").strip():
            expires_at = _parse_utc_datetime(source.get("webhook_expires_at"))
            if expires_at is not None:
                renewal_due = expires_at <= (now + timedelta(seconds=_renewal_lookahead_seconds()))
        if renewal_due:
            return "subscription_renewal"
        if sync_mode not in {"poll", "hybrid"}:
            return None
        if bool(source.get("needs_full_rescan")):
            return "repair_rescan"
        return "incremental_sync"

    async def _scan_once(self) -> None:
        pool = await get_db_pool()
        async with pool.transaction() as db:
            rows = await list_sources_for_scheduler(db)

        now = datetime.now(UTC)
        for source in rows:
            job_type = self._select_job_type(source, now=now)
            if not job_type:
                continue
            user_id = int(source.get("user_id"))
            source_id = int(source.get("id"))
            try:
                await create_import_job(user_id, source_id, job_type=job_type)
            except _NONCRITICAL_EXCEPTIONS as exc:
                logger.warning(
                    "Connectors sync scheduler enqueue failed for source_id={} job_type={}: {}",
                    source_id,
                    job_type,
                    exc,
                )


_INSTANCE: _ConnectorsSyncScheduler | None = None


def get_connectors_sync_scheduler() -> _ConnectorsSyncScheduler:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = _ConnectorsSyncScheduler()
    return _INSTANCE


async def start_connectors_sync_scheduler(enabled: bool | None = None) -> asyncio.Task | None:
    if enabled is None:
        enabled = env_flag_enabled("CONNECTORS_SYNC_SCHEDULER_ENABLED")
    if not enabled:
        return None
    scheduler = get_connectors_sync_scheduler()
    await scheduler.start()

    async def _noop() -> None:
        while True:
            await asyncio.sleep(60)

    return asyncio.create_task(_noop(), name="connectors_sync_scheduler")


async def stop_connectors_sync_scheduler(task: asyncio.Task | None) -> None:
    try:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    except _NONCRITICAL_EXCEPTIONS:
        pass
    with contextlib.suppress(_NONCRITICAL_EXCEPTIONS):
        await get_connectors_sync_scheduler().stop()


__all__ = [
    "_ConnectorsSyncScheduler",
    "get_connectors_sync_scheduler",
    "start_connectors_sync_scheduler",
    "stop_connectors_sync_scheduler",
]
