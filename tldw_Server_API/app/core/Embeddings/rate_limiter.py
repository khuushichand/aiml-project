# rate_limiter.py
# Per-user rate limiting for embeddings service

import asyncio
import configparser
import os
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.Embeddings.audit_adapter import log_security_violation

try:
    # Resource Governor (optional; enabled via RG flags)
    from tldw_Server_API.app.core.Resource_Governance import (
        MemoryResourceGovernor,
        RedisResourceGovernor,
        RGRequest,
    )
    from tldw_Server_API.app.core.Resource_Governance.metrics_rg import (
        record_shadow_mismatch,
    )
    from tldw_Server_API.app.core.Resource_Governance.policy_loader import (
        PolicyLoader,
        PolicyReloadConfig,
        default_policy_loader,
    )
    from tldw_Server_API.app.core.config import rg_enabled  # type: ignore
except Exception:  # pragma: no cover - RG is optional for embeddings
    MemoryResourceGovernor = None  # type: ignore
    RedisResourceGovernor = None  # type: ignore
    RGRequest = None  # type: ignore
    record_shadow_mismatch = None  # type: ignore
    PolicyLoader = None  # type: ignore
    PolicyReloadConfig = None  # type: ignore
    default_policy_loader = None  # type: ignore
    rg_enabled = None  # type: ignore


class UserRateLimiter:
    """
    Per-user rate limiter using sliding window algorithm.
    Tracks API calls per user and enforces rate limits.
    """

    def __init__(
        self,
        default_limit: int = 60,  # Default requests per window
        window_seconds: int = 60,  # Window size in seconds
        premium_limit: int = 200,  # Premium user limit
        burst_allowance: float = 1.5  # Allow burst up to 1.5x limit
    ):
        """
        Initialize the rate limiter.

        Args:
            default_limit: Default number of requests per window
            window_seconds: Size of the sliding window in seconds
            premium_limit: Limit for premium users
            burst_allowance: Multiplier for burst allowance
        """
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.premium_limit = premium_limit
        self.burst_allowance = burst_allowance

        # Track requests per user: user_id -> deque of (timestamp, cost)
        self.user_requests: Dict[str, deque] = defaultdict(lambda: deque())
        # Shadow-only request history used for RG comparisons. This is kept
        # separate from the enforcement queue so that enabling RG does not
        # mutate legacy limiter state while still allowing “what would legacy
        # do?” drift metrics to remain meaningful.
        self._shadow_user_requests: Dict[str, deque] = defaultdict(lambda: deque())

        # Track user tiers: user_id -> tier
        self.user_tiers: Dict[str, str] = {}

        # Lock for thread safety
        self._lock = threading.RLock()

        # Statistics
        self.total_requests = 0
        self.total_blocked = 0

        logger.info(
            f"UserRateLimiter initialized: "
            f"default_limit={default_limit}/{window_seconds}s, "
            f"premium_limit={premium_limit}/{window_seconds}s"
        )

    def set_user_tier(self, user_id: str, tier: str) -> None:
        """
        Set the tier for a user (e.g., 'free', 'premium', 'enterprise').

        Args:
            user_id: User identifier
            tier: User tier
        """
        with self._lock:
            self.user_tiers[user_id] = tier

    def get_user_limit(self, user_id: str) -> int:
        """
        Get the rate limit for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Rate limit for the user
        """
        tier = self.user_tiers.get(user_id, 'free')

        if tier in ['premium', 'enterprise']:
            return self.premium_limit
        else:
            return self.default_limit

    def check_rate_limit(
        self,
        user_id: str,
        cost: int = 1,
        ip_address: Optional[str] = None
    ) -> tuple[bool, Optional[int]]:
        """
        Check if a user has exceeded their rate limit.

        Args:
            user_id: User identifier
            cost: Cost of this request (default 1)
            ip_address: IP address of the request

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        cost = int(cost) if cost is not None else 1
        if cost <= 0:
            cost = 1
        with self._lock:
            current_time = time.time()
            window_start = current_time - self.window_seconds

            # Get user's request history
            user_queue = self.user_requests[user_id]

            # Remove old requests outside the window
            while user_queue and user_queue[0][0] < window_start:
                user_queue.popleft()

            # Get user's limit
            limit = self.get_user_limit(user_id)
            burst_limit = int(limit * self.burst_allowance)

            # Check if adding this request would exceed the limit
            current_count = sum(entry[1] for entry in user_queue)

            if current_count + cost > burst_limit:
                # Rate limit exceeded
                self.total_blocked += 1

                # Calculate when the oldest request will expire
                if user_queue:
                    retry_after = int(user_queue[0][0] + self.window_seconds - current_time) + 1
                else:
                    retry_after = 1

                # Unified audit (mandatory)
                log_security_violation(
                    user_id=user_id,
                    action="embeddings_rate_limit_exceeded",
                    metadata={
                        "current_count": current_count,
                        "limit": limit,
                        "burst_limit": burst_limit,
                        "cost": cost,
                        "retry_after": retry_after,
                    },
                    ip_address=ip_address,
                )

                logger.warning(
                    f"Rate limit exceeded for user {user_id}: "
                    f"{current_count}/{limit} requests in {self.window_seconds}s"
                )

                return False, retry_after

            # Request allowed - record it
            user_queue.append((current_time, cost))

            self.total_requests += cost

            # Log if user is approaching limit
            if current_count + cost > limit * 0.8:
                logger.debug(
                    f"User {user_id} approaching rate limit: "
                    f"{current_count + cost}/{limit}"
                )

            return True, None

    def peek_rate_limit(
        self,
        user_id: str,
        cost: int = 1,
    ) -> tuple[bool, Optional[int]]:
        """
        Side-effect-light rate limit check (no consumption).

        This is intended for RG shadow comparisons where we want to know whether
        the legacy limiter *would* allow a request without counting it.

        This method evaluates the primary (enforcement) in-memory state.
        """
        cost = int(cost) if cost is not None else 1
        if cost <= 0:
            cost = 1
        with self._lock:
            current_time = time.time()
            window_start = current_time - self.window_seconds

            user_queue = self.user_requests[user_id]
            while user_queue and user_queue[0][0] < window_start:
                user_queue.popleft()

            limit = self.get_user_limit(user_id)
            burst_limit = int(limit * self.burst_allowance)
            current_count = sum(entry[1] for entry in user_queue)

            if current_count + cost > burst_limit:
                if user_queue:
                    retry_after = int(user_queue[0][0] + self.window_seconds - current_time) + 1
                else:
                    retry_after = 1
                return False, retry_after

            return True, None

    def peek_shadow_rate_limit(
        self,
        user_id: str,
        cost: int = 1,
    ) -> tuple[bool, Optional[int]]:
        """
        Side-effect-light rate limit check against shadow state.

        This is used for RG shadow comparisons: we want to know whether legacy
        *would* allow a request given the shadow traffic pattern, without
        recording a new request when RG denies.
        """
        cost = int(cost) if cost is not None else 1
        if cost <= 0:
            cost = 1
        with self._lock:
            current_time = time.time()
            window_start = current_time - self.window_seconds

            user_queue = self._shadow_user_requests[user_id]
            while user_queue and user_queue[0][0] < window_start:
                user_queue.popleft()

            limit = self.get_user_limit(user_id)
            burst_limit = int(limit * self.burst_allowance)
            current_count = sum(entry[1] for entry in user_queue)

            if current_count + cost > burst_limit:
                if user_queue:
                    retry_after = int(user_queue[0][0] + self.window_seconds - current_time) + 1
                else:
                    retry_after = 1
                return False, retry_after

            return True, None

    def shadow_check_rate_limit(
        self,
        user_id: str,
        cost: int = 1,
    ) -> tuple[bool, Optional[int]]:
        """
        Legacy limiter evaluation intended for RG shadow comparisons.

        This mirrors ``check_rate_limit`` without emitting audit/log noise or
        updating global stats counters. It updates *shadow-only* state so
        repeated comparisons reflect the traffic pattern being simulated
        without mutating the primary enforcement limiter state.
        """
        cost = int(cost) if cost is not None else 1
        if cost <= 0:
            cost = 1
        with self._lock:
            current_time = time.time()
            window_start = current_time - self.window_seconds

            user_queue = self._shadow_user_requests[user_id]
            while user_queue and user_queue[0][0] < window_start:
                user_queue.popleft()

            limit = self.get_user_limit(user_id)
            burst_limit = int(limit * self.burst_allowance)
            current_count = sum(entry[1] for entry in user_queue)

            if current_count + cost > burst_limit:
                if user_queue:
                    retry_after = int(user_queue[0][0] + self.window_seconds - current_time) + 1
                else:
                    retry_after = 1
                return False, retry_after

            user_queue.append((current_time, cost))

            return True, None

    def get_user_usage(self, user_id: str) -> Dict[str, any]:
        """
        Get current usage statistics for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with usage statistics
        """
        with self._lock:
            current_time = time.time()
            window_start = current_time - self.window_seconds

            user_queue = self.user_requests[user_id]

            # Clean old requests
            while user_queue and user_queue[0][0] < window_start:
                user_queue.popleft()

            limit = self.get_user_limit(user_id)
            current_count = sum(entry[1] for entry in user_queue)

            return {
                "user_id": user_id,
                "tier": self.user_tiers.get(user_id, 'free'),
                "current_usage": current_count,
                "limit": limit,
                "burst_limit": int(limit * self.burst_allowance),
                "window_seconds": self.window_seconds,
                "percentage_used": (current_count / limit * 100) if limit > 0 else 0,
                "requests_remaining": max(0, limit - current_count)
            }

    def reset_user(self, user_id: str) -> None:
        """
        Reset rate limit tracking for a specific user.

        Args:
            user_id: User identifier
        """
        with self._lock:
            if user_id in self.user_requests:
                self.user_requests[user_id].clear()
                logger.info(f"Rate limit reset for user {user_id}")

    def get_statistics(self) -> Dict[str, any]:
        """
        Get overall rate limiter statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            active_users = sum(1 for q in self.user_requests.values() if q)

            return {
                "total_requests": self.total_requests,
                "total_blocked": self.total_blocked,
                "block_rate": (self.total_blocked / self.total_requests * 100)
                              if self.total_requests > 0 else 0,
                "active_users": active_users,
                "window_seconds": self.window_seconds,
                "default_limit": self.default_limit,
                "premium_limit": self.premium_limit
            }

    def cleanup_old_entries(self, max_age_hours: int = 24) -> int:
        """
        Clean up old user entries that haven't been used recently.

        Args:
            max_age_hours: Remove users with no requests in this many hours

        Returns:
            Number of users cleaned up
        """
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - (max_age_hours * 3600)

            users_to_remove = []
            for user_id, queue in self.user_requests.items():
                if not queue or (queue and queue[-1][0] < cutoff_time):
                    users_to_remove.append(user_id)

            for user_id in users_to_remove:
                del self.user_requests[user_id]
                self.user_tiers.pop(user_id, None)

            # Also clean up shadow request history to prevent memory leak
            shadow_users_to_remove = []
            for user_id, queue in self._shadow_user_requests.items():
                if not queue or (queue and queue[-1][0] < cutoff_time):
                    shadow_users_to_remove.append(user_id)

            for user_id in shadow_users_to_remove:
                del self._shadow_user_requests[user_id]

            total_cleaned = len(users_to_remove) + len(shadow_users_to_remove)
            if total_cleaned:
                logger.info(
                    f"Cleaned up {len(users_to_remove)} inactive users and "
                    f"{len(shadow_users_to_remove)} shadow entries from rate limiter"
                )

            return len(users_to_remove)


# Global rate limiter instance
_rate_limiter: Optional[UserRateLimiter] = None


def get_rate_limiter() -> UserRateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        # Prefer Embeddings-specific config and environment overrides; fall back gracefully
        try:
            from tldw_Server_API.app.core.config import load_comprehensive_config
            cfg = load_comprehensive_config()
            emb_cfg = {}
            try:
                if cfg and cfg.has_section('Embeddings-Module'):
                    emb_cfg = dict(cfg.items('Embeddings-Module'))
            except (AttributeError, KeyError, TypeError, configparser.Error) as exc:
                logger.debug(f"Embeddings rate limiter: failed to read Embeddings-Module config: {exc}")
                emb_cfg = {}

            # Environment overrides take precedence
            import os
            rate_limit = None
            win_seconds = None
            premium_limit = None

            try:
                env_rate = os.getenv('EMBEDDINGS_RATE_LIMIT_PER_MINUTE')
                if env_rate is not None:
                    rate_limit = max(1, int(env_rate))
            except (TypeError, ValueError) as exc:
                logger.debug(f"Embeddings rate limiter: invalid EMBEDDINGS_RATE_LIMIT_PER_MINUTE: {exc}")
            try:
                env_win = os.getenv('EMBEDDINGS_WINDOW_SECONDS')
                if env_win is not None:
                    win_seconds = max(1, int(env_win))
            except (TypeError, ValueError) as exc:
                logger.debug(f"Embeddings rate limiter: invalid EMBEDDINGS_WINDOW_SECONDS: {exc}")
            try:
                env_pl = os.getenv('EMBEDDINGS_PREMIUM_LIMIT')
                if env_pl is not None:
                    premium_limit = max(1, int(env_pl))
            except (TypeError, ValueError) as exc:
                logger.debug(f"Embeddings rate limiter: invalid EMBEDDINGS_PREMIUM_LIMIT: {exc}")

            # Config fallbacks if envs are not set
            if rate_limit is None:
                if 'rate_limit_per_minute' in emb_cfg:
                    try:
                        rate_limit = max(1, int(emb_cfg.get('rate_limit_per_minute', 60)))
                    except (TypeError, ValueError) as exc:
                        logger.debug(f"Embeddings rate limiter: invalid rate_limit_per_minute: {exc}")
                        rate_limit = 60
                else:
                    # Legacy fallback to Chat-Module if Embeddings not configured
                    chat_cfg = {}
                    try:
                        if cfg and cfg.has_section('Chat-Module'):
                            chat_cfg = dict(cfg.items('Chat-Module'))
                    except (AttributeError, KeyError, TypeError, configparser.Error) as exc:
                        logger.debug(f"Embeddings rate limiter: failed to read Chat-Module config: {exc}")
                        chat_cfg = {}
                    try:
                        rate_limit = max(1, int(chat_cfg.get('rate_limit_per_minute', 60)))
                    except (TypeError, ValueError) as exc:
                        logger.debug(f"Embeddings rate limiter: invalid chat rate_limit_per_minute: {exc}")
                        rate_limit = 60

            if win_seconds is None:
                if emb_cfg:
                    try:
                        win_seconds = int(emb_cfg.get('window_seconds', 60))
                    except (TypeError, ValueError) as exc:
                        logger.debug(f"Embeddings rate limiter: invalid window_seconds: {exc}")
                        win_seconds = 60
                else:
                    win_seconds = 60

            if premium_limit is None:
                # Allow premium multiplier or absolute limit
                try:
                    mult = emb_cfg.get('premium_multiplier') if emb_cfg else None
                    premium_limit = int(float(mult) * rate_limit) if mult is not None else rate_limit * 3
                except (TypeError, ValueError) as exc:
                    logger.debug(f"Embeddings rate limiter: invalid premium_multiplier: {exc}")
                    premium_limit = rate_limit * 3

            _rate_limiter = UserRateLimiter(
                default_limit=rate_limit,
                window_seconds=win_seconds,
                premium_limit=premium_limit,
            )
        except (AttributeError, ImportError, KeyError, OSError, TypeError, ValueError, configparser.Error) as e:
            logger.warning(f"Could not load embeddings rate limit config: {e}. Using defaults.")
            _rate_limiter = UserRateLimiter()

    return _rate_limiter


def check_user_rate_limit(
    user_id: str,
    cost: int = 1,
    ip_address: Optional[str] = None
) -> tuple[bool, Optional[int]]:
    """
    Convenience function to check rate limit for a user.

    Args:
        user_id: User identifier
        cost: Cost of the request
        ip_address: IP address of the request

    Returns:
        Tuple of (allowed, retry_after_seconds)
    """
    limiter = get_rate_limiter()
    return limiter.check_rate_limit(user_id, cost, ip_address)


# Async extensions for rate limiting
import asyncio


class AsyncRateLimiter:
    """Async wrapper for UserRateLimiter"""

    def __init__(self, rate_limiter: Optional[UserRateLimiter] = None):
        self.rate_limiter = rate_limiter
        if self.rate_limiter is None and not _rg_embeddings_enabled():
            self.rate_limiter = get_rate_limiter()
        self.executor = None
        # Shadow-mode flag for comparing legacy vs RG behavior without breaking callers
        self.shadow_enabled = (
            os.getenv("RG_SHADOW_EMBEDDINGS", "0").lower() in {"1", "true", "yes", "on"}
        )

    async def _legacy_check_rate_limit(
        self,
        user_id: str,
        cost: int,
        ip_address: Optional[str],
    ) -> tuple[bool, Optional[int]]:
        if self.rate_limiter is None:
            self.rate_limiter = get_rate_limiter()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            self.rate_limiter.check_rate_limit,
            user_id,
            cost,
            ip_address,
        )

    async def check_rate_limit_async(
        self,
        user_id: str,
        cost: int = 1,
        ip_address: Optional[str] = None,
        tokens_units: int = 0,
    ) -> tuple[bool, Optional[int]]:
        """
        Async version of check_rate_limit.

        Args:
            user_id: User identifier
            cost: Cost of the request
            ip_address: IP address of the request

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        mode = _rate_limit_mode()
        legacy_cost = cost
        if mode == "tokens":
            legacy_cost = int(tokens_units or 0)
            if legacy_cost <= 0:
                legacy_cost = cost

        if not _rg_embeddings_enabled():
            if self.rate_limiter is None:
                self.rate_limiter = get_rate_limiter()
            # RG disabled: fall back to legacy limiter behavior.
            return await self._legacy_check_rate_limit(user_id, legacy_cost, ip_address)

        # Prefer Resource Governor when configured; use the legacy limiter only
        # as a fallback when RG is unavailable.
        rg_decision = await _maybe_enforce_with_rg(
            user_id=user_id,
            cost=cost,
            tokens_units=int(tokens_units or 0),
        )

        if rg_decision is not None:
            rg_allowed = bool(rg_decision.get("allowed", False))

            # Shadow comparison (best-effort): simulate legacy decision and record
            # mismatches between legacy allow/deny and RG allow/deny.
            if self.shadow_enabled and record_shadow_mismatch is not None and self.rate_limiter is not None:
                try:
                    loop = asyncio.get_running_loop()
                    if rg_allowed:
                        legacy_allowed, _legacy_retry = await loop.run_in_executor(
                            self.executor,
                            self.rate_limiter.shadow_check_rate_limit,
                            user_id,
                            legacy_cost,
                        )
                    else:
                        legacy_allowed, _legacy_retry = await loop.run_in_executor(
                            self.executor,
                            self.rate_limiter.peek_shadow_rate_limit,
                            user_id,
                            legacy_cost,
                        )

                    legacy_dec = "allow" if legacy_allowed else "deny"
                    rg_dec = "allow" if rg_allowed else "deny"
                    if legacy_dec != rg_dec:
                        record_shadow_mismatch(
                            module="embeddings",
                            route="/api/v1/embeddings",
                            policy_id=str(rg_decision.get("policy_id", "embeddings.default")),
                            legacy=legacy_dec,
                            rg=rg_dec,
                        )
                except Exception:  # noqa: BLE001 - observability only
                    # Observability only: never affect enforcement path.
                    pass

            return rg_allowed, rg_decision.get("retry_after")

        _log_rg_embeddings_fallback("rg_decision_unavailable")
        return await self._legacy_check_rate_limit(user_id, legacy_cost, ip_address)

    async def record_usage_async(self, user_id: str, cost: int = 1):
        """Record usage asynchronously (for post-processing)"""
        # This is handled in check_rate_limit, but provided for compatibility
        pass

    async def get_user_usage_async(self, user_id: str) -> Dict[str, any]:
        """Get user usage statistics asynchronously"""
        if self.rate_limiter is None:
            return {"available": False, "reason": "rate_limiter_disabled"}
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            self.rate_limiter.get_user_usage,
            user_id
        )


# Global async rate limiter
_async_rate_limiter: Optional[AsyncRateLimiter] = None


def get_async_rate_limiter() -> AsyncRateLimiter:
    """Get or create the global async rate limiter."""
    global _async_rate_limiter
    if _async_rate_limiter is None:
        _async_rate_limiter = AsyncRateLimiter()
    return _async_rate_limiter


# --- Resource Governor plumbing (optional) ---
_rg_embeddings_governor = None
_rg_embeddings_loader = None
_rg_embeddings_lock = asyncio.Lock()
_rg_embeddings_init_error: Optional[str] = None
_rg_embeddings_init_error_logged = False
_rg_embeddings_fallback_logged = False

_rate_limit_mode_warned = False


def _rate_limit_mode() -> str:
    """Return the embeddings rate limit mode ('tokens' or 'requests')."""
    raw = os.getenv("EMBEDDINGS_RATE_LIMIT_MODE", "tokens")
    mode = str(raw or "").strip().lower()
    if mode in {"token", "tokens", "tok"}:
        return "tokens"
    if mode in {"request", "requests", "req"}:
        return "requests"
    global _rate_limit_mode_warned
    if not _rate_limit_mode_warned:
        _rate_limit_mode_warned = True
        logger.warning(
            "Unknown EMBEDDINGS_RATE_LIMIT_MODE=%r; defaulting to 'tokens'.",
            raw,
        )
    return "tokens"


def _rg_embeddings_context() -> Dict[str, str]:
    policy_path = os.getenv(
        "RG_POLICY_PATH",
        "tldw_Server_API/Config_Files/resource_governor_policies.yaml",
    )
    try:
        policy_path_resolved = os.path.abspath(policy_path)
    except Exception:  # noqa: BLE001 - best-effort path resolution
        policy_path_resolved = policy_path
    return {
        "backend": os.getenv("RG_BACKEND", "memory"),
        "policy_path": policy_path,
        "policy_path_resolved": policy_path_resolved,
        "policy_store": os.getenv("RG_POLICY_STORE", ""),
        "policy_reload_enabled": os.getenv("RG_POLICY_RELOAD_ENABLED", ""),
        "policy_reload_interval": os.getenv("RG_POLICY_RELOAD_INTERVAL_SEC", ""),
        "cwd": os.getcwd(),
    }


def _log_rg_embeddings_init_failure(exc: Exception) -> None:
    global _rg_embeddings_init_error, _rg_embeddings_init_error_logged
    _rg_embeddings_init_error = repr(exc)
    if _rg_embeddings_init_error_logged:
        return
    _rg_embeddings_init_error_logged = True
    ctx = _rg_embeddings_context()
    logger.exception(
        "Embeddings ResourceGovernor init failed; falling back to legacy limiter. "
        "backend={backend} policy_path={policy_path} policy_path_resolved={policy_path_resolved} "
        "policy_store={policy_store} reload_enabled={policy_reload_enabled} "
        "reload_interval={policy_reload_interval} cwd={cwd}",
        **ctx,
    )


def _log_rg_embeddings_fallback(reason: str) -> None:
    global _rg_embeddings_fallback_logged
    if _rg_embeddings_fallback_logged:
        return
    _rg_embeddings_fallback_logged = True
    ctx = _rg_embeddings_context()
    logger.error(
        "Embeddings ResourceGovernor unavailable; falling back to legacy limiter. "
        "reason={} init_error={} backend={backend} policy_path={policy_path} "
        "policy_path_resolved={policy_path_resolved} policy_store={policy_store} "
        "reload_enabled={policy_reload_enabled} reload_interval={policy_reload_interval} cwd={cwd}",
        reason,
        _rg_embeddings_init_error,
        **ctx,
    )


def _rg_embeddings_enabled() -> bool:
    if rg_enabled:
        try:
            return bool(rg_enabled(True))  # type: ignore[func-returns-value]
        except Exception:  # noqa: BLE001 - RG should never break rate limiting
            return False
    return False


async def _get_embeddings_rg_governor():
    """Lazily initialize a ResourceGovernor for embeddings if enabled."""
    global _rg_embeddings_governor, _rg_embeddings_loader
    if not _rg_embeddings_enabled():
        return None
    if RGRequest is None or PolicyLoader is None:
        _log_rg_embeddings_fallback("rg_components_unavailable")
        return None
    if _rg_embeddings_governor is not None:
        return _rg_embeddings_governor
    async with _rg_embeddings_lock:
        if _rg_embeddings_governor is not None:
            return _rg_embeddings_governor
        try:
            loader = default_policy_loader() if default_policy_loader else PolicyLoader(
                os.getenv("RG_POLICY_PATH", "tldw_Server_API/Config_Files/resource_governor_policies.yaml"),
                PolicyReloadConfig(enabled=True, interval_sec=int(os.getenv("RG_POLICY_RELOAD_INTERVAL_SEC", "10") or "10")),
            )
            await loader.load_once()
            _rg_embeddings_loader = loader
            backend = os.getenv("RG_BACKEND", "memory").lower()
            if backend == "redis" and RedisResourceGovernor is not None:
                gov = RedisResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            else:
                gov = MemoryResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            _rg_embeddings_governor = gov
            return gov
        except Exception as exc:  # pragma: no cover - optional path  # noqa: BLE001
            _log_rg_embeddings_init_failure(exc)
            return None


async def _maybe_enforce_with_rg(
    user_id: str,
    cost: int,
    tokens_units: int = 0,
) -> Optional[Dict[str, object]]:
    """
    Attempt to enforce embeddings limits via Resource Governor.

    Requests are enforced at ingress via `RGSimpleMiddleware`. This helper is
    used for token accounting (and legacy fallback) and MUST NOT reserve
    `requests` to avoid double-enforcement on RG-governed routes.

    Returns a decision dict when RG is used, or None when RG is unavailable/disabled.
    """
    gov = await _get_embeddings_rg_governor()
    if gov is None:
        return None
    policy_id = os.getenv("RG_EMBEDDINGS_POLICY_ID", "embeddings.default")
    op_id = f"emb-{user_id}-{time.time_ns()}"
    try:
        try:
            tu = int(tokens_units or 0)
        except Exception:  # noqa: BLE001 - defensive conversion
            tu = 0
        tu = max(0, tu)

        # Only enforce token budgets here; request-rate limiting happens at ingress.
        categories: Dict[str, Dict[str, int]] = {}
        if tu > 0:
            categories["tokens"] = {"units": tu}
        else:
            # No token units to enforce; allow and bypass legacy limiter.
            return {"allowed": True, "retry_after": None, "policy_id": policy_id}

        decision, handle = await gov.reserve(
            RGRequest(
                entity=f"user:{user_id}",
                categories=categories,
                tags={"policy_id": policy_id, "module": "embeddings"},
            ),
            op_id=op_id,
        )
        if decision.allowed:
            # Treat reserve as consumption and finalize immediately to keep semantics simple.
            if handle:
                try:
                    await gov.commit(handle, None, op_id=op_id)
                except Exception:  # noqa: BLE001 - logging-only fallback
                    logger.debug("Embeddings RG commit failed", exc_info=True)
            return {"allowed": True, "retry_after": None, "policy_id": policy_id}
        return {
            "allowed": False,
            "retry_after": decision.retry_after or 1,
            "policy_id": policy_id,
        }
    except Exception as exc:  # noqa: BLE001 - fallback to legacy limiter on RG errors
        logger.debug(f"Embeddings RG reserve failed; falling back to legacy: {exc}")
        return None
