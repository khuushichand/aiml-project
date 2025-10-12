from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _month_bounds_utc(dt: Optional[datetime] = None) -> tuple[str, str]:
    now = dt or datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
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
    day = day_iso or _utc_today()
    pool = await get_db_pool()
    if pool.pool:
        total_tokens = await pool.fetchval(
            "SELECT COALESCE(SUM(total_tokens),0) FROM llm_usage_log WHERE date(ts AT TIME ZONE 'UTC') = $1 AND key_id = $2",
            day, key_id,
        )
        total_cost = await pool.fetchval(
            "SELECT COALESCE(SUM(total_cost_usd),0) FROM llm_usage_log WHERE date(ts AT TIME ZONE 'UTC') = $1 AND key_id = $2",
            day, key_id,
        )
    else:
        total_tokens = await pool.fetchval(
            "SELECT COALESCE(SUM(total_tokens),0) FROM llm_usage_log WHERE DATE(ts) = ? AND key_id = ?",
            day, key_id,
        )
        total_cost = await pool.fetchval(
            "SELECT COALESCE(SUM(total_cost_usd),0) FROM llm_usage_log WHERE DATE(ts) = ? AND key_id = ?",
            day, key_id,
        )
    return {"tokens": int(total_tokens or 0), "usd": float(total_cost or 0.0)}


async def summarize_usage_for_key_month(key_id: int) -> Dict[str, Any]:
    start, end = _month_bounds_utc()
    pool = await get_db_pool()
    if pool.pool:
        totals = await pool.fetchone(
            """
            SELECT COALESCE(SUM(total_tokens),0) AS tokens,
                   COALESCE(SUM(total_cost_usd),0.0) AS usd
            FROM llm_usage_log
            WHERE ts >= $1 AND ts < $2 AND key_id = $3
            """,
            start, end, key_id,
        )
    else:
        totals = await pool.fetchone(
            """
            SELECT COALESCE(SUM(total_tokens),0) AS tokens,
                   COALESCE(SUM(total_cost_usd),0.0) AS usd
            FROM llm_usage_log
            WHERE ts >= ? AND ts < ? AND key_id = ?
            """,
            start, end, key_id,
        )
    return {"tokens": int(totals["tokens"] if totals and isinstance(totals, dict) else 0), "usd": float(totals["usd"] if totals and isinstance(totals, dict) else 0.0)}


async def is_key_over_budget(key_id: int) -> Dict[str, Any]:
    """
    Returns dict with keys: over (bool), reasons (list[str]), day and month summaries.
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

    return {"over": len(reasons) > 0, "reasons": reasons, "day": day, "month": month, "limits": limits}
