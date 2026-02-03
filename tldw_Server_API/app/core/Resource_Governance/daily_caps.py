from __future__ import annotations

"""
Daily-cap helpers for ResourceGovernor categories.

v1.1 introduces durable per-day caps (e.g., tokens-per-day) backed by the
generic ResourceDailyLedger DAL. Governors consult these helpers when a policy
defines a ``daily_cap`` for a category.

These helpers are best-effort and fail open when the ledger is unavailable to
avoid breaking request flows during upgrades.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

try:  # pragma: no cover - DAL optional in early startup/tests
    from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import (  # type: ignore
        ResourceDailyLedger,
    )
except Exception:  # pragma: no cover - safe fallback
    ResourceDailyLedger = None  # type: ignore

_daily_ledger: "ResourceDailyLedger" | None = None  # type: ignore[name-defined]
_daily_ledger_lock = asyncio.Lock()


async def _get_ledger() -> "ResourceDailyLedger" | None:
    global _daily_ledger
    if ResourceDailyLedger is None:
        return None
    if _daily_ledger is not None:
        return _daily_ledger
    async with _daily_ledger_lock:
        if _daily_ledger is not None:
            return _daily_ledger
        try:
            ledger = ResourceDailyLedger()  # type: ignore[call-arg]
            await ledger.initialize()
            _daily_ledger = ledger
            return ledger
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"RG daily caps: ledger init failed; caps disabled: {exc}")
            _daily_ledger = None
            return None


def _seconds_until_next_utc_day(now_dt: datetime | None = None) -> int:
    dt = now_dt or datetime.now(timezone.utc)
    dt = dt.astimezone(timezone.utc)
    tomorrow = dt.date() + timedelta(days=1)
    next_midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc)
    try:
        return max(1, int((next_midnight - dt).total_seconds()))
    except Exception:
        return 60 * 60 * 24


async def check_daily_cap(
    *,
    entity_scope: str,
    entity_value: str,
    category: str,
    daily_cap: int,
    units: int,
    day_utc: str | None = None,
) -> tuple[bool, int, dict[str, Any]]:
    """
    Check whether an entity has remaining daily headroom for the given category.

    Returns (allowed, retry_after_seconds, details). When the ledger is
    unavailable or daily_cap <= 0, this returns (True, 0, {}).
    """
    try:
        cap = int(daily_cap or 0)
        if cap <= 0:
            return True, 0, {}
    except Exception:
        return True, 0, {}

    ledger = await _get_ledger()
    if ledger is None:
        return True, 0, {}

    try:
        used = await ledger.total_for_day(
            entity_scope=str(entity_scope),
            entity_value=str(entity_value),
            category=str(category),
            day_utc=day_utc,
        )
        remaining = max(0, cap - int(used or 0))
        allowed = remaining >= int(units or 0)
        retry_after = _seconds_until_next_utc_day()
        details = {
            "daily_cap": cap,
            "daily_used": int(used or 0),
            "daily_remaining": int(remaining),
            "daily_reset_seconds": int(retry_after),
        }
        return bool(allowed), int(retry_after), details
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"RG daily caps: check failed for {entity_scope}:{entity_value}:{category}: {exc}")
        return True, 0, {}
