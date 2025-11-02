# rate_limiter.py
# Per-user rate limiting for embeddings service

import time
import threading
from typing import Dict, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta

from loguru import logger
from tldw_Server_API.app.core.Embeddings.audit_adapter import log_security_violation


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

        # Track requests per user: user_id -> deque of timestamps
        self.user_requests: Dict[str, deque] = defaultdict(lambda: deque())

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
        with self._lock:
            current_time = time.time()
            window_start = current_time - self.window_seconds

            # Get user's request history
            user_queue = self.user_requests[user_id]

            # Remove old requests outside the window
            while user_queue and user_queue[0] < window_start:
                user_queue.popleft()

            # Get user's limit
            limit = self.get_user_limit(user_id)
            burst_limit = int(limit * self.burst_allowance)

            # Check if adding this request would exceed the limit
            current_count = len(user_queue)

            if current_count + cost > burst_limit:
                # Rate limit exceeded
                self.total_blocked += 1

                # Calculate when the oldest request will expire
                if user_queue:
                    retry_after = int(user_queue[0] + self.window_seconds - current_time) + 1
                else:
                    retry_after = 1

                # Unified audit (non-blocking)
                try:
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
                except Exception:
                    pass

                logger.warning(
                    f"Rate limit exceeded for user {user_id}: "
                    f"{current_count}/{limit} requests in {self.window_seconds}s"
                )

                return False, retry_after

            # Request allowed - record it
            for _ in range(cost):
                user_queue.append(current_time)

            self.total_requests += cost

            # Log if user is approaching limit
            if current_count + cost > limit * 0.8:
                logger.debug(
                    f"User {user_id} approaching rate limit: "
                    f"{current_count + cost}/{limit}"
                )

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
            while user_queue and user_queue[0] < window_start:
                user_queue.popleft()

            limit = self.get_user_limit(user_id)
            current_count = len(user_queue)

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
                if not queue or (queue and queue[-1] < cutoff_time):
                    users_to_remove.append(user_id)

            for user_id in users_to_remove:
                del self.user_requests[user_id]
                self.user_tiers.pop(user_id, None)

            if users_to_remove:
                logger.info(f"Cleaned up {len(users_to_remove)} inactive users from rate limiter")

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
            except Exception:
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
            except Exception:
                pass
            try:
                env_win = os.getenv('EMBEDDINGS_WINDOW_SECONDS')
                if env_win is not None:
                    win_seconds = max(1, int(env_win))
            except Exception:
                pass
            try:
                env_pl = os.getenv('EMBEDDINGS_PREMIUM_LIMIT')
                if env_pl is not None:
                    premium_limit = max(1, int(env_pl))
            except Exception:
                pass

            # Config fallbacks if envs are not set
            if rate_limit is None:
                if 'rate_limit_per_minute' in emb_cfg:
                    rate_limit = max(1, int(emb_cfg.get('rate_limit_per_minute', 60)))
                else:
                    # Legacy fallback to Chat-Module if Embeddings not configured
                    chat_cfg = {}
                    try:
                        if cfg and cfg.has_section('Chat-Module'):
                            chat_cfg = dict(cfg.items('Chat-Module'))
                    except Exception:
                        chat_cfg = {}
                    rate_limit = max(1, int(chat_cfg.get('rate_limit_per_minute', 60)))

            if win_seconds is None:
                win_seconds = int(emb_cfg.get('window_seconds', 60)) if emb_cfg else 60

            if premium_limit is None:
                # Allow premium multiplier or absolute limit
                try:
                    mult = emb_cfg.get('premium_multiplier') if emb_cfg else None
                    premium_limit = int(float(mult) * rate_limit) if mult is not None else rate_limit * 3
                except Exception:
                    premium_limit = rate_limit * 3

            _rate_limiter = UserRateLimiter(
                default_limit=rate_limit,
                window_seconds=win_seconds,
                premium_limit=premium_limit,
            )
        except Exception as e:
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
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.executor = None

    async def check_rate_limit_async(
        self,
        user_id: str,
        cost: int = 1,
        ip_address: Optional[str] = None
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
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            self.rate_limiter.check_rate_limit,
            user_id,
            cost,
            ip_address
        )

    async def record_usage_async(self, user_id: str, cost: int = 1):
        """Record usage asynchronously (for post-processing)"""
        # This is handled in check_rate_limit, but provided for compatibility
        pass

    async def get_user_usage_async(self, user_id: str) -> Dict[str, any]:
        """Get user usage statistics asynchronously"""
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
