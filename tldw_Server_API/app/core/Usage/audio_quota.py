"""
Audio usage quotas and tracking.

Provides per-user tiered limits for:
- daily transcription minutes
- concurrent streaming connections
- concurrent audio jobs (batch pipeline)
- per-request max file size

Backed by the AuthNZ database via DatabasePool for durable daily minute tracking.
In-process maps are used for concurrency caps (MVP, single-process safety).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from typing import Dict, Optional, Tuple
from functools import lru_cache

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


@lru_cache(maxsize=1)
def _get_stream_ttl_seconds() -> int:
    """
    Determine the TTL (in seconds) to use for Redis stream counters.

    Checks for a value in this order: the AUDIO_STREAM_TTL_SECONDS environment variable, the
    Audio-Quota stream_ttl_seconds config setting, then a hard default of 120. The resulting
    value is clamped to the inclusive range 30-3600.

    Returns:
        int: TTL in seconds (clamped to 30-3600).
    """
    # 1) Environment variable override
    val_env = os.getenv("AUDIO_STREAM_TTL_SECONDS")
    if val_env:
        try:
            v = int(val_env)
            return max(30, min(3600, v))
        except Exception:
            pass
    # 2) Config default
    try:
        from tldw_Server_API.app.core.config import load_comprehensive_config  # lazy import
        cfg = load_comprehensive_config()
        if cfg and cfg.has_section('Audio-Quota'):
            try:
                v = int(cfg.get('Audio-Quota', 'stream_ttl_seconds', fallback='120'))
            except Exception:
                v = 120
            return max(30, min(3600, v))
    except Exception:
        pass
    # 3) Hard default
    return 120


def clear_stream_ttl_cache() -> None:
    """Clear the cached TTL value so subsequent calls re-read configuration.

    Use this after reloading application configuration or changing
    AUDIO_STREAM_TTL_SECONDS at runtime.
    """
    try:
        _get_stream_ttl_seconds.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        # If decoration is missing for any reason, ignore
        pass


def _use_redis() -> bool:
    """
    Determine whether Redis should be used for audio quota operations.

    Checks whether the redis_async package is available, a Redis URL is configured in settings, and the AUDIO_QUOTA_USE_REDIS environment flag does not disable Redis.

    Returns:
        bool: `True` if Redis is available and enabled by configuration and environment, `False` otherwise.
    """
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
    """
    Register and update a gauge metric under both underscore and dot-name variants and set its value with provided labels.

    Attempts to register and set the gauge for the canonical metric name (underscores) and a backward-compatible alias (dots). Any errors during registration or setting are suppressed so the call never raises. `labels` must map label names to their string values; `value` is converted to float before setting.
    """
    try:
        if not get_metrics_registry or not MetricDefinition or not MetricType:
            return
        reg = get_metrics_registry()
        # Canonical metric name: underscores
        canonical = name
        # Backward-compat alias with dots
        alias = name.replace('_', '.') if '_' in name else name
        for metric_name in (canonical, alias):
            try:
                reg.register_metric(
                    MetricDefinition(
                        name=metric_name,
                        type=MetricType.GAUGE,
                        description=metric_name,
                        labels=list(labels.keys()),
                    )
                )
            except Exception:
                pass
            reg.set_gauge(metric_name, float(value), labels)
    except Exception:
        pass


def _metrics_increment(name: str, labels: Dict[str, str]) -> None:
    """
    Increment a counter metric in the metrics registry for a given metric name and label set.

    Attempts to register and increment two metric name variants: the provided name and a dot-separated alias (underscores replaced with dots). If a metrics registry is unavailable or any error occurs, the function does nothing and does not raise.

    Parameters:
        name (str): Base metric name to increment (e.g., "audio_jobs_active").
        labels (Dict[str, str]): Mapping of label names to values to attach to the metric.
    """
    try:
        if not get_metrics_registry or not MetricDefinition or not MetricType:
            return
        reg = get_metrics_registry()
        canonical = name
        alias = name.replace('_', '.') if '_' in name else name
        for metric_name in (canonical, alias):
            try:
                reg.register_metric(
                    MetricDefinition(
                        name=metric_name,
                        type=MetricType.COUNTER,
                        description=metric_name,
                        labels=list(labels.keys()),
                    )
                )
            except Exception:
                pass
            reg.increment(metric_name, 1, labels)
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
    """
    Determine whether a new concurrent audio job may be started for the given user and, if allowed, increment the active-job counter.

    If a concurrency limit exists for the user's tier the function enforces it using Redis when available (falling back to an in-process counter). It also emits quota and active-job metrics. When the limit is exceeded the function does not increment the counter and reports a descriptive message.

    Returns:
        (bool, str): `True` and `"OK"` if the job may start and the active-job counter was incremented; `False` and an explanatory message like `"Concurrent job limit reached (<max>)"` if starting the job would exceed the user's concurrency limit.
    """
    limits = await get_limits_for_user(user_id)
    max_jobs = int(limits.get("concurrent_jobs") or 0)
    r = await _get_redis()
    if r and max_jobs:
        key = f"audio:active_jobs:{int(user_id)}"
        try:
            new_val = await r.incr(key)
            if new_val > max_jobs:
                await r.decr(key)
                _metrics_increment("audio_quota_violations_total", {"type": "concurrent_jobs"})
                return False, f"Concurrent job limit reached ({max_jobs})"
            _metrics_set_gauge("audio_jobs_active", float(new_val), {"user_id": str(int(user_id))})
            return True, "OK"
        except Exception as e:
            logger.debug(f"Redis error in can_start_job: {e}")
    async with _lock:
        active = _active_jobs.get(user_id, 0)
        if max_jobs and active >= max_jobs:
            _metrics_increment("audio_quota_violations_total", {"type": "concurrent_jobs"})
            return False, f"Concurrent job limit reached ({max_jobs})"
        new_val = active + 1
        _active_jobs[user_id] = new_val
        _metrics_set_gauge("audio_jobs_active", float(new_val), {"user_id": str(int(user_id))})
        return True, "OK"


async def finish_job(user_id: int) -> None:
    """
    Decrement the user's active audio job counter and update metrics.

    If a Redis client is available, decrement the per-user Redis counter and clamp it to zero; otherwise decrement the in-process counter protected by the module lock. Updates the `audio_jobs_active` gauge with the new value.

    Parameters:
        user_id (int): Numeric identifier of the user whose active-job count should be decremented.
    """
    r = await _get_redis()
    if r:
        try:
            key = f"audio:active_jobs:{int(user_id)}"
            new_val = await r.decr(key)
            if new_val < 0:
                await r.set(key, 0)
                new_val = 0
            _metrics_set_gauge("audio_jobs_active", float(new_val), {"user_id": str(int(user_id))})
            return
        except Exception as e:
            logger.debug(f"Redis error in finish_job: {e}")
    async with _lock:
        cur = _active_jobs.get(user_id, 0)
        new_val = max(0, cur - 1)
        _active_jobs[user_id] = new_val
        _metrics_set_gauge("audio_jobs_active", float(new_val), {"user_id": str(int(user_id))})


async def can_start_stream(user_id: int) -> Tuple[bool, str]:
    """
    Determines whether the user may start a new concurrent audio stream and reserves a slot if allowed.

    Attempts to allocate a concurrent-stream slot for the given user; if a slot is available the function records the reservation and returns success, otherwise it reports the denial reason.

    Returns:
        (bool, str): `True` and `"OK"` if a slot was reserved and the stream may start, `False` and a human-readable reason (e.g., "Concurrent streams limit reached (<n>)") otherwise.
    """
    limits = await get_limits_for_user(user_id)
    max_streams = int(limits.get("concurrent_streams") or 0)
    r = await _get_redis()
    if r and max_streams:
        key = f"audio:active_streams:{int(user_id)}"
        try:
            new_val = await r.incr(key)
            # Set/refresh TTL to mitigate leaks
            try:
                await r.expire(key, _get_stream_ttl_seconds())
            except Exception:
                pass
            if new_val > max_streams:
                await r.decr(key)
                _metrics_increment("audio_quota_violations_total", {"type": "concurrent_streams"})
                return False, f"Concurrent streams limit reached ({max_streams})"
            _metrics_set_gauge("audio_streaming_active", float(new_val), {"user_id": str(int(user_id))})
            return True, "OK"
        except Exception as e:
            logger.debug(f"Redis error in can_start_stream: {e}")
    async with _lock:
        active = _active_streams.get(user_id, 0)
        if max_streams and active >= max_streams:
            _metrics_increment("audio_quota_violations_total", {"type": "concurrent_streams"})
            return False, f"Concurrent streams limit reached ({max_streams})"
        new_val = active + 1
        _active_streams[user_id] = new_val
        _metrics_set_gauge("audio_streaming_active", float(new_val), {"user_id": str(int(user_id))})
        return True, "OK"


async def finish_stream(user_id: int) -> None:
    """
    Decrement the user's active audio stream count and update the corresponding metric.

    If a Redis client is available, the Redis counter for the user is decremented and clamped to zero; otherwise an in-process counter protected by an async lock is decremented and clamped to zero. Always emits the updated `audio_streaming_active` gauge with the user's id as a label.
    """
    r = await _get_redis()
    if r:
        try:
            key = f"audio:active_streams:{int(user_id)}"
            new_val = await r.decr(key)
            if new_val < 0:
                await r.set(key, 0)
                new_val = 0
            _metrics_set_gauge("audio_streaming_active", float(new_val), {"user_id": str(int(user_id))})
            return
        except Exception as e:
            logger.debug(f"Redis error in finish_stream: {e}")
    async with _lock:
        cur = _active_streams.get(user_id, 0)
        new_val = max(0, cur - 1)
        _active_streams[user_id] = new_val
        _metrics_set_gauge("audio_streaming_active", float(new_val), {"user_id": str(int(user_id))})


async def check_daily_minutes_allow(user_id: int, minutes_requested: float) -> Tuple[bool, Optional[float]]:
    """
    Check whether the requested daily transcription minutes can be consumed and report the remaining minutes.

    Parameters:
        user_id (int): ID of the user whose quota is being checked.
        minutes_requested (float): Minutes requested to consume from today's quota.

    Returns:
        Tuple[bool, Optional[float]]:
            allowed: `True` if the requested minutes can be consumed, `False` otherwise.
            remaining_after: Remaining minutes for the current UTC day after the request, or `None` if the user's daily limit is unlimited.

    Notes:
        When the request is denied due to insufficient remaining minutes, a quota violation metric is recorded.
    """
    limits = await get_limits_for_user(user_id)
    limit = limits.get("daily_minutes")
    if limit is None:
        return True, None
    used = await get_daily_minutes_used(user_id)
    remaining = float(limit) - float(used)
    if minutes_requested > remaining:
        _metrics_increment("audio_quota_violations_total", {"type": "daily_minutes"})
        return False, max(0.0, remaining)
    return True, remaining - minutes_requested


def bytes_to_seconds(byte_count: int, sample_rate: int) -> float:
    # Float32 mono: 4 bytes per sample
    """
    Convert a byte count of Float32 mono audio into playback duration in seconds.

    Treats audio as mono Float32 (4 bytes per sample). Negative byte counts are treated as zero. If `sample_rate` is zero or otherwise falsy, a default sample rate of 16000 Hz is used.

    Parameters:
        byte_count (int): Number of bytes of audio data.
        sample_rate (int): Samples per second for the audio; if falsy, 16000 is used.

    Returns:
        float: Duration in seconds represented by the given byte count.
    """
    samples = max(0, int(byte_count // 4))
    return float(samples) / float(sample_rate or 16000)


async def heartbeat_stream(user_id: int) -> None:
    """
    Refresh the TTL for a user's active audio stream counter to prevent stale/ leaked keys.

    If Redis is unavailable this is a no-op; does nothing for in-process counters.
    """
    r = await _get_redis()
    if not r:
        return
    try:
        key = f"audio:active_streams:{int(user_id)}"
        # Only refresh if key exists
        exists = await r.exists(key)
        if exists:
            await r.expire(key, _get_stream_ttl_seconds())
    except Exception as e:
        logger.debug(f"Redis heartbeat_stream failed: {e}")


async def active_streams_count(user_id: int) -> int:
    """
    Get the number of currently active audio streams for a user.

    When Redis is available, reads the user's Redis counter key; otherwise returns the in-process counter. If the Redis value is missing or cannot be parsed as an integer, returns 0.

    Returns:
        int: Active stream count for the user.
    """
    r = await _get_redis()
    if r:
        try:
            key = f"audio:active_streams:{int(user_id)}"
            val = await r.get(key)
            if val is None:
                return 0
            try:
                return int(val)
            except Exception:
                return 0
        except Exception as e:
            logger.debug(f"Redis active_streams_count failed: {e}")
    return int(_active_streams.get(int(user_id), 0))


def _apply_tier_overrides_from_config(base: Dict[str, Dict[str, Optional[float]]]) -> Dict[str, Dict[str, Optional[float]]]:
    """
    Merge a base per-tier limits mapping with overrides from the environment and configuration.

    Checks the AUDIO_TIER_LIMITS_JSON environment variable (JSON object mapping tier names to partial
    limit objects) first, then the application's [Audio-Quota] config section. Keys recognized per tier
    are: `daily_minutes`, `concurrent_streams`, `concurrent_jobs`, and `max_file_size_mb`. Only tiers
    present in the base mapping are updated; other entries in the environment JSON are ignored.

    Environment JSON takes precedence over config file values. For `daily_minutes`, the string values
    "none", "unlimited", or "-1" in the config are treated as `None` (unlimited).

    Parameters:
        base (Dict[str, Dict[str, Optional[float]]]): Original tier limits mapping to copy and merge into.

    Returns:
        Dict[str, Dict[str, Optional[float]]]: A new mapping with overrides applied.
    """
    merged = {k: v.copy() for k, v in base.items()}
    # Env JSON has priority
    import json as _json
    try:
        j = os.getenv("AUDIO_TIER_LIMITS_JSON")
        if j:
            data = _json.loads(j)
            if isinstance(data, dict):
                for tier, vals in data.items():
                    if tier in merged and isinstance(vals, dict):
                        merged[tier].update(vals)
    except Exception as e:
        logger.debug(f"AUDIO_TIER_LIMITS_JSON parse failed: {e}")
    # Config file overrides
    try:
        from tldw_Server_API.app.core.config import load_comprehensive_config
        cfg = load_comprehensive_config()
        if cfg and cfg.has_section('Audio-Quota'):
            for tier in ("free", "standard", "premium"):
                for key in ("daily_minutes", "concurrent_streams", "concurrent_jobs", "max_file_size_mb"):
                    opt = f"{tier}_{key}"
                    if cfg.has_option('Audio-Quota', opt):
                        val = cfg.get('Audio-Quota', opt)
                        # Coerce None for 'unlimited'
                        if str(val).strip().lower() in {"none", "unlimited", "-1"} and key == "daily_minutes":
                            merged[tier][key] = None
                        else:
                            try:
                                merged[tier][key] = float(val) if key == "daily_minutes" else int(val)
                            except Exception:
                                pass
    except Exception as e:
        logger.debug(f"Audio-Quota config overrides failed: {e}")
    return merged


# Apply overrides on import
TIER_LIMITS = _apply_tier_overrides_from_config(TIER_LIMITS)
