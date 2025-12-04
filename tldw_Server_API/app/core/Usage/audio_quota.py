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
from typing import Dict, Optional, Tuple, List
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

try:
    # Resource Governor (optional, guarded by RG_ENABLE_AUDIO)
    from tldw_Server_API.app.core.Resource_Governance import (
        RGRequest,
        MemoryResourceGovernor,
        RedisResourceGovernor,
    )
    from tldw_Server_API.app.core.Resource_Governance.policy_loader import (
        PolicyLoader,
        PolicyReloadConfig,
        db_policy_loader,
    )
    from tldw_Server_API.app.core.Resource_Governance.authnz_policy_store import (
        AuthNZPolicyStore,
    )
    from tldw_Server_API.app.core.config import (
        rg_enabled,
        rg_policy_store,
        rg_policy_reload_enabled,
        rg_policy_reload_interval_sec,
        rg_policy_path,
        rg_backend,
    )
except Exception:  # pragma: no cover - RG is optional for audio quotas
    RGRequest = None  # type: ignore
    MemoryResourceGovernor = None  # type: ignore
    RedisResourceGovernor = None  # type: ignore
    PolicyLoader = None  # type: ignore
    PolicyReloadConfig = None  # type: ignore
    db_policy_loader = None  # type: ignore
    AuthNZPolicyStore = None  # type: ignore
    rg_enabled = None  # type: ignore
    rg_policy_store = None  # type: ignore
    rg_policy_reload_enabled = None  # type: ignore
    rg_policy_reload_interval_sec = None  # type: ignore
    rg_policy_path = None  # type: ignore
    rg_backend = None  # type: ignore

try:
    # Generic daily ledger (optional; used in shadow mode)
    from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import (
        ResourceDailyLedger,
        LedgerEntry,
    )
except Exception:  # pragma: no cover
    ResourceDailyLedger = None  # type: ignore
    LedgerEntry = None  # type: ignore


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


def _rg_audio_enabled() -> bool:
    """
    Return True when audio quotas should use the shared Resource Governor for
    streams/jobs concurrency instead of Redis/in-process counters.

    Resolution order:
      1) Explicit module env flag RG_ENABLE_AUDIO=1|true|yes|on
      2) [ResourceGovernor] enable_audio in config.txt (bool)
      3) Global RG_ENABLED flag via config.rg_enabled()

    When all are unset/false or when the governor cannot be initialized,
    legacy behavior remains in effect.
    """
    # 1) Env flag wins
    v = os.getenv("RG_ENABLE_AUDIO")
    if v is not None:
        return v.strip().lower() in {"1", "true", "yes", "on"}
    # 2) Config toggle
    try:
        from tldw_Server_API.app.core.config import load_comprehensive_config  # lazy import

        cfg = load_comprehensive_config()
        if cfg and cfg.has_section("ResourceGovernor") and cfg.has_option("ResourceGovernor", "enable_audio"):
            try:
                return cfg.getboolean("ResourceGovernor", "enable_audio", fallback=False)
            except Exception:
                logger.debug("Failed to parse ResourceGovernor.enable_audio as boolean")
    except Exception as e:
        logger.debug(f"Failed to load config for RG audio check: {e}")
    # 3) Inherit global flag
    if rg_enabled is not None:
        try:
            return bool(rg_enabled(False))  # type: ignore[func-returns-value]
        except Exception:
            return False
    return False


_rg_audio_governor = None
_rg_audio_loader = None
_rg_audio_lock = asyncio.Lock()
_rg_stream_handles: Dict[int, List[str]] = {}
_rg_job_handles: Dict[int, List[str]] = {}
_rg_job_handle_locks: Dict[int, asyncio.Lock] = {}
_rg_job_handle_locks_lock = asyncio.Lock()


def _reset_in_process_counters_for_tests() -> None:
    """
    Reset in-process concurrency tracking state for tests.

    This helper clears the local counters and handle registries used for
    stream and job concurrency so that integration tests can start from a
    clean slate without reaching into module internals such as _active_jobs
    directly. It is not intended for application runtime use.
    """
    _active_streams.clear()
    _active_jobs.clear()
    _rg_stream_handles.clear()
    _rg_job_handles.clear()
    _rg_job_handle_locks.clear()


async def _get_audio_rg_governor():
    """
    Lazily initialize a process-local ResourceGovernor instance for audio
    streams/jobs using the same configuration helpers as app.main.

    On failure, returns None and callers must fall back to legacy counters.
    """
    global _rg_audio_governor, _rg_audio_loader
    if not _rg_audio_enabled():
        return None
    # If RG is not available in this environment, keep legacy behavior.
    if RGRequest is None or PolicyLoader is None or PolicyReloadConfig is None or rg_policy_store is None:
        return None
    if _rg_audio_governor is not None:
        return _rg_audio_governor
    async with _rg_audio_lock:
        if _rg_audio_governor is not None:
            return _rg_audio_governor
        try:
            store_mode = rg_policy_store()  # type: ignore[operator]
        except Exception:
            store_mode = "file"
        try:
            if store_mode == "db" and AuthNZPolicyStore is not None and db_policy_loader is not None:
                store = AuthNZPolicyStore()  # type: ignore[call-arg]
                interval = rg_policy_reload_interval_sec() if rg_policy_reload_interval_sec else 10  # type: ignore[operator]
                loader = db_policy_loader(store, PolicyReloadConfig(enabled=True, interval_sec=interval))  # type: ignore[call-arg]
            else:
                # File-based loader mirroring app.main behavior
                enabled = rg_policy_reload_enabled() if rg_policy_reload_enabled else True  # type: ignore[operator]
                interval = rg_policy_reload_interval_sec() if rg_policy_reload_interval_sec else 10  # type: ignore[operator]
                path = rg_policy_path() if rg_policy_path else "Config_Files/resource_governor_policies.yaml"  # type: ignore[operator]
                loader = PolicyLoader(path, PolicyReloadConfig(enabled=enabled, interval_sec=interval))  # type: ignore[call-arg]
            await loader.load_once()
            _rg_audio_loader = loader
            try:
                backend = rg_backend() if rg_backend else "memory"  # type: ignore[operator]
            except Exception:
                backend = "memory"
            if backend == "redis" and RedisResourceGovernor is not None:
                gov = RedisResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            else:
                gov = MemoryResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            _rg_audio_governor = gov
            return gov
        except Exception as e:
            logger.debug(f"Audio quotas: ResourceGovernor initialization failed; falling back to legacy counters: {e}")
            _rg_audio_governor = None
            _rg_audio_loader = None
            return None


async def _get_job_handle_lock(user_id: int) -> asyncio.Lock:
    """Return (and lazily create) the per-user lock protecting RG job handles."""
    uid = int(user_id)
    async with _rg_job_handle_locks_lock:
        lock = _rg_job_handle_locks.get(uid)
        if lock is None:
            lock = asyncio.Lock()
            _rg_job_handle_locks[uid] = lock
        return lock


async def _cleanup_job_handle_lock(user_id: int) -> None:
    """Remove a per-user job handle lock when no handles remain."""
    uid = int(user_id)
    async with _rg_job_handle_locks_lock:
        # If handles were added after the pop, keep the lock.
        if _rg_job_handles.get(uid):
            return
        lock = _rg_job_handle_locks.get(uid)
        if lock and not lock.locked():
            _rg_job_handle_locks.pop(uid, None)


async def _cleanup_stream_handles(user_id: int) -> None:
    """Prune empty stream handle entries to avoid unbounded growth."""
    uid = int(user_id)
    async with _rg_audio_lock:
        handles = _rg_stream_handles.get(uid)
        if handles:
            return
        _rg_stream_handles.pop(uid, None)


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


_daily_ledger: Optional[ResourceDailyLedger] = None  # type: ignore[assignment]
_daily_ledger_lock = asyncio.Lock()


async def _get_daily_ledger() -> Optional[ResourceDailyLedger]:
    """
    Lazily initialize the shared ResourceDailyLedger for audio minutes.

    This runs in "shadow mode": failures are logged but never affect quota
    enforcement, which continues to rely on audio_usage_daily as the source
    of truth until a future cutover.
    """
    global _daily_ledger
    # If the ledger implementation is not available, skip silently.
    if ResourceDailyLedger is None or LedgerEntry is None:
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
        except Exception as e:  # pragma: no cover - best-effort shadow path
            logger.debug(f"Audio quotas: ResourceDailyLedger init failed; continuing without ledger: {e}")
            _daily_ledger = None
            return None


async def add_daily_minutes(user_id: int, minutes: float) -> None:
    if minutes <= 0:
        return
    day = datetime.now(timezone.utc).date().isoformat()

    # First, record against the shared ResourceDailyLedger so enforcement can
    # rely on the ledger even when legacy counters fail.
    units = int(max(0, round(float(minutes) * 60.0)))
    try:
        ledger = await _get_daily_ledger()
        if ledger is not None and LedgerEntry is not None and units > 0:
            entry = LedgerEntry(  # type: ignore[call-arg]
                entity_scope="user",
                entity_value=str(int(user_id)),
                category="minutes",
                units=units,
                op_id=f"audio-minutes:{int(user_id)}:{day}:{units}",
                occurred_at=datetime.now(timezone.utc),
            )
            try:
                await ledger.add(entry)
            except Exception as le:
                logger.debug(f"Audio quotas: ResourceDailyLedger add failed; shadow-only: {le}")
    except Exception as outer:
        logger.debug(f"Audio quotas: ResourceDailyLedger shadow path failed; ignoring: {outer}")

    # Legacy counter retained for backward compatibility/observability only.
    pool = await get_db_pool()
    await _ensure_tables(pool)
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


async def _ledger_remaining_minutes(user_id: int, daily_limit_minutes: float) -> Optional[float]:
    """
    Compute remaining minutes using the ResourceDailyLedger when available.

    Returns None when the ledger is unavailable; otherwise returns remaining
    minutes (float) based on a per-day cap (converted to seconds internally).
    """
    ledger = await _get_daily_ledger()
    if ledger is None:
        return None
    try:
        cap_units = int(max(0, round(daily_limit_minutes * 60.0)))
        remaining_units = await ledger.remaining_for_day(
            entity_scope="user",
            entity_value=str(int(user_id)),
            category="minutes",
            daily_cap=cap_units,
        )
        return float(remaining_units) / 60.0
    except Exception as e:
        logger.debug(f"Audio quotas: ledger remaining check failed; fallback to legacy: {e}")
        return None


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
    # When RG audio integration is enabled and available, prefer streams/jobs
    # concurrency via the shared governor. Legacy Redis/in-process counters are
    # retained as a fallback when RG cannot be used.
    gov = await _get_audio_rg_governor()
    if gov is not None and RGRequest is not None:
        try:
            user_key = int(user_id)
            entity = f"user:{user_key}"
            policy_id = "audio.default"
            req = RGRequest(
                entity=entity,
                categories={"jobs": {"units": 1}},  # type: ignore[call-arg]
                tags={"policy_id": policy_id, "endpoint": "audio.jobs"},
            )
            dec, handle_id = await gov.reserve(req, op_id=f"audio-job:{entity}")
            if not dec.allowed or not handle_id:
                _metrics_increment("audio_quota_violations_total", {"type": "concurrent_jobs"})
                return False, "Concurrent job limit reached"
            # Track handle for explicit release in finish_job
            job_lock = await _get_job_handle_lock(user_key)
            async with job_lock:
                handles = _rg_job_handles.setdefault(user_key, [])
                handles.append(handle_id)
                # Approximate active count via local handles for metrics
                _metrics_set_gauge("audio_jobs_active", float(len(handles)), {"user_id": str(user_key)})
            return True, "OK"
        except Exception as e:
            logger.debug(f"RG error in can_start_job; falling back to legacy counters: {e}")

    # Legacy path: per-tier concurrent_jobs enforced via Redis / in-process counters.
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
    # When RG audio integration is enabled, release one jobs concurrency lease
    # for this user if present, then fall back to legacy counters for metrics.
    gov = await _get_audio_rg_governor()
    if gov is not None:
        try:
            user_key = int(user_id)
            job_lock = await _get_job_handle_lock(user_key)
            should_cleanup_lock = False
            async with job_lock:
                handles = _rg_job_handles.get(user_key)
                if handles:
                    handle_id = handles.pop()
                    try:
                        await gov.release(handle_id)
                    except Exception as e:
                        logger.debug(f"RG finish_job release failed: {e}")
                remaining_handles = _rg_job_handles.get(user_key)
                remaining = len(remaining_handles or [])
                if remaining == 0:
                    _rg_job_handles.pop(user_key, None)
                    should_cleanup_lock = True
                _metrics_set_gauge("audio_jobs_active", float(remaining), {"user_id": str(user_key)})
            if should_cleanup_lock:
                await _cleanup_job_handle_lock(user_key)
            # Even when RG is in use, do not touch Redis/in-process counters here
            # to avoid double-decrement; legacy state is not used when RG_ENABLE_AUDIO=1.
            return
        except Exception as e:
            logger.debug(f"RG error in finish_job; falling back to legacy counters: {e}")

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
    # Prefer ResourceGovernor-based concurrency when enabled for audio.
    gov = await _get_audio_rg_governor()
    if gov is not None and RGRequest is not None:
        try:
            entity = f"user:{int(user_id)}"
            policy_id = "audio.default"
            req = RGRequest(
                entity=entity,
                categories={"streams": {"units": 1}},  # type: ignore[call-arg]
                tags={"policy_id": policy_id, "endpoint": "audio.stream"},
            )
            dec, handle_id = await gov.reserve(req, op_id=f"audio-stream:{entity}")
            if not dec.allowed or not handle_id:
                _metrics_increment("audio_quota_violations_total", {"type": "concurrent_streams"})
                return False, "Concurrent streams limit reached"
            handles = _rg_stream_handles.setdefault(int(user_id), [])
            handles.append(handle_id)
            _metrics_set_gauge("audio_streaming_active", float(len(handles)), {"user_id": str(int(user_id))})
            return True, "OK"
        except Exception as e:
            logger.debug(f"RG error in can_start_stream; falling back to legacy counters: {e}")

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
    # When RG audio integration is enabled, release one streams concurrency
    # lease for this user if present and update metrics from local handles.
    gov = await _get_audio_rg_governor()
    if gov is not None:
        try:
            handles = _rg_stream_handles.get(int(user_id)) or []
            if handles:
                handle_id = handles.pop()
                try:
                    await gov.release(handle_id)
                except Exception as e:
                    logger.debug(f"RG finish_stream release failed: {e}")
            remaining = len(_rg_stream_handles.get(int(user_id)) or [])
            if remaining == 0:
                await _cleanup_stream_handles(int(user_id))
            _metrics_set_gauge("audio_streaming_active", float(remaining), {"user_id": str(int(user_id))})
            return
        except Exception as e:
            logger.debug(f"RG error in finish_stream; falling back to legacy counters: {e}")

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

    # Prefer the shared ResourceDailyLedger when available to enforce daily caps.
    ledger_remaining = await _ledger_remaining_minutes(user_id=int(user_id), daily_limit_minutes=float(limit))
    if ledger_remaining is not None:
        if minutes_requested > ledger_remaining:
            _metrics_increment("audio_quota_violations_total", {"type": "daily_minutes"})
            return False, max(0.0, ledger_remaining)
        return True, ledger_remaining - minutes_requested

    # Fallback to legacy audio_usage_daily enforcement.
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
    # When RG audio integration is enabled, renew any active RG streams leases
    # for this user using the configured stream TTL. Legacy Redis TTL refresh
    # remains as a fallback when RG is unavailable.
    gov = await _get_audio_rg_governor()
    if gov is not None:
        try:
            ttl = _get_stream_ttl_seconds()
            for handle_id in list(_rg_stream_handles.get(int(user_id)) or []):
                try:
                    await gov.renew(handle_id, ttl_s=ttl)
                except Exception as e:
                    logger.debug(f"RG heartbeat_stream renew failed for handle {handle_id}: {e}")
        except Exception as e:
            logger.debug(f"RG error in heartbeat_stream; falling back to legacy Redis TTL: {e}")

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


def _get_job_ttl_seconds() -> int:
    """Determine TTL for RG job leases; defaults to 600 seconds."""
    val_env = os.getenv("AUDIO_JOB_TTL_SECONDS")
    if val_env:
        try:
            v = int(val_env)
            return max(30, min(3600, v))
        except Exception:
            pass
    try:
        from tldw_Server_API.app.core.config import load_comprehensive_config  # lazy import

        cfg = load_comprehensive_config()
        if cfg and cfg.has_section("Audio-Quota"):
            try:
                v = int(cfg.get("Audio-Quota", "job_ttl_seconds", fallback="600"))
            except Exception:
                v = 600
            return max(30, min(3600, v))
    except Exception:
        pass
    return 600


def get_job_heartbeat_interval_seconds() -> int:
    """Return a safe heartbeat interval derived from the job TTL."""
    ttl = _get_job_ttl_seconds()
    if ttl <= 10:
        return ttl
    # Refresh roughly twice per TTL window while avoiding overly chatty loops.
    return max(10, ttl // 2)


async def heartbeat_jobs(user_id: int) -> None:
    """
    Renew active RG job leases to prevent premature expiry during long-running jobs.

    Legacy Redis/in-process counters are not renewed here; they do not rely on TTL.
    """
    gov = await _get_audio_rg_governor()
    if gov is None:
        return
    try:
        ttl = _get_job_ttl_seconds()
        handles = list(_rg_job_handles.get(int(user_id)) or [])
        if not handles:
            return
        job_lock = await _get_job_handle_lock(int(user_id))
        async with job_lock:
            for handle_id in list(_rg_job_handles.get(int(user_id)) or []):
                try:
                    await gov.renew(handle_id, ttl_s=ttl)
                except Exception as e:
                    logger.debug(f"RG heartbeat_jobs renew failed for handle {handle_id}: {e}")
    except Exception as e:
        logger.debug(f"RG error in heartbeat_jobs: {e}")


async def active_streams_count(user_id: int) -> int:
    """
    Get the number of currently active audio streams for a user.

    When Redis is available, reads the user's Redis counter key; otherwise returns the in-process counter. If the Redis value is missing or cannot be parsed as an integer, returns 0.

    Returns:
        int: Active stream count for the user.
    """
    # When RG audio integration is enabled, approximate active streams using
    # the in-process handle registry; peeking via the governor is possible but
    # not required for the status/limits endpoint semantics.
    gov = await _get_audio_rg_governor()
    if gov is not None:
        try:
            return len(_rg_stream_handles.get(int(user_id)) or [])
        except Exception as e:
            logger.debug(f"RG error in active_streams_count; falling back to legacy counters: {e}")

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
