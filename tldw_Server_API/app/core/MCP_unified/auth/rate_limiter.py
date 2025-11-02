"""
Rate limiting for unified MCP module

Supports both in-memory and distributed (Redis) rate limiting.
"""

import time
import os
import asyncio
import inspect
from typing import Optional, Dict, Any
from collections import defaultdict, deque
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from loguru import logger

from ..config import get_config
from tldw_Server_API.app.core.Infrastructure.redis_factory import (
    create_async_redis_client,
)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds")


class BaseRateLimiter(ABC):
    """Abstract base class for rate limiters"""

    @abstractmethod
    async def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Check if request is allowed.

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        pass

    @abstractmethod
    async def reset(self, key: str):
        """Reset rate limit for a key"""
        pass

    @abstractmethod
    async def get_usage(self, key: str) -> Dict[str, Any]:
        """Get current usage statistics for a key"""
        pass


class TokenBucketRateLimiter(BaseRateLimiter):
    """
    Token bucket rate limiter for smooth rate limiting.

    Good for allowing burst traffic while maintaining average rate.
    """

    def __init__(self, rate: int, per: int, burst: int = None):
        """
        Initialize token bucket rate limiter.

        Args:
            rate: Number of requests allowed
            per: Time period in seconds
            burst: Maximum burst size (defaults to rate)
        """
        self.rate = rate
        self.per = per
        self.burst = burst or rate
        self.allowance = {}
        self.last_check = {}
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> tuple[bool, int]:
        """Check if request is allowed"""
        async with self._lock:
            current = time.time()

            # Initialize for new key
            if key not in self.allowance:
                self.allowance[key] = self.burst
                self.last_check[key] = current
                return (True, 0)

            # Calculate time passed
            time_passed = current - self.last_check[key]
            self.last_check[key] = current

            # Add tokens based on time passed
            self.allowance[key] += time_passed * (self.rate / self.per)

            # Cap at burst limit
            if self.allowance[key] > self.burst:
                self.allowance[key] = self.burst

            # Check if we have tokens
            if self.allowance[key] < 1.0:
                # Calculate retry after
                tokens_needed = 1.0 - self.allowance[key]
                retry_after = int(tokens_needed * (self.per / self.rate)) + 1
                return (False, retry_after)

            # Consume a token
            self.allowance[key] -= 1.0
            return (True, 0)

    async def reset(self, key: str):
        """Reset rate limit for a key"""
        async with self._lock:
            if key in self.allowance:
                del self.allowance[key]
                del self.last_check[key]

    async def get_usage(self, key: str) -> Dict[str, Any]:
        """Get current usage statistics"""
        async with self._lock:
            return {
                "tokens_remaining": int(self.allowance.get(key, self.burst)),
                "burst_limit": self.burst,
                "rate": f"{self.rate}/{self.per}s"
            }

    async def cleanup_old_entries(self, max_age: int = 3600):
        """Clean up old entries to prevent memory leak"""
        async with self._lock:
            current = time.time()
            keys_to_delete = []

            for key, last_check in self.last_check.items():
                if current - last_check > max_age:
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del self.allowance[key]
                del self.last_check[key]

            if keys_to_delete:
                logger.debug(f"Cleaned up {len(keys_to_delete)} old rate limit entries")


class SlidingWindowRateLimiter(BaseRateLimiter):
    """
    Sliding window rate limiter for precise rate limiting.

    More accurate than token bucket but uses more memory.
    """

    def __init__(self, rate: int, window: int):
        """
        Initialize sliding window rate limiter.

        Args:
            rate: Number of requests allowed
            window: Time window in seconds
        """
        self.rate = rate
        self.window = window
        self.requests = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> tuple[bool, int]:
        """Check if request is allowed"""
        async with self._lock:
            current = time.time()
            window_start = current - self.window

            # Get request timestamps for this key
            timestamps = self.requests[key]

            # Remove old timestamps outside window
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()

            # Check if under rate limit
            if len(timestamps) >= self.rate:
                # Calculate retry after (when oldest request exits window)
                retry_after = int(timestamps[0] + self.window - current) + 1
                return (False, retry_after)

            # Add current timestamp
            timestamps.append(current)
            return (True, 0)

    async def reset(self, key: str):
        """Reset rate limit for a key"""
        async with self._lock:
            if key in self.requests:
                del self.requests[key]

    async def get_usage(self, key: str) -> Dict[str, Any]:
        """Get current usage statistics"""
        async with self._lock:
            current = time.time()
            window_start = current - self.window

            # Count requests in current window
            timestamps = self.requests[key]
            count = sum(1 for ts in timestamps if ts >= window_start)

            return {
                "requests_in_window": count,
                "limit": self.rate,
                "window": f"{self.window}s",
                "remaining": max(0, self.rate - count)
            }

    async def cleanup_old_entries(self, max_age: int = 3600):
        """Clean up old entries to prevent memory leak"""
        async with self._lock:
            current = time.time()
            empty_keys = []

            for key, timestamps in self.requests.items():
                # Remove old timestamps
                cutoff = current - max_age
                while timestamps and timestamps[0] < cutoff:
                    timestamps.popleft()

                # Mark empty keys for deletion
                if not timestamps:
                    empty_keys.append(key)

            # Delete empty keys
            for key in empty_keys:
                del self.requests[key]

            if empty_keys:
                logger.debug(f"Cleaned up {len(empty_keys)} empty rate limit entries")


class DistributedRateLimiter(BaseRateLimiter):
    """
    Redis-backed distributed rate limiter for multi-instance deployments.

    Uses Redis Lua scripts for atomic operations.
    """

    def __init__(
        self,
        rate: int,
        window: int,
        redis_client=None,
        redis_url: Optional[str] = None,
        redis_kwargs: Optional[Dict[str, Any]] = None,
        context: str = "mcp_rate_limiter",
    ):
        """
        Initialize distributed rate limiter.

        Args:
            rate: Number of requests allowed
            window: Time window in seconds
            redis_client: Optional pre-configured Redis client
            redis_url: Redis URL for lazy initialization when client not supplied
            redis_kwargs: Additional kwargs for redis.from_url (password, ssl, etc.)
            context: Human-readable label for logging/fallback traces
        """
        self.rate = rate
        self.window = window
        self.redis = redis_client
        self._redis_url = redis_url
        self._redis_kwargs = dict(redis_kwargs or {})
        self._context = context
        self._fallback = None  # lazy TokenBucketRateLimiter fallback
        self.script_sha = None
        self._ensure_lock = asyncio.Lock()

        # Lua script for atomic rate limit check
        self.lua_script = """
        local key = KEYS[1]
        local limit = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local current_time = tonumber(ARGV[3])

        -- Remove old entries
        redis.call('ZREMRANGEBYSCORE', key, 0, current_time - window)

        -- Count current entries
        local current_count = redis.call('ZCARD', key)

        if current_count < limit then
            -- Add new entry
            redis.call('ZADD', key, current_time, current_time)
            redis.call('EXPIRE', key, window)
            return {1, 0}  -- allowed, no retry
        else
            -- Get oldest entry
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            if oldest[2] then
                local retry_after = math.ceil(oldest[2] + window - current_time)
                return {0, retry_after}  -- not allowed, retry after
            else
                return {0, window}  -- not allowed, retry after window
            end
        end
        """

    async def _ensure_redis(self) -> bool:
        """Ensure Redis client and Lua script are prepared before use."""
        if self.redis and self.script_sha:
            return True
        async with self._ensure_lock:
            if self.redis and self.script_sha:
                return True
            if not self.redis and self._redis_url:
                try:
                    self.redis = await create_async_redis_client(
                        preferred_url=self._redis_url,
                        context=self._context,
                        redis_kwargs=self._redis_kwargs,
                    )
                except Exception as exc:
                    logger.warning(f"Redis unavailable for {self._context}: {exc}")
                    self.redis = None
                    self.script_sha = None
                    return False
            if not self.redis:
                return False
            try:
                maybe_sha = self.redis.script_load(self.lua_script)
                if inspect.isawaitable(maybe_sha):
                    maybe_sha = await maybe_sha
                self.script_sha = maybe_sha
                return True
            except Exception as exc:
                logger.error(f"Failed to initialize Redis rate limiter script: {exc}")
                self.redis = None
                self.script_sha = None
                return False

    async def _fallback_limiter(self):
        """Lazily initialize in-memory fallback limiter."""
        if self._fallback is None:
            try:
                self._fallback = TokenBucketRateLimiter(rate=self.rate, per=self.window, burst=self.rate)
                logger.warning("Redis not available; using in-memory rate limiting fallback")
            except Exception:
                self._fallback = None
        return self._fallback

    def _record_fallback_metric(self) -> None:
        """Record metric for Redis fallback usage (best-effort)."""
        try:
            from ..monitoring.metrics import get_metrics_collector
            get_metrics_collector().record_rate_limit_fallback("redis")
        except Exception:
            pass

    async def _use_fallback(self, key: str) -> tuple[bool, int]:
        limiter = await self._fallback_limiter()
        self._record_fallback_metric()
        if limiter:
            return await limiter.is_allowed(key)
        return (True, 0)

    async def _fallback_reset(self, key: str) -> None:
        limiter = await self._fallback_limiter()
        if limiter:
            await limiter.reset(key)

    async def _fallback_get_usage(self, key: str) -> Dict[str, Any]:
        limiter = await self._fallback_limiter()
        if limiter:
            return await limiter.get_usage(key)
        return {"error": "Redis not available"}

    async def is_allowed(self, key: str) -> tuple[bool, int]:
        """Check if request is allowed using Redis"""
        if not await self._ensure_redis() or not self.redis or not self.script_sha:
            return await self._use_fallback(key)

        try:
            # Execute Lua script
            result = await self.redis.evalsha(
                self.script_sha,
                1,  # number of keys
                f"rate_limit:{key}",  # key
                self.rate,  # limit
                self.window,  # window
                time.time()  # current time
            )

            return (bool(result[0]), int(result[1]))

        except Exception as e:
            logger.error(f"Redis rate limit error: {e}; falling back to in-memory limiter")
            return await self._use_fallback(key)

    async def reset(self, key: str):
        """Reset rate limit for a key in Redis"""
        has_redis = await self._ensure_redis()
        if has_redis and self.redis:
            try:
                await self.redis.delete(f"rate_limit:{key}")
            except Exception as e:
                logger.error(f"Redis reset error: {e}")
        await self._fallback_reset(key)

    async def get_usage(self, key: str) -> Dict[str, Any]:
        """Get current usage statistics from Redis"""
        if not await self._ensure_redis() or not self.redis:
            return await self._fallback_get_usage(key)

        try:
            redis_key = f"rate_limit:{key}"
            current_time = time.time()

            # Remove old entries and count current
            await self.redis.zremrangebyscore(redis_key, 0, current_time - self.window)
            count = await self.redis.zcard(redis_key)

            return {
                "requests_in_window": count,
                "limit": self.rate,
                "window": f"{self.window}s",
                "remaining": max(0, self.rate - count)
            }

        except Exception as e:
            logger.error(f"Redis usage error: {e}; using in-memory usage stats if available")
            return await self._fallback_get_usage(key)


class RateLimiter:
    """
    Main rate limiter that automatically selects appropriate backend.

    Uses Redis if available, otherwise falls back to in-memory.
    """

    def __init__(self):
        self.config = get_config()
        self.limiters = {}
        self._using_distributed = False
        self._defer_cleanup = False
        self._cleanup_task_handle: Optional[asyncio.Task] = None
        self._init_limiters()
        # Optional category-specific limiters (e.g., ingestion vs read)
        # Defaults fall back to the main limiter rates
        try:
            # In-memory token buckets for categories when Redis not used
            rpm_ing = int(os.getenv("MCP_RATE_LIMIT_RPM_INGESTION", str(self.config.rate_limit_requests_per_minute)))
            burst_ing = int(os.getenv("MCP_RATE_LIMIT_BURST_INGESTION", str(self.config.rate_limit_burst_size)))
            rpm_read = int(os.getenv("MCP_RATE_LIMIT_RPM_READ", str(self.config.rate_limit_requests_per_minute)))
            burst_read = int(os.getenv("MCP_RATE_LIMIT_BURST_READ", str(self.config.rate_limit_burst_size)))
        except Exception:
            rpm_ing = self.config.rate_limit_requests_per_minute
            burst_ing = self.config.rate_limit_burst_size
            rpm_read = self.config.rate_limit_requests_per_minute
            burst_read = self.config.rate_limit_burst_size

        # If Redis is enabled, we reuse DistributedRateLimiter with window=60
        if self.config.rate_limit_use_redis and self.config.redis_url:
            params = self.config.get_redis_connection_params() or {}
            redis_url = params.get("url")
            redis_kwargs = {k: v for k, v in params.items() if k != "url"}
            if redis_url:
                self.ingestion_limiter = DistributedRateLimiter(
                    rate=rpm_ing,
                    window=60,
                    redis_url=redis_url,
                    redis_kwargs=dict(redis_kwargs),
                    context="mcp_ingestion_limiter",
                )
                self.read_limiter = DistributedRateLimiter(
                    rate=rpm_read,
                    window=60,
                    redis_url=redis_url,
                    redis_kwargs=dict(redis_kwargs),
                    context="mcp_read_limiter",
                )
                self._using_distributed = True
            else:
                self.ingestion_limiter = TokenBucketRateLimiter(rate=rpm_ing, per=60, burst=burst_ing)
                self.read_limiter = TokenBucketRateLimiter(rate=rpm_read, per=60, burst=burst_read)
        else:
            self.ingestion_limiter = TokenBucketRateLimiter(rate=rpm_ing, per=60, burst=burst_ing)
            self.read_limiter = TokenBucketRateLimiter(rate=rpm_read, per=60, burst=burst_read)

        # Start cleanup task for in-memory limiters; defer if no running loop
        if not self._using_distributed:
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task_handle = loop.create_task(self._cleanup_task())
            except RuntimeError:
                # No running event loop in this context (e.g., sync test setup)
                # Defer scheduling until later; functional behavior unaffected.
                self._defer_cleanup = True  # marker only

    def _init_limiters(self):
        """Initialize rate limiters based on configuration"""
        if self.config.rate_limit_use_redis and self.config.redis_url:
            params = self.config.get_redis_connection_params() or {}
            redis_url = params.get("url")
            redis_kwargs = {k: v for k, v in params.items() if k != "url"}
            if redis_url:
                self.default_limiter = DistributedRateLimiter(
                    rate=self.config.rate_limit_requests_per_minute,
                    window=60,
                    redis_url=redis_url,
                    redis_kwargs=redis_kwargs,
                    context="mcp_default_limiter",
                )
                logger.info("Using Redis-backed distributed rate limiting")
                self._using_distributed = True
                return
            logger.warning("Redis URL not configured; falling back to in-memory rate limiting")
        self._using_distributed = False
        self._init_memory_limiter()

    def _init_memory_limiter(self):
        """Initialize in-memory rate limiter"""
        self._using_distributed = False
        self.default_limiter = TokenBucketRateLimiter(
            rate=self.config.rate_limit_requests_per_minute,
            per=60,
            burst=self.config.rate_limit_burst_size
        )

    def _ensure_cleanup_task(self) -> None:
        """Schedule cleanup task once an event loop is available."""
        if self._using_distributed or not self._defer_cleanup:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._cleanup_task_handle and not self._cleanup_task_handle.done():
            self._defer_cleanup = False
            return
        self._cleanup_task_handle = loop.create_task(self._cleanup_task())
        self._defer_cleanup = False
        logger.info("Using in-memory token bucket rate limiting")

    async def check_rate_limit(
        self,
        key: str,
        limiter: Optional[BaseRateLimiter] = None
    ) -> None:
        """
        Check rate limit and raise exception if exceeded.

        Args:
            key: Unique identifier for rate limiting
            limiter: Optional custom limiter

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        if not self.config.rate_limit_enabled:
            return

        self._ensure_cleanup_task()

        limiter = limiter or self.default_limiter
        allowed, retry_after = await limiter.is_allowed(key)

        if not allowed:
            logger.warning(f"Rate limit exceeded for key: {key}")
            raise RateLimitExceeded(retry_after)

    async def get_usage(self, key: str) -> Dict[str, Any]:
        """Get rate limit usage for a key"""
        self._ensure_cleanup_task()
        return await self.default_limiter.get_usage(key)

    async def reset(self, key: str):
        """Reset rate limit for a key"""
        self._ensure_cleanup_task()
        await self.default_limiter.reset(key)
        logger.info(f"Rate limit reset for key: {key}", extra={"audit": True})

    async def _cleanup_task(self):
        """Background task to clean up old entries"""
        try:
            while True:
                await asyncio.sleep(3600)  # Run every hour
                try:
                    if hasattr(self.default_limiter, 'cleanup_old_entries'):
                        await self.default_limiter.cleanup_old_entries()
                    if hasattr(self.ingestion_limiter, 'cleanup_old_entries'):
                        await self.ingestion_limiter.cleanup_old_entries()
                    if hasattr(self.read_limiter, 'cleanup_old_entries'):
                        await self.read_limiter.cleanup_old_entries()

                    for limiter in self.limiters.values():
                        if hasattr(limiter, 'cleanup_old_entries'):
                            await limiter.cleanup_old_entries()

                except Exception as e:
                    logger.error(f"Error in rate limit cleanup: {e}")
        except asyncio.CancelledError:
            logger.info("Rate limiter cleanup task cancelled")
            return

    async def shutdown(self) -> None:
        """Cancel background cleanup task if running."""
        try:
            if getattr(self, "_cleanup_task_handle", None) and not self._cleanup_task_handle.done():
                self._cleanup_task_handle.cancel()
                try:
                    await self._cleanup_task_handle
                except asyncio.CancelledError:
                    pass
        except Exception:
            pass

    def get_category_limiter(self, category: str) -> BaseRateLimiter:
        """Return limiter for a category ('ingestion' or 'read')."""
        if category == 'ingestion':
            return self.ingestion_limiter
        return self.read_limiter


# Singleton instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter singleton"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

async def shutdown_rate_limiter() -> None:
    """Shutdown the singleton rate limiter, cancelling cleanup task if active."""
    try:
        global _rate_limiter
        if _rate_limiter is not None:
            await _rate_limiter.shutdown()
    except Exception:
        pass
