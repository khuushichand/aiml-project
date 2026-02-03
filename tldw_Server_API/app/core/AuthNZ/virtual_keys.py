from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool


def _debug_log(msg: str) -> None:
    """Emit debug logging when budget debug mode or pytest is active."""
    try:
        debug_flag = os.getenv("BUDGET_MW_DEBUG", "").lower()
        if debug_flag in {"1", "true", "yes", "on"} or os.getenv("PYTEST_CURRENT_TEST"):
            logger.debug(msg)
            print(f"[BUDGET_DEBUG] {msg}")
    except (OSError, TypeError) as exc:
        logger.trace(f"Debug logging failed: {exc}")


def _utc_today() -> date:
    """Return today's date in UTC as a date object.

    Postgres bindings expect a date object for date comparisons, while
    SQLite queries can use ISO strings. Callers should convert as needed.
    """
    return datetime.now(timezone.utc).date()


def _month_bounds_utc(dt: datetime | None = None) -> tuple[str, str]:
    now = dt or datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    # Return ISO strings; callers will normalize tz-awareness
    return start.isoformat(), nxt.isoformat()


async def get_key_limits(key_id: int) -> dict[str, Any] | None:
    pool: DatabasePool = await get_db_pool()
    # Route API-key limit lookups through the AuthNZ repository layer so
    # virtual-key logic no longer needs to embed backend-specific SQL.
    from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo

    repo = AuthnzApiKeysRepo(pool)
    return await repo.fetch_key_limits(key_id)


async def summarize_usage_for_key_day(
    key_id: int, day_iso: str | date | None = None
) -> dict[str, Any]:
    """
    Summarizes total tokens and USD cost for a given API key on a specific UTC day.

    Parameters:
        day_iso (Optional[str|datetime.date]): ISO date string (YYYY-MM-DD) or a date
            object specifying the UTC day to summarize. If omitted, the current UTC
            date is used.

    Returns:
        dict: A dictionary with keys:
            - "tokens" (int): Total tokens consumed on the specified day.
            - "usd" (float): Total USD cost incurred on the specified day.
    """
    day_val = day_iso if day_iso is not None else _utc_today()
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.usage_repo import AuthnzUsageRepo

    repo = AuthnzUsageRepo(pool)
    if isinstance(day_val, date):
        summary = await repo.summarize_key_day(key_id=key_id, day=day_val)
    else:
        try:
            parsed = date.fromisoformat(str(day_val))
        except ValueError:
            parsed = _utc_today()
        summary = await repo.summarize_key_day(key_id=key_id, day=parsed)

    result = {
        "tokens": int(summary.get("tokens", 0)),
        "usd": float(summary.get("usd", 0.0)),
    }
    _debug_log(f"VK summarize day: key_id={key_id} day={day_val} -> {result}")
    return result


async def summarize_usage_for_key_month(key_id: int) -> dict[str, Any]:
    """
    Summarizes token and USD usage for a key over a rolling 30-day UTC window.

    Returns:
        dict: A mapping with keys ``tokens`` (int) and ``usd`` (float); both are
        0 when no usage records are found.
    """
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.usage_repo import AuthnzUsageRepo

    repo = AuthnzUsageRepo(pool)
    totals = await repo.summarize_key_rolling_window(key_id=key_id, days=30)
    out = {
        "tokens": int(totals.get("tokens", 0)),
        "usd": float(totals.get("usd", 0.0)),
    }
    _debug_log(f"VK summarize month: key_id={key_id} rolling_days=30 -> {out}")
    return out


async def is_key_over_budget(key_id: int) -> dict[str, Any]:
    """
    Determine whether the given API key has exceeded any configured consumption limits for its current day and rolling 30-day window.

    Returns:
        A dictionary with:
        - `over` - `True` if any configured limit is exceeded, `False` otherwise.
        - `reasons` - list of strings describing which limits were exceeded and the observed/current values (e.g., "day_tokens_exceeded:1234/1000").
        - `day` - daily usage summary with keys `tokens` (int) and `usd` (float).
        - `month` - 30-day usage summary with keys `tokens` (int) and `usd` (float).
        - `limits` - the stored limit configuration for the key (as returned by the database), or an empty dict when no limits exist.
    """
    limits = await get_key_limits(key_id)
    if not limits or not limits.get("is_virtual"):
        return {"over": False, "reasons": [], "day": {}, "month": {}, "limits": limits or {}}

    day = await summarize_usage_for_key_day(key_id)
    month = await summarize_usage_for_key_month(key_id)

    reasons = []
    d_tok = limits.get("llm_budget_day_tokens")
    if d_tok is not None and day["tokens"] >= int(d_tok):
        reasons.append(f"day_tokens_exceeded:{day['tokens']}/{d_tok}")
    d_usd = limits.get("llm_budget_day_usd")
    if d_usd is not None and day["usd"] >= float(d_usd):
        reasons.append(f"day_usd_exceeded:{day['usd']}/{d_usd}")
    m_tok = limits.get("llm_budget_month_tokens")
    if m_tok is not None and month["tokens"] >= int(m_tok):
        reasons.append(f"month_tokens_exceeded:{month['tokens']}/{m_tok}")
    m_usd = limits.get("llm_budget_month_usd")
    if m_usd is not None and month["usd"] >= float(m_usd):
        reasons.append(f"month_usd_exceeded:{month['usd']}/{m_usd}")

    result = {"over": len(reasons) > 0, "reasons": reasons, "day": day, "month": month, "limits": limits}
    _debug_log(f"VK over_budget check: key_id={key_id} -> {result}")
    return result
