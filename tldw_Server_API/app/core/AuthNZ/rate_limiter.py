"""AuthNZ limiter facade: lockout tracking via LockoutTracker + RG-compatible no-op rate limits.

Lockout logic has been extracted to ``lockout_tracker.py``.  This module
preserves the public API (``RateLimiter``, ``get_rate_limiter``,
``check_rate_limit``) for backward compatibility while delegating lockout
methods to ``LockoutTracker``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.exceptions import RateLimitError
from tldw_Server_API.app.core.AuthNZ.lockout_tracker import LockoutTracker, get_lockout_tracker
from tldw_Server_API.app.core.AuthNZ.repos.rate_limits_repo import AuthnzRateLimitsRepo
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings


class RateLimiter:
    """
    AuthNZ limiter facade.

    - Rate limiting is delegated to Resource Governor at ingress.
    - Lockout tracking is delegated to ``LockoutTracker``.
    - This class preserves compatibility signatures for existing callers.
    """

    def __init__(
        self,
        db_pool: DatabasePool | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.db_pool = db_pool
        self.enabled = True
        self._initialized = False
        self._rate_limits_repo: AuthnzRateLimitsRepo | None = None
        self._lockout: LockoutTracker | None = None

    async def initialize(self) -> None:
        if self._initialized:
            return
        if not self.db_pool:
            self.db_pool = await get_db_pool()
        if self._rate_limits_repo is None:
            self._rate_limits_repo = AuthnzRateLimitsRepo(self.db_pool)
        try:
            await self._rate_limits_repo.ensure_schema()
        except Exception as exc:
            logger.warning(f"AuthNZ limiter schema ensure warning: {exc}")
        # Initialize the lockout tracker with the same pool
        self._lockout = LockoutTracker(db_pool=self.db_pool, settings=self.settings)
        await self._lockout.initialize()
        self._initialized = True

    def _get_lockout_tracker(self) -> LockoutTracker:
        if self._lockout is not None:
            return self._lockout
        # Fallback to global singleton when not explicitly initialized
        return get_lockout_tracker()

    def _get_rate_limits_repo(self) -> AuthnzRateLimitsRepo:
        if not self.db_pool:
            raise RateLimitError("RateLimiter database pool is not initialized")
        if self._rate_limits_repo is None:
            self._rate_limits_repo = AuthnzRateLimitsRepo(self.db_pool)
        return self._rate_limits_repo

    async def check_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        limit: int | None = None,
        window_minutes: int | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """No-op rate limit check (RG handles ingress limits)."""
        return True, {"rate_limit_source": "resource_governor"}

    async def check_user_rate_limit(
        self,
        user_id: int,
        endpoint: str,
        limit: int | None = None,
        window_minutes: int | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """No-op per-user rate limit check (RG handles ingress limits)."""
        return True, {"rate_limit_source": "resource_governor"}

    @staticmethod
    def _window_start_for_minutes(now: datetime, window_minutes: int) -> datetime:
        # Normalize to a fixed bucket start to keep counters deterministic.
        minute_epoch = int(now.timestamp() // 60)
        bucket = minute_epoch - (minute_epoch % max(1, int(window_minutes)))
        return datetime.fromtimestamp(bucket * 60, tz=timezone.utc).replace(second=0, microsecond=0)

    async def check_rate_limit_fallback(
        self,
        *,
        identifier: str,
        endpoint: str,
        limit: int | None = None,
        window_minutes: int | None = None,
        fail_open: bool = True,
    ) -> tuple[bool, dict[str, Any]]:
        """
        DB-backed fallback limiter for auth endpoint abuse controls.

        This path is intended for explicit fallback usage when RG ingress
        governance is unavailable for a request.
        """
        if not getattr(self.settings, "RATE_LIMIT_ENABLED", True):
            return True, {"rate_limit_source": "authnz_fallback_db", "disabled": True}

        if not self._initialized:
            await self.initialize()

        limit_value = int(limit or getattr(self.settings, "RATE_LIMIT_PER_MINUTE", 60))
        window_value = int(window_minutes or 1)
        if limit_value <= 0 or window_value <= 0:
            return True, {"rate_limit_source": "authnz_fallback_db", "disabled": True}

        now = datetime.now(timezone.utc)
        window_start = self._window_start_for_minutes(now, window_value)
        reset_at = window_start + timedelta(minutes=window_value)
        retry_after = max(1, int((reset_at - now).total_seconds()))

        try:
            repo = self._get_rate_limits_repo()
            current_count = await repo.increment_rate_limit_window(
                identifier=identifier,
                endpoint=endpoint,
                window_start=window_start,
            )
            allowed = int(current_count) <= limit_value
            return allowed, {
                "rate_limit_source": "authnz_fallback_db",
                "limit": limit_value,
                "window_minutes": window_value,
                "current_count": int(current_count),
                "remaining": max(0, limit_value - int(current_count)),
                "retry_after": retry_after,
                "window_start": window_start.isoformat(),
                "reset_at": reset_at.isoformat(),
            }
        except Exception as exc:
            logger.warning(f"AuthNZ fallback rate limit failed for {endpoint} [{identifier}]: {exc}")
            if fail_open:
                return True, {
                    "rate_limit_source": "authnz_fallback_db",
                    "error": "fallback_limiter_unavailable",
                }
            raise RateLimitError("Fallback rate limiter unavailable")

    async def record_failed_attempt(
        self,
        identifier: str,
        attempt_type: str = "login",
        lockout_threshold: int | None = None,
        lockout_duration_minutes: int | None = None,
    ) -> dict[str, Any]:
        """Delegate to LockoutTracker."""
        tracker = self._get_lockout_tracker()
        return await tracker.record_failed_attempt(
            identifier,
            attempt_type=attempt_type,
            lockout_threshold=lockout_threshold,
            lockout_duration_minutes=lockout_duration_minutes,
        )

    async def check_lockout(self, identifier: str, attempt_type: str = "login") -> tuple[bool, datetime | None]:
        """Delegate to LockoutTracker."""
        tracker = self._get_lockout_tracker()
        return await tracker.check_lockout(identifier, attempt_type=attempt_type)

    async def reset_failed_attempts(self, identifier: str, attempt_type: str = "login") -> None:
        """Delegate to LockoutTracker."""
        tracker = self._get_lockout_tracker()
        await tracker.reset_failed_attempts(identifier, attempt_type=attempt_type)

    async def reset_rate_limit(self, identifier: str, endpoint: str | None = None) -> None:
        """No-op reset for legacy rate limit counters (deprecated)."""
        return None

    async def get_usage_stats(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"rate_limit_source": "resource_governor"}


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def check_rate_limit(
    identifier: str,
    endpoint: str,
    limit: int | None = None,
    window_minutes: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    limiter = get_rate_limiter()
    return await limiter.check_rate_limit(identifier, endpoint, limit=limit, window_minutes=window_minutes)
