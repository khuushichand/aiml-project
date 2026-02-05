from __future__ import annotations

"""
Workflows daily-ledger helpers (RG v1.1).

These helpers provide best-effort, idempotent accounting of workflow runs into
the shared ResourceDailyLedger so ResourceGovernor can enforce
``workflows_runs.daily_cap`` policies.

All functions fail open when the ledger or AuthNZ DB is unavailable.
"""

import asyncio
from datetime import date, datetime, timezone
from datetime import time as dtime
from typing import Any

from loguru import logger

try:  # pragma: no cover - DAL optional during early startup/tests
    from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import (  # type: ignore
        LedgerEntry,
        ResourceDailyLedger,
    )
except Exception:  # pragma: no cover - safe fallback
    LedgerEntry = None  # type: ignore
    ResourceDailyLedger = None  # type: ignore


_WORKFLOWS_CATEGORY = "workflows_runs"

_workflows_daily_ledger: ResourceDailyLedger | None = None  # type: ignore[name-defined]
_workflows_daily_ledger_lock = asyncio.Lock()
_workflows_backfill_done: set[str] = set()


async def get_workflows_daily_ledger() -> ResourceDailyLedger | None:
    """Lazily initialize the shared ResourceDailyLedger for workflows."""
    global _workflows_daily_ledger
    if ResourceDailyLedger is None:
        return None
    if _workflows_daily_ledger is not None:
        return _workflows_daily_ledger
    async with _workflows_daily_ledger_lock:
        if _workflows_daily_ledger is not None:
            return _workflows_daily_ledger
        try:
            ledger = ResourceDailyLedger()  # type: ignore[call-arg]
            await ledger.initialize()
            _workflows_daily_ledger = ledger
            return ledger
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Workflows: ResourceDailyLedger init failed: {exc}")
            _workflows_daily_ledger = None
            return None


def workflows_ledger_category() -> str:
    """Return the ledger category name used for workflow runs."""
    return _WORKFLOWS_CATEGORY


async def backfill_legacy_runs_to_ledger(
    *,
    ledger: ResourceDailyLedger,
    db: Any,
    tenant_id: str,
    user_id: str,
    entity_scope: str,
    entity_value: str,
    day_utc: str | None = None,
) -> None:
    """
    Best-effort migration helper: mirror today's legacy run totals into the ledger.

    Computes a delta (legacy_count - ledger_used) once per process/day and
    inserts it under a deterministic op_id so that daily caps preserve
    in-progress usage after upgrades without double-counting.
    """
    if LedgerEntry is None:
        return
    day = day_utc or datetime.now(timezone.utc).date().isoformat()
    key = f"{tenant_id}:{user_id}:{day}"
    if key in _workflows_backfill_done:
        return

    try:
        midnight_dt = datetime.combine(
            date.fromisoformat(day),
            dtime(0, 0, 0, tzinfo=timezone.utc),
        )
        midnight_iso = midnight_dt.isoformat()
    except Exception:
        midnight_iso = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

    legacy_count = 0
    try:
        legacy_count = int(
            db.count_runs_for_user_window(
                tenant_id=str(tenant_id),
                user_id=str(user_id),
                window_start_iso=str(midnight_iso),
            )
            or 0
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"Workflows: legacy run-count backfill query failed: {exc}")
        _workflows_backfill_done.add(key)
        return

    if legacy_count <= 0:
        _workflows_backfill_done.add(key)
        return

    try:
        used = await ledger.total_for_day(
            entity_scope=str(entity_scope),
            entity_value=str(entity_value),
            category=_WORKFLOWS_CATEGORY,
            day_utc=day,
        )
        delta = int(legacy_count) - int(used or 0)
        if delta <= 0:
            _workflows_backfill_done.add(key)
            return

        ts = datetime.now(timezone.utc)
        entry = LedgerEntry(  # type: ignore[call-arg]
            entity_scope=str(entity_scope),
            entity_value=str(entity_value),
            category=_WORKFLOWS_CATEGORY,
            units=int(delta),
            op_id=f"workflows-legacy:{entity_scope}:{entity_value}:{day}",
            occurred_at=ts,
        )
        await ledger.add(entry)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"Workflows: legacy backfill insert skipped: {exc}")
    finally:
        _workflows_backfill_done.add(key)


async def record_workflow_run(
    *,
    entity_scope: str,
    entity_value: str,
    run_id: str,
    units: int = 1,
    occurred_at: datetime | None = None,
) -> bool:
    """
    Shadow-write a workflow run into the daily ledger.

    Returns True if inserted; False if already present or ledger unavailable.
    """
    if ResourceDailyLedger is None or LedgerEntry is None:
        return False
    ledger = await get_workflows_daily_ledger()
    if ledger is None:
        return False

    ts = occurred_at or datetime.now(timezone.utc)
    try:
        entry = LedgerEntry(  # type: ignore[call-arg]
            entity_scope=str(entity_scope),
            entity_value=str(entity_value),
            category=_WORKFLOWS_CATEGORY,
            units=max(0, int(units)),
            op_id=str(run_id),
            occurred_at=ts,
        )
        return bool(await ledger.add(entry))
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"Workflows: ledger.add failed for run_id={run_id}: {exc}")
        return False
