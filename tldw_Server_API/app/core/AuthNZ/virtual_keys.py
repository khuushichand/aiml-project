from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Optional, Dict, Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool


def _utc_today() -> date:
    """Return today's date in UTC as a date object.

    Postgres bindings expect a date object for date comparisons, while
    SQLite queries can use ISO strings. Callers should convert as needed.
    """
    return datetime.now(timezone.utc).date()


def _month_bounds_utc(dt: Optional[datetime] = None) -> tuple[str, str]:
    now = dt or datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    # Return ISO strings; callers will normalize tz-awareness
    return start.isoformat(), nxt.isoformat()


async def get_key_limits(key_id: int) -> Optional[Dict[str, Any]]:
    pool: DatabasePool = await get_db_pool()
    # Route API-key limit lookups through the AuthNZ repository layer so
    # virtual-key logic no longer needs to embed backend-specific SQL.
    from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo

    repo = AuthnzApiKeysRepo(pool)
    return await repo.fetch_key_limits(key_id)


async def summarize_usage_for_key_day(key_id: int, day_iso: Optional[str] = None) -> Dict[str, Any]:
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
    try:
        import os
        if os.getenv("BUDGET_MW_DEBUG", "").lower() in {"1","true","yes","on"} or os.getenv("PYTEST_CURRENT_TEST") is not None:
            logger.debug(f"VK summarize day: key_id={key_id} day={day_val} -> {result}")
            print(f"[BUDGET_DEBUG] day-summary key={key_id} day={day_val} -> {result}")
    except Exception:
        pass
    return result


async def summarize_usage_for_key_month(key_id: int) -> Dict[str, Any]:
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
    try:
        import os
        if os.getenv("BUDGET_MW_DEBUG", "").lower() in {"1","true","yes","on"} or os.getenv("PYTEST_CURRENT_TEST") is not None:
            logger.debug(f"VK summarize month: key_id={key_id} start={start_dt} end={end_dt} -> {out}")
            print(f"[BUDGET_DEBUG] month-summary key={key_id} start={start_dt} end={end_dt} -> {out}")
    except Exception:
        pass
    return out


async def is_key_over_budget(key_id: int) -> Dict[str, Any]:
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
    try:
        import os
        if os.getenv("BUDGET_MW_DEBUG", "").lower() in {"1","true","yes","on"} or os.getenv("PYTEST_CURRENT_TEST") is not None:
            logger.debug(f"VK over_budget check: key_id={key_id} -> {result}")
            print(f"[BUDGET_DEBUG] over-budget key={key_id} -> {result}")
    except Exception:
        pass
    return result
