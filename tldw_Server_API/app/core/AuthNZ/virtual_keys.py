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
    if pool.pool:
        row = await pool.fetchall(
            """
            SELECT id,
                   COALESCE(is_virtual, FALSE) AS is_virtual,
                   org_id, team_id,
                   llm_budget_day_tokens, llm_budget_month_tokens,
                   llm_budget_day_usd, llm_budget_month_usd,
                   llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models
            FROM api_keys WHERE id = $1
            """,
            key_id,
        )
        return row[0] if row else None
    else:
        row = await pool.fetchone(
            """
            SELECT id,
                   COALESCE(is_virtual,0) AS is_virtual,
                   org_id, team_id,
                   llm_budget_day_tokens, llm_budget_month_tokens,
                   llm_budget_day_usd, llm_budget_month_usd,
                   llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models
            FROM api_keys WHERE id = ?
            """,
            key_id,
        )
        return row


async def summarize_usage_for_key_day(key_id: int, day_iso: Optional[str] = None) -> Dict[str, Any]:
    # Use a proper date for Postgres; SQLite path will use ISO string
    """
    Summarizes total tokens and USD cost for a given API key on a specific UTC day.

    Parameters:
        day_iso (Optional[str|datetime.date]): ISO date string (YYYY-MM-DD) or a date object specifying the UTC day to summarize. If omitted, the current UTC date is used.

    Returns:
        dict: A dictionary with keys:
            - "tokens" (int): Total tokens consumed on the specified day.
            - "usd" (float): Total USD cost incurred on the specified day.
    """
    day_val = day_iso if day_iso is not None else _utc_today()
    pool = await get_db_pool()
    if pool.pool:
        # Ensure we pass a datetime.date to asyncpg for date() comparisons
        _day_param = day_val if isinstance(day_val, date) else date.fromisoformat(str(day_val))
        total_tokens = await pool.fetchval(
            "SELECT COALESCE(SUM(total_tokens),0) FROM llm_usage_log WHERE date(ts AT TIME ZONE 'UTC') = $1 AND key_id = $2",
            _day_param, key_id,
        )
        total_cost = await pool.fetchval(
            "SELECT COALESCE(SUM(total_cost_usd),0) FROM llm_usage_log WHERE date(ts AT TIME ZONE 'UTC') = $1 AND key_id = $2",
            _day_param, key_id,
        )
    else:
        # SQLite: compare DATE(ts) to an ISO date string.
        # Normalize potential ISO 'T' separator to a space so both
        # 'YYYY-MM-DD HH:MM:SS' and 'YYYY-MM-DDTHH:MM:SS' forms match.
        _day_str = day_val.isoformat() if isinstance(day_val, date) else str(day_val)
        total_tokens = await pool.fetchval(
            """
            SELECT COALESCE(SUM(total_tokens),0)
            FROM llm_usage_log
            WHERE DATE(datetime(ts)) = ? AND key_id = ?
            """,
            _day_str, key_id,
        )
        total_cost = await pool.fetchval(
            """
            SELECT COALESCE(SUM(total_cost_usd),0)
            FROM llm_usage_log
            WHERE DATE(datetime(ts)) = ? AND key_id = ?
            """,
            _day_str, key_id,
        )
    result = {"tokens": int(total_tokens or 0), "usd": float(total_cost or 0.0)}
    try:
        import os
        if os.getenv("BUDGET_MW_DEBUG", "").lower() in {"1","true","yes","on"} or os.getenv("PYTEST_CURRENT_TEST") is not None:
            logger.debug(f"VK summarize day: key_id={key_id} day={day_val} -> {result}")
            print(f"[BUDGET_DEBUG] day-summary key={key_id} day={day_val} -> {result}")
    except Exception:
        pass
    return result


async def summarize_usage_for_key_month(key_id: int) -> Dict[str, Any]:
    # Use a rolling 30-day window to avoid calendar-boundary flakiness
    """
    Summarizes token and USD usage for a key over a rolling 30-day UTC window.

    Returns:
        dict: A mapping with keys `"tokens"` and `"usd"`. `"tokens"` is the total tokens consumed (int) and `"usd"` is the total cost in USD (float); both are 0 when no usage records are found.
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    start_dt = (now - timedelta(days=30)).replace(microsecond=0)
    end_dt = now.replace(microsecond=0)
    pool = await get_db_pool()
    if pool.pool:
        # Provide real datetimes to asyncpg
        _start_dt = start_dt
        _end_dt = end_dt
        # Postgres TIMESTAMP columns compare with naive datetimes; strip tzinfo if present
        if _start_dt.tzinfo is not None:
            _start_dt = _start_dt.replace(tzinfo=None)
        if _end_dt.tzinfo is not None:
            _end_dt = _end_dt.replace(tzinfo=None)
        totals = await pool.fetchone(
            """
            SELECT COALESCE(SUM(total_tokens),0) AS tokens,
                   COALESCE(SUM(total_cost_usd),0.0) AS usd
            FROM llm_usage_log
            WHERE ts >= $1 AND ts < $2 AND key_id = $3
            """,
            _start_dt, _end_dt, key_id,
        )
    else:
        # SQLite: rows may contain timestamps in either 'YYYY-MM-DD HH:MM:SS'
        # or ISO 'YYYY-MM-DDTHH:MM:SS' form. Normalize with REPLACE for
        # robust string comparisons across both representations.
        def _sqlite_fmt(iso: str) -> str:
            """
            Format an ISO datetime string or datetime object into a SQLite-compatible naive UTC timestamp.

            Parameters:
                iso (str | datetime): An ISO-formatted datetime string or a datetime instance. If a string is provided it is parsed with datetime.fromisoformat.

            Returns:
                str: Timestamp in "YYYY-MM-DD HH:MM:SS" format representing the equivalent instant in UTC with no timezone information.
            """
            dt = iso if isinstance(iso, datetime) else datetime.fromisoformat(iso)
            # Ensure UTC and naive for lexical comparison
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        start_str = _sqlite_fmt(start_dt)
        end_str = _sqlite_fmt(end_dt)
        totals = await pool.fetchone(
            """
            SELECT COALESCE(SUM(total_tokens),0) AS tokens,
                   COALESCE(SUM(total_cost_usd),0.0) AS usd
            FROM llm_usage_log
            WHERE datetime(ts) >= ? AND datetime(ts) < ? AND key_id = ?
            """,
            start_str, end_str, key_id,
        )
    out = {"tokens": int(totals["tokens"] if totals and isinstance(totals, dict) else 0), "usd": float(totals["usd"] if totals and isinstance(totals, dict) else 0.0)}
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
