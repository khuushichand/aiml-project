"""
Audio usage quotas and tracking.

Provides per-user tiered limits for:
- daily transcription minutes
- concurrent streaming connections
- concurrent audio jobs (batch pipeline)
- per-request max file size

Backed by the AuthNZ database via DatabasePool for durable daily minute tracking.
In‑process maps are used for concurrency caps (MVP, single-process safety).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from typing import Dict, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool
from tldw_Server_API.app.core.AuthNZ.settings import get_settings

try:
    from redis import asyncio as redis_async  # type: ignore
except Exception:  # pragma: no cover
    redis_async = None  # type: ignore

try:
    from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry, MetricDefinition, MetricType
except Exception:  # pragma: no cover
    get_metrics_registry = None  # type: ignore
    MetricDefinition = None  # type: ignore
    MetricType = None  # type: ignore


# Default tier limits (can be extended later via configuration or DB)
TIER_LIMITS = {
    "free": {
        "daily_minutes": 30.0,
        "concurrent_streams": 1,
        "concurrent_jobs": 1,
        "max_file_size_mb": 25,
    },
    "standard": {
        "daily_minutes": 300.0,
        "concurrent_streams": 3,
        "concurrent_jobs": 3,
        "max_file_size_mb": 100,
    },
    "premium": {
        "daily_minutes": None,  # unlimited
        "concurrent_streams": 10,
        "concurrent_jobs": 10,
        "max_file_size_mb": 500,
    },
}


_active_streams: Dict[int, int] = {}
_active_jobs: Dict[int, int] = {}
_lock = asyncio.Lock()

_redis_client = None


def _use_redis() -> bool:
    if not redis_async:
        return False
    try:
        s = get_settings()
        if not getattr(s, "REDIS_URL", None):
            return False
        if os.getenv("AUDIO_QUOTA_USE_REDIS", "true").lower() in {"0", "false", "no", "off"}:
            return False
        return True
    except Exception:
        return False


async def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not _use_redis():
        return None
    try:
        s = get_settings()
        _redis_client = redis_async.from_url(s.REDIS_URL)  # type: ignore[attr-defined]
        await _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable for audio quotas: {e}")
        _redis_client = None
        return None


def _metrics_set_gauge(name: str, value: float, labels: Dict[str, str]) -> None:
    try:
        if not get_metrics_registry or not MetricDefinition or not MetricType:
            return
        reg = get_metrics_registry()
        try:
            reg.register_metric(MetricDefinition(name=name, type=MetricType.GAUGE, description=name, labels=list(labels.keys())))
        except Exception:
            pass
        reg.set_gauge(name, float(value), labels)
    except Exception:
        pass


def _metrics_increment(name: str, labels: Dict[str, str]) -> None:
    try:
        if not get_metrics_registry or not MetricDefinition or not MetricType:
            return
        reg = get_metrics_registry()
        try:
            reg.register_metric(MetricDefinition(name=name, type=MetricType.COUNTER, description=name, labels=list(labels.keys())))
        except Exception:
            pass
        reg.increment(name, 1, labels)
    except Exception:
        pass


async def _ensure_tables(pool: DatabasePool) -> None:
    """Ensure audio usage tables exist."""
    try:
        # Create tables separately to satisfy SQLite single-statement execution
        if pool.pool:
            await pool.execute(
                """
                CREATE TABLE IF NOT EXISTS audio_usage_daily (
                    user_id INTEGER NOT NULL,
                    day DATE NOT NULL,
                    minutes_used DOUBLE PRECISION NOT NULL DEFAULT 0,
                    jobs_started INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, day)
                )
                """
            )
            await pool.execute(
                """
                CREATE TABLE IF NOT EXISTS audio_user_tiers (
                    user_id INTEGER PRIMARY KEY,
                    tier TEXT NOT NULL
                )
                """
            )
        else:
            await pool.execute(
                """
                CREATE TABLE IF NOT EXISTS audio_usage_daily (
                    user_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    minutes_used REAL NOT NULL DEFAULT 0,
                    jobs_started INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, day)
                )
                """
            )
            await pool.execute(
                """
                CREATE TABLE IF NOT EXISTS audio_user_tiers (
                    user_id INTEGER PRIMARY KEY,
                    tier TEXT NOT NULL
                )
                """
            )
    except Exception as e:
        logger.debug(f"audio_usage_daily ensure failed: {e}")


async def get_user_tier(user_id: int) -> str:
    """Return user tier string from DB if set, else 'free'."""
    try:
        pool = await get_db_pool()
        await _ensure_tables(pool)
        # Use portable fetchone helper (supports both backends)
        row = await pool.fetchone("SELECT tier FROM audio_user_tiers WHERE user_id = ?", int(user_id))
        if row and row.get("tier"):
            return str(row["tier"]).strip()
        return "free"
    except Exception as e:
        logger.debug(f"get_user_tier failed: {e}")
        return "free"


async def get_limits_for_user(user_id: int) -> Dict[str, Optional[float]]:
    tier = await get_user_tier(user_id)
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"]).copy()


async def get_daily_minutes_used(user_id: int) -> float:
    pool = await get_db_pool()
    await _ensure_tables(pool)
    day = datetime.now(timezone.utc).date().isoformat()
    try:
        if pool.pool:
            row = await pool.fetchrow(
                "SELECT minutes_used FROM audio_usage_daily WHERE user_id=$1 AND day=$2",
                user_id,
                day,
            )
            return float(row["minutes_used"]) if row else 0.0
        else:
            rows = await pool.fetch(
                "SELECT minutes_used FROM audio_usage_daily WHERE user_id=? AND day=?",
                user_id,
                day,
            )
            return float(rows[0][0]) if rows else 0.0
    except Exception as e:
        logger.debug(f"get_daily_minutes_used failed: {e}")
        return 0.0


async def add_daily_minutes(user_id: int, minutes: float) -> None:
    if minutes <= 0:
        return
    pool = await get_db_pool()
    await _ensure_tables(pool)
    day = datetime.now(timezone.utc).date().isoformat()
    try:
        if pool.pool:
            await pool.execute(
                """
                INSERT INTO audio_usage_daily (user_id, day, minutes_used, jobs_started)
                VALUES ($1, $2, $3, 0)
                ON CONFLICT (user_id, day) DO UPDATE SET minutes_used = audio_usage_daily.minutes_used + EXCLUDED.minutes_used
                """,
                user_id,
                day,
                float(minutes),
            )
        else:
            await pool.execute(
                """
                INSERT INTO audio_usage_daily (user_id, day, minutes_used, jobs_started)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(user_id, day) DO UPDATE SET minutes_used = minutes_used + excluded.minutes_used
                """,
                user_id,
                day,
                float(minutes),
            )
    except Exception as e:
        logger.debug(f"add_daily_minutes failed: {e}")


async def increment_jobs_started(user_id: int) -> None:
    pool = await get_db_pool()
    await _ensure_tables(pool)
    day = datetime.now(timezone.utc).date().isoformat()
    try:
        if pool.pool:
            await pool.execute(
                """
                INSERT INTO audio_usage_daily (user_id, day, minutes_used, jobs_started)
                VALUES ($1, $2, 0, 1)
                ON CONFLICT (user_id, day) DO UPDATE SET jobs_started = audio_usage_daily.jobs_started + 1
                """,
                user_id,
                day,
            )
        else:
            await pool.execute(
                """
                INSERT INTO audio_usage_daily (user_id, day, minutes_used, jobs_started)
                VALUES (?, ?, 0, 1)
                ON CONFLICT(user_id, day) DO UPDATE SET jobs_started = jobs_started + 1
                """,
                user_id,
                day,
            )
    except Exception as e:
        logger.debug(f"increment_jobs_started failed: {e}")


async def can_start_job(user_id: int) -> Tuple[bool, str]:
    limits = await get_limits_for_user(user_id)
    max_jobs = int(limits.get("concurrent_jobs") or 0)
    r = await _get_redis()
    if r and max_jobs:
        key = f"audio:active_jobs:{int(user_id)}"
        try:
            new_val = await r.incr(key)
            if new_val > max_jobs:
                await r.decr(key)
                _metrics_increment("audio.quota_violations_total", {"type": "concurrent_jobs"})
                return False, f"Concurrent job limit reached ({max_jobs})"
            _metrics_set_gauge("audio.jobs.active", float(new_val), {"user_id": str(int(user_id))})
            return True, "OK"
        except Exception as e:
            logger.debug(f"Redis error in can_start_job: {e}")
    async with _lock:
        active = _active_jobs.get(user_id, 0)
        if max_jobs and active >= max_jobs:
            _metrics_increment("audio.quota_violations_total", {"type": "concurrent_jobs"})
            return False, f"Concurrent job limit reached ({max_jobs})"
        new_val = active + 1
        _active_jobs[user_id] = new_val
        _metrics_set_gauge("audio.jobs.active", float(new_val), {"user_id": str(int(user_id))})
        return True, "OK"


async def finish_job(user_id: int) -> None:
    r = await _get_redis()
    if r:
        try:
            key = f"audio:active_jobs:{int(user_id)}"
            new_val = await r.decr(key)
            if new_val < 0:
                await r.set(key, 0)
                new_val = 0
            _metrics_set_gauge("audio.jobs.active", float(new_val), {"user_id": str(int(user_id))})
            return
        except Exception as e:
            logger.debug(f"Redis error in finish_job: {e}")
    async with _lock:
        cur = _active_jobs.get(user_id, 0)
        new_val = max(0, cur - 1)
        _active_jobs[user_id] = new_val
        _metrics_set_gauge("audio.jobs.active", float(new_val), {"user_id": str(int(user_id))})


async def can_start_stream(user_id: int) -> Tuple[bool, str]:
    limits = await get_limits_for_user(user_id)
    max_streams = int(limits.get("concurrent_streams") or 0)
    r = await _get_redis()
    if r and max_streams:
        key = f"audio:active_streams:{int(user_id)}"
        try:
            new_val = await r.incr(key)
            if new_val > max_streams:
                await r.decr(key)
                _metrics_increment("audio.quota_violations_total", {"type": "concurrent_streams"})
                return False, f"Concurrent streams limit reached ({max_streams})"
            _metrics_set_gauge("audio.streaming.active", float(new_val), {"user_id": str(int(user_id))})
            return True, "OK"
        except Exception as e:
            logger.debug(f"Redis error in can_start_stream: {e}")
    async with _lock:
        active = _active_streams.get(user_id, 0)
        if max_streams and active >= max_streams:
            _metrics_increment("audio.quota_violations_total", {"type": "concurrent_streams"})
            return False, f"Concurrent streams limit reached ({max_streams})"
        new_val = active + 1
        _active_streams[user_id] = new_val
        _metrics_set_gauge("audio.streaming.active", float(new_val), {"user_id": str(int(user_id))})
        return True, "OK"


async def finish_stream(user_id: int) -> None:
    r = await _get_redis()
    if r:
        try:
            key = f"audio:active_streams:{int(user_id)}"
            new_val = await r.decr(key)
            if new_val < 0:
                await r.set(key, 0)
                new_val = 0
            _metrics_set_gauge("audio.streaming.active", float(new_val), {"user_id": str(int(user_id))})
            return
        except Exception as e:
            logger.debug(f"Redis error in finish_stream: {e}")
    async with _lock:
        cur = _active_streams.get(user_id, 0)
        new_val = max(0, cur - 1)
        _active_streams[user_id] = new_val
        _metrics_set_gauge("audio.streaming.active", float(new_val), {"user_id": str(int(user_id))})


async def check_daily_minutes_allow(user_id: int, minutes_requested: float) -> Tuple[bool, Optional[float]]:
    """Return (allowed, remaining_after) for daily minutes.

    If limit is unlimited (None), returns (True, None).
    """
    limits = await get_limits_for_user(user_id)
    limit = limits.get("daily_minutes")
    if limit is None:
        return True, None
    used = await get_daily_minutes_used(user_id)
    remaining = float(limit) - float(used)
    if minutes_requested > remaining:
        _metrics_increment("audio.quota_violations_total", {"type": "daily_minutes"})
        return False, max(0.0, remaining)
    return True, remaining - minutes_requested


def bytes_to_seconds(byte_count: int, sample_rate: int) -> float:
    # Float32 mono: 4 bytes per sample
    samples = max(0, int(byte_count // 4))
    return float(samples) / float(sample_rate or 16000)
