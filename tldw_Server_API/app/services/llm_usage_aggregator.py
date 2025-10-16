from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


async def aggregate_llm_usage_daily(db_pool: Optional[DatabasePool] = None, day: Optional[str] = None) -> None:
    """
    Aggregate llm_usage_log into llm_usage_daily for a given UTC day.

    Args:
        db_pool: Optional database pool; if None, fetch singleton
        day: Optional ISO date string (YYYY-MM-DD). Defaults to current UTC date.
    """
    try:
        pool = db_pool or await get_db_pool()
        day_str = day or datetime.now(timezone.utc).date().isoformat()

        if pool.pool:
            # PostgreSQL
            query = (
                """
                INSERT INTO llm_usage_daily (
                    day, user_id, operation, provider, model,
                    requests, errors, input_tokens, output_tokens, total_tokens, total_cost_usd, latency_avg_ms
                )
                SELECT
                    $1::date as day,
                    user_id as user_id,
                    COALESCE(operation,'') as operation,
                    COALESCE(provider,'') as provider,
                    COALESCE(model,'') as model,
                    COUNT(*) as requests,
                    SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors,
                    COALESCE(SUM(COALESCE(prompt_tokens,0)),0) as input_tokens,
                    COALESCE(SUM(COALESCE(completion_tokens,0)),0) as output_tokens,
                    COALESCE(SUM(COALESCE(total_tokens,0)),0) as total_tokens,
                    COALESCE(SUM(COALESCE(total_cost_usd,0)),0) as total_cost_usd,
                    AVG(latency_ms)::float as latency_avg_ms
                FROM llm_usage_log
                WHERE user_id IS NOT NULL AND date(ts AT TIME ZONE 'UTC') = $1::date
                GROUP BY user_id, COALESCE(operation,''), COALESCE(provider,''), COALESCE(model,'')
                ON CONFLICT (day, user_id, operation, provider, model) DO UPDATE SET
                    requests = EXCLUDED.requests,
                    errors = EXCLUDED.errors,
                    input_tokens = EXCLUDED.input_tokens,
                    output_tokens = EXCLUDED.output_tokens,
                    total_tokens = EXCLUDED.total_tokens,
                    total_cost_usd = EXCLUDED.total_cost_usd,
                    latency_avg_ms = EXCLUDED.latency_avg_ms
                """
            )
            await pool.execute(query, day_str)
        else:
            # SQLite
            query = (
                """
                INSERT OR REPLACE INTO llm_usage_daily (
                    day, user_id, operation, provider, model,
                    requests, errors, input_tokens, output_tokens, total_tokens, total_cost_usd, latency_avg_ms
                )
                SELECT
                    ? as day,
                    user_id as user_id,
                    IFNULL(operation,'') as operation,
                    IFNULL(provider,'') as provider,
                    IFNULL(model,'') as model,
                    COUNT(*) as requests,
                    SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors,
                    IFNULL(SUM(IFNULL(prompt_tokens,0)),0) as input_tokens,
                    IFNULL(SUM(IFNULL(completion_tokens,0)),0) as output_tokens,
                    IFNULL(SUM(IFNULL(total_tokens,0)),0) as total_tokens,
                    IFNULL(SUM(IFNULL(total_cost_usd,0)),0) as total_cost_usd,
                    AVG(latency_ms) as latency_avg_ms
                FROM llm_usage_log
                WHERE user_id IS NOT NULL AND DATE(ts) = ?
                GROUP BY user_id, IFNULL(operation,''), IFNULL(provider,''), IFNULL(model,'')
                """
            )
            await pool.execute(query, day_str, day_str)

        logger.debug(f"llm_usage_daily aggregated for {day_str}")
    except Exception as e:
        logger.debug(f"llm_usage_daily aggregation skipped/failed: {e}")


async def _aggregator_loop(stop_event: asyncio.Event):
    settings = get_settings()
    if not getattr(settings, "LLM_USAGE_AGGREGATOR_ENABLED", True):
        logger.info("LLM usage aggregator disabled (LLM_USAGE_AGGREGATOR_ENABLED is false)")
        return
    interval_minutes = int(getattr(settings, "LLM_USAGE_AGGREGATOR_INTERVAL_MINUTES", 60) or 60)
    logger.info(f"Starting LLM usage aggregator task (interval: {interval_minutes} min)")
    try:
        while not stop_event.is_set():
            await aggregate_llm_usage_daily()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_minutes * 60)
            except asyncio.TimeoutError:
                continue
    except Exception as e:
        logger.warning(f"LLM usage aggregator loop exited: {e}")


async def start_llm_usage_aggregator() -> Optional[asyncio.Task]:
    """Start background LLM aggregator if enabled; return task or None."""
    settings = get_settings()
    if not getattr(settings, "LLM_USAGE_AGGREGATOR_ENABLED", True):
        return None
    stop_event = asyncio.Event()
    task = asyncio.create_task(_aggregator_loop(stop_event))
    task._tldw_stop_event = stop_event  # type: ignore[attr-defined]
    return task


async def stop_llm_usage_aggregator(task: Optional[asyncio.Task]) -> None:
    if not task:
        return
    try:
        stop_event = getattr(task, "_tldw_stop_event", None)
        if isinstance(stop_event, asyncio.Event):
            stop_event.set()
        task.cancel()
    except Exception:
        pass
