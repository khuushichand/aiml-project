from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool


async def aggregate_usage_daily(db_pool: Optional[DatabasePool] = None, day: Optional[str] = None) -> None:
    """
    Aggregate per-request usage from usage_log into usage_daily.

    Args:
        db_pool: Optional DatabasePool; if None, fetch singleton
        day: Optional ISO date (YYYY-MM-DD). If None, uses current UTC date.
    """
    try:
        pool = db_pool or await get_db_pool()
        # Resolve day (UTC)
        day_str = day or datetime.now(timezone.utc).date().isoformat()

        # Upsert aggregates per user for given day
        if pool.pool:
            # PostgreSQL: use date(ts) for grouping
            query = (
                """
                INSERT INTO usage_daily (user_id, day, requests, errors, bytes_total, latency_avg_ms)
                SELECT
                    COALESCE(user_id, 0) as user_id,
                    $1::date as day,
                    COUNT(*) as requests,
                    SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors,
                    COALESCE(SUM(COALESCE(bytes, 0)), 0) as bytes_total,
                    AVG(latency_ms)::float as latency_avg_ms
                FROM usage_log
                WHERE date(ts AT TIME ZONE 'UTC') = $1::date
                GROUP BY COALESCE(user_id, 0)
                ON CONFLICT (user_id, day) DO UPDATE SET
                    requests = EXCLUDED.requests,
                    errors = EXCLUDED.errors,
                    bytes_total = EXCLUDED.bytes_total,
                    latency_avg_ms = EXCLUDED.latency_avg_ms
                """
            )
            await pool.execute(query, day_str)
        else:
            # SQLite: use DATE(ts) for grouping
            query = (
                """
                INSERT OR REPLACE INTO usage_daily (user_id, day, requests, errors, bytes_total, latency_avg_ms)
                SELECT
                    IFNULL(user_id, 0) as user_id,
                    ? as day,
                    COUNT(*) as requests,
                    SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors,
                    IFNULL(SUM(IFNULL(bytes, 0)), 0) as bytes_total,
                    AVG(latency_ms) as latency_avg_ms
                FROM usage_log
                WHERE DATE(ts) = ?
                GROUP BY IFNULL(user_id, 0)
                """
            )
            await pool.execute(query, day_str, day_str)

        logger.debug(f"usage_daily aggregated for {day_str}")
    except Exception as e:
        logger.debug(f"usage_daily aggregation skipped/failed: {e}")


async def _aggregator_loop(stop_event: asyncio.Event):
    settings = get_settings()
    if not getattr(settings, "USAGE_LOG_ENABLED", False):
        logger.info("Usage aggregator disabled (USAGE_LOG_ENABLED is false)")
        return
    interval_minutes = 60  # simple default interval
    logger.info("Starting usage aggregator task (interval: %s min)", interval_minutes)
    try:
        while not stop_event.is_set():
            await aggregate_usage_daily()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_minutes * 60)
            except asyncio.TimeoutError:
                continue
    except Exception as e:
        logger.warning(f"Usage aggregator loop exited: {e}")


async def start_usage_aggregator() -> Optional[asyncio.Task]:
    """Start background aggregator if enabled; return task or None."""
    settings = get_settings()
    if not getattr(settings, "USAGE_LOG_ENABLED", False):
        return None
    stop_event = asyncio.Event()
    task = asyncio.create_task(_aggregator_loop(stop_event))
    # Attach a helper to task for stopping
    task._tldw_stop_event = stop_event  # type: ignore[attr-defined]
    return task


async def stop_usage_aggregator(task: Optional[asyncio.Task]) -> None:
    if not task:
        return
    try:
        stop_event = getattr(task, "_tldw_stop_event", None)
        if isinstance(stop_event, asyncio.Event):
            stop_event.set()
        task.cancel()
    except Exception:
        pass

