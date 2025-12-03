# rate_limiter.py
# Description: Database-backed rate limiting with token bucket algorithm
#
# Imports
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
import hashlib
import asyncio
import json
#
# 3rd-party imports
from redis import asyncio as redis_async
from redis.exceptions import RedisError
from loguru import logger
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter, log_histogram
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.exceptions import RateLimitError
from tldw_Server_API.app.core.AuthNZ.repos.rate_limits_repo import AuthnzRateLimitsRepo

#######################################################################################################################
#
# Rate Limiter Class


def _compute_window_start(now: datetime, window_minutes: int) -> datetime:
    """Return the start of the current time bucket for the requested window size.

    Uses day-based modulo so windows > 60 minutes align correctly.
    """
    window_minutes = max(1, int(window_minutes))
    window_seconds = window_minutes * 60
    # Seconds since start of day, to avoid anchoring only to the current hour
    seconds_since_day = now.hour * 3600 + now.minute * 60 + now.second
    offset = seconds_since_day % window_seconds
    window_start = now - timedelta(seconds=offset, microseconds=now.microsecond)
    return window_start.replace(microsecond=0)


def _window_key(timestamp: datetime) -> str:
    """Stable Redis key suffix for a bucketed timestamp."""
    return timestamp.strftime("%Y%m%d%H%M%S")

class RateLimiter:
    """
    Token bucket rate limiter with database backend and optional Redis caching

    Implements a sliding window rate limiter that:
    - Tracks requests per identifier (IP, user_id, API key)
    - Supports burst traffic handling
    - Uses database as source of truth
    - Optionally uses Redis for performance
    """

    def __init__(
        self,
        db_pool: Optional[DatabasePool] = None,
        settings: Optional[Settings] = None
    ):
        """Initialize rate limiter"""
        self.settings = settings or get_settings()
        self.db_pool = db_pool
        self.redis_client: Optional[redis_async.Redis] = None
        self.enabled = self.settings.RATE_LIMIT_ENABLED
        self._initialized = False

        # Default limits
        self.default_limit = self.settings.RATE_LIMIT_PER_MINUTE
        self.default_burst = self.settings.RATE_LIMIT_BURST

        # Service account limits
        self.service_limit = self.settings.SERVICE_ACCOUNT_RATE_LIMIT

        self._rate_limits_repo: Optional[AuthnzRateLimitsRepo] = None

    async def initialize(self):
        """Initialize rate limiter"""
        if self._initialized:
            return

        # Get database pool
        if not self.db_pool:
            self.db_pool = await get_db_pool()

        # Initialize Redis if configured
        if self.settings.REDIS_URL:
            try:
                self.redis_client = redis_async.from_url(
                    self.settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=1
                )
                await self.redis_client.ping()
                logger.debug("Redis connected for rate limiting")
            except (RedisError, Exception) as e:
                logger.warning(f"Redis unavailable for rate limiting: {e}")
                self.redis_client = None

        # Ensure required schema exists for the backend
        try:
            # If using SQLite (db_pool.pool is None), create required tables
            if not getattr(self.db_pool, 'pool', None):
                await self._ensure_sqlite_schema()
            else:
                await self._ensure_postgres_schema()
        except Exception as e:
            logger.warning(f"RateLimiter schema ensure warning: {e}")

        if self.db_pool and self._rate_limits_repo is None:
            self._rate_limits_repo = AuthnzRateLimitsRepo(self.db_pool)

        self._initialized = True
        logger.info(f"RateLimiter initialized (enabled={self.enabled})")
        log_counter("auth_rate_limiter_initialized", labels={"enabled": str(self.enabled)})

    def _get_rate_limits_repo(self) -> AuthnzRateLimitsRepo:
        """Return cached AuthnzRateLimitsRepo instance."""
        if not self.db_pool:
            raise RateLimitError("RateLimiter database pool is not initialized")
        if self._rate_limits_repo is None:
            self._rate_limits_repo = AuthnzRateLimitsRepo(self.db_pool)
        return self._rate_limits_repo

    async def _ensure_sqlite_schema(self):
        """Create SQLite tables used by rate limiter if they do not exist."""
        ddl_statements = [
            # Per-identifier request counts per window
            (
                """
                CREATE TABLE IF NOT EXISTS rate_limits (
                    identifier TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    request_count INTEGER NOT NULL,
                    window_start TEXT NOT NULL,
                    PRIMARY KEY (identifier, endpoint, window_start)
                )
                """,
                None,
            ),
            # Failed attempts for lockout
            (
                """
                CREATE TABLE IF NOT EXISTS failed_attempts (
                    identifier TEXT NOT NULL,
                    attempt_type TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    window_start TEXT NOT NULL,
                    PRIMARY KEY (identifier, attempt_type)
                )
                """,
                None,
            ),
            # Account lockouts
            (
                """
                CREATE TABLE IF NOT EXISTS account_lockouts (
                    identifier TEXT PRIMARY KEY,
                    locked_until TEXT NOT NULL,
                    reason TEXT
                )
                """,
                None,
            ),
            # Helpful index for queries by identifier
            (
                "CREATE INDEX IF NOT EXISTS idx_rate_limits_identifier ON rate_limits(identifier)",
                None,
            ),
        ]

        async with self.db_pool.transaction() as conn:
            for sql, params in ddl_statements:
                if hasattr(conn, 'execute'):
                    await conn.execute(sql) if not params else await conn.execute(sql, params)
            try:
                await conn.commit()
            except Exception:
                # aiosqlite transaction manager may commit outside; ignore
                pass

    async def _ensure_postgres_schema(self):
        """Create PostgreSQL tables used by the rate limiter if they do not exist."""
        ddl_statements = [
            (
                """
                CREATE TABLE IF NOT EXISTS rate_limits (
                    identifier TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    request_count INTEGER NOT NULL,
                    window_start TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (identifier, endpoint, window_start)
                )
                """,
                (),
            ),
            (
                """
                CREATE TABLE IF NOT EXISTS failed_attempts (
                    identifier TEXT NOT NULL,
                    attempt_type TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    window_start TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (identifier, attempt_type)
                )
                """,
                (),
            ),
            (
                """
                CREATE TABLE IF NOT EXISTS account_lockouts (
                    identifier TEXT PRIMARY KEY,
                    locked_until TIMESTAMPTZ NOT NULL,
                    reason TEXT
                )
                """,
                (),
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_rate_limits_identifier ON rate_limits(identifier)",
                (),
            ),
        ]

        async with self.db_pool.transaction() as conn:
            for sql, params in ddl_statements:
                await conn.execute(sql, *params)

    async def record_failed_attempt(
        self,
        identifier: str,
        attempt_type: str = "login",
        lockout_threshold: Optional[int] = None,
        lockout_duration_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Record a failed authentication attempt and check for lockout

        Args:
            identifier: Unique identifier (IP, username, etc.)
            attempt_type: Type of attempt (login, password_reset, etc.)
            lockout_threshold: Number of failures before lockout
            lockout_duration_minutes: Duration of lockout in minutes

        Returns:
            Dict with attempt count, lockout status, and reset time
        """
        if not self._initialized:
            await self.initialize()

        # Use settings defaults if not provided
        lockout_threshold = lockout_threshold or self.settings.MAX_LOGIN_ATTEMPTS
        lockout_duration_minutes = lockout_duration_minutes or self.settings.LOCKOUT_DURATION_MINUTES

        key = f"failed_{attempt_type}:{identifier}"
        now = datetime.now(timezone.utc)

        # Try Redis first if available
        if self.redis_client:
            try:
                # Increment counter with expiry
                pipe = self.redis_client.pipeline()
                pipe.incr(key)
                pipe.expire(key, lockout_duration_minutes * 60)
                results = await pipe.execute()

                attempt_count = results[0]

                if attempt_count >= lockout_threshold:
                    # Set lockout key
                    lockout_key = f"lockout:{identifier}"
                    await self.redis_client.setex(
                        lockout_key,
                        lockout_duration_minutes * 60,
                        json.dumps({
                            "locked_at": now.isoformat(),
                            "attempts": attempt_count,
                            "reason": f"Too many failed {attempt_type} attempts"
                        })
                    )

                    if self.settings.PII_REDACT_LOGS:
                        logger.warning("Account locked after failed attempts [redacted]")
                    else:
                        logger.warning(f"Account locked for {identifier} after {attempt_count} failed attempts")

                    return {
                        "attempt_count": attempt_count,
                        "is_locked": True,
                        "lockout_expires": (now + timedelta(minutes=lockout_duration_minutes)).isoformat(),
                        "remaining_attempts": 0
                    }

                return {
                    "attempt_count": attempt_count,
                    "is_locked": False,
                    "remaining_attempts": lockout_threshold - attempt_count
                }

            except (RedisError, Exception) as e:
                logger.warning(f"Redis error in record_failed_attempt: {e}")

        # Database fallback
        repo = self._get_rate_limits_repo()
        result = await repo.record_failed_attempt_and_lockout(
            identifier=identifier,
            attempt_type=attempt_type,
            now=now,
            lockout_threshold=int(lockout_threshold),
            lockout_duration_minutes=int(lockout_duration_minutes),
        )

        attempt_count = int(result.get("attempt_count", 0))
        is_locked = bool(result.get("is_locked", False))
        lockout_expires_dt = result.get("lockout_expires")

        if is_locked and lockout_expires_dt is not None:
            if self.settings.PII_REDACT_LOGS:
                logger.warning("Account locked after failed attempts [redacted]")
            else:
                logger.warning(
                    f"Account locked for {identifier} after {attempt_count} failed attempts"
                )
            log_counter("auth_rate_limit_lockout", labels={"attempt_type": attempt_type})

            return {
                "attempt_count": attempt_count,
                "is_locked": True,
                "lockout_expires": lockout_expires_dt.isoformat(),
                "remaining_attempts": 0,
            }

        return {
            "attempt_count": attempt_count,
            "is_locked": False,
            "remaining_attempts": max(0, lockout_threshold - attempt_count),
        }

    async def check_lockout(self, identifier: str) -> Tuple[bool, Optional[datetime]]:
        """
        Check if an identifier is currently locked out

        Args:
            identifier: Unique identifier to check

        Returns:
            Tuple of (is_locked, lockout_expires)
        """
        if not self._initialized:
            await self.initialize()

        now = datetime.now(timezone.utc)

        # Check Redis first
        if self.redis_client:
            try:
                lockout_key = f"lockout:{identifier}"
                lockout_data = await self.redis_client.get(lockout_key)
                if lockout_data:
                    data = json.loads(lockout_data)
                    locked_at = datetime.fromisoformat(data['locked_at'])
                    # Calculate expiry based on TTL
                    ttl = await self.redis_client.ttl(lockout_key)
                    if ttl > 0:
                        expires = now + timedelta(seconds=ttl)
                        return True, expires
                return False, None
            except (RedisError, Exception) as e:
                logger.warning(f"Redis error in check_lockout: {e}")

        # Database fallback
        repo = self._get_rate_limits_repo()
        locked_until = await repo.get_active_lockout(identifier=identifier, now=now)
        if locked_until is not None:
            return True, locked_until
        return False, None

    async def reset_failed_attempts(self, identifier: str, attempt_type: str = "login"):
        """
        Reset failed attempt counter for an identifier

        Args:
            identifier: Unique identifier
            attempt_type: Type of attempt to reset
        """
        if not self._initialized:
            await self.initialize()

        key = f"failed_{attempt_type}:{identifier}"

        # Clear from Redis
        if self.redis_client:
            try:
                await self.redis_client.delete(key)
                await self.redis_client.delete(f"lockout:{identifier}")
            except (RedisError, Exception) as e:
                logger.warning(f"Redis error in reset_failed_attempts: {e}")

        # Clear from database
        repo = self._get_rate_limits_repo()
        await repo.reset_failed_attempts_and_lockout(
            identifier=identifier,
            attempt_type=attempt_type,
        )

    async def check_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        limit: Optional[int] = None,
        burst: Optional[int] = None,
        window_minutes: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit

        Args:
            identifier: Unique identifier (IP, user_id, etc.)
            endpoint: API endpoint being accessed
            limit: Requests allowed per window (default from settings)
            burst: Burst requests allowed
            window_minutes: Time window in minutes

        Returns:
            Tuple of (is_allowed, metadata)
            - is_allowed: True if request is allowed
            - metadata: Rate limit information (remaining, reset_time, etc.)
        """
        if not self.enabled:
            return True, {"rate_limit_enabled": False}

        if not self._initialized:
            await self.initialize()

        # Use provided limits or defaults; treat zero values as intentional
        if limit is None:
            limit = self.default_limit
        if burst is None:
            burst = self.default_burst

        if limit <= 0:
            return True, {
                "limit": 0,
                "remaining": None,
                "reset_time": None,
                "retry_after": None,
                "rate_limit_enabled": True,
                "unbounded": True,
            }

        # Create unique key for rate limiting
        key = self._create_key(identifier, endpoint)

        # Try Redis first if available
        if self.redis_client:
            result = await self._check_redis_rate_limit(
                key, limit, burst, window_minutes
            )
            if result is not None:
                return result

        # Fallback to database
        return await self._check_database_rate_limit(
            identifier, endpoint, limit, burst, window_minutes
        )

    async def _check_redis_rate_limit(
        self,
        key: str,
        limit: int,
        burst: int,
        window_minutes: int
    ) -> Optional[Tuple[bool, Dict[str, Any]]]:
        """Check rate limit using Redis"""
        if not self.redis_client:
            return None

        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()

            now = datetime.now(timezone.utc)
            window_start = _compute_window_start(now, window_minutes)
            window_key = f"rate:{key}:{_window_key(window_start)}"

            # Increment counter
            pipe.incr(window_key)
            pipe.expire(window_key, window_minutes * 60 + 10)  # Extra 10 seconds buffer

            results = await pipe.execute()
            current_count = results[0]

            # Check burst by looking at previous window
            if current_count > limit - burst:
                prev_window_start = window_start - timedelta(minutes=window_minutes)
                prev_window_key = f"rate:{key}:{_window_key(prev_window_start)}"
                prev_count = await self.redis_client.get(prev_window_key)
                prev_count = int(prev_count) if prev_count else 0

                if prev_count + current_count > limit + burst:
                    # Rate limit exceeded
                    reset_time = window_start + timedelta(minutes=window_minutes)
                    retry_after = max(0, int((reset_time - now).total_seconds()))
                    return False, {
                        "limit": limit,
                        "remaining": 0,
                        "reset_time": reset_time.isoformat(),
                        "retry_after": retry_after,
                    }

            # Request allowed
            return True, {
                "limit": limit,
                "remaining": max(0, limit - current_count),
                "reset_time": (window_start + timedelta(minutes=window_minutes)).isoformat(),
            }

        except RedisError as e:
            logger.warning(f"Redis rate limit check failed: {e}")
            return None

    async def _check_database_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        limit: int,
        burst: int,
        window_minutes: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit using database"""
        now = datetime.now(timezone.utc)
        window_start = _compute_window_start(now, window_minutes)

        try:
            repo = self._get_rate_limits_repo()
            current_count = await repo.increment_rate_limit_window(
                identifier=identifier,
                endpoint=endpoint,
                window_start=window_start,
            )

            # Check burst with previous window when close to the limit
            if current_count > limit - burst:
                prev_window = window_start - timedelta(minutes=window_minutes)
                prev_count = await repo.get_rate_limit_count(
                    identifier=identifier,
                    endpoint=endpoint,
                    window_start=prev_window,
                )
                prev_count = prev_count or 0

                if prev_count + current_count > limit + burst:
                    reset_time = window_start + timedelta(minutes=window_minutes)
                    retry_after = max(0, int((reset_time - now).total_seconds()))
                    return False, {
                        "limit": limit,
                        "remaining": 0,
                        "reset_time": reset_time.isoformat(),
                        "retry_after": retry_after,
                    }

            # Request allowed
            return True, {
                "limit": limit,
                "remaining": max(0, limit - current_count),
                "reset_time": (
                    window_start + timedelta(minutes=window_minutes)
                ).isoformat(),
            }

        except Exception as e:
            logger.error(f"Database rate limit check failed: {e}")
            # In test mode, fail open to avoid spurious 429s when tables
            # are not provisioned by the test harness.
            try:
                import os
                if os.getenv("TEST_MODE") == "true":
                    return True, {
                        "rate_limit_enabled": True,
                        "note": "bypass on backend error in TEST_MODE"
                    }
            except Exception:
                pass
            # Otherwise, deny (fail closed) for security
            return False, {
                "error": "Rate limit check failed",
                "limit": limit,
                "remaining": 0,
                "retry_after": 60  # Conservative retry time
            }

    async def check_user_rate_limit(
        self,
        user_id: int,
        endpoint: str,
        role: str = "user"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit for authenticated user

        Args:
            user_id: User's database ID
            endpoint: API endpoint
            role: User's role (affects limits)

        Returns:
            Rate limit check result
        """
        # Determine limits based on role
        if role == "service":
            limit = self.service_limit
            burst = self.service_limit // 10
        elif role in ["admin", "root"]:
            limit = self.default_limit * 10
            burst = self.default_burst * 10
        elif role == "moderator":
            limit = self.default_limit * 2
            burst = self.default_burst * 2
        else:
            limit = self.default_limit
            burst = self.default_burst

        identifier = f"user:{user_id}"
        return await self.check_rate_limit(
            identifier, endpoint, limit, burst
        )

    async def check_ip_rate_limit(
        self,
        ip_address: str,
        endpoint: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit for IP address

        Args:
            ip_address: Client IP address
            endpoint: API endpoint

        Returns:
            Rate limit check result
        """
        identifier = f"ip:{ip_address}"
        return await self.check_rate_limit(identifier, endpoint)

    async def check_api_key_rate_limit(
        self,
        api_key_hash: str,
        endpoint: str,
        is_service_account: bool = False
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit for API key

        Args:
            api_key_hash: Hashed API key
            endpoint: API endpoint
            is_service_account: Whether this is a service account

        Returns:
            Rate limit check result
        """
        identifier = f"api:{api_key_hash[:16]}"  # Use first 16 chars of hash

        if is_service_account:
            limit = self.service_limit
            burst = self.service_limit // 10
        else:
            limit = self.default_limit
            burst = self.default_burst

        return await self.check_rate_limit(
            identifier, endpoint, limit, burst
        )

    async def reset_rate_limit(
        self,
        identifier: str,
        endpoint: Optional[str] = None
    ):
        """
        Reset rate limit for an identifier

        Args:
            identifier: Identifier to reset
            endpoint: Specific endpoint or all if None
        """
        if not self._initialized:
            await self.initialize()

        try:
            repo = self._get_rate_limits_repo()

            # Collect distinct endpoints for Redis cleanup before DB deletion when endpoint is None
            endpoints_for_cleanup: Optional[list[str]] = None
            if self.redis_client and endpoint is None:
                try:
                    endpoints = await repo.list_rate_limit_endpoints_for_identifier(
                        identifier=identifier
                    )
                    endpoints_for_cleanup = list(endpoints)
                except Exception as _e:
                    logger.debug(f"reset_rate_limit: failed to enumerate endpoints for {identifier}: {_e}")

            await repo.delete_rate_limits_for_identifier(
                identifier=identifier,
                endpoint=endpoint,
            )

            # Clear Redis cache if available
            if self.redis_client:
                # Keys are stored as rate:{md5(identifier:endpoint)}:{window}
                if endpoint:
                    pattern = f"rate:{self._create_key(identifier, endpoint)}:*"
                    async for key in self.redis_client.scan_iter(pattern):
                        await self.redis_client.delete(key)
                else:
                    # Use the enumerated endpoints to compute hashed keys and delete them
                    for ep in endpoints_for_cleanup or []:
                        pattern = f"rate:{self._create_key(identifier, ep)}:*"
                        async for key in self.redis_client.scan_iter(pattern):
                            await self.redis_client.delete(key)

            if self.settings.PII_REDACT_LOGS:
                logger.info("Reset rate limit [redacted]")
            else:
                logger.info(f"Reset rate limit for {identifier}")

        except Exception as e:
            logger.error(f"Failed to reset rate limit: {e}")

    async def cleanup_old_entries(self, hours: int = 1):
        """
        Clean up old rate limit entries

        Args:
            hours: Remove entries older than this many hours
        """
        if not self._initialized:
            await self.initialize()

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            repo = self._get_rate_limits_repo()
            deleted = await repo.cleanup_rate_limits_older_than(cutoff)
            if deleted:
                logger.info(f"Cleaned up {deleted} old rate limit entries")
        except Exception as e:
            logger.error(f"Rate limit cleanup failed: {e}")

    def _create_key(self, identifier: str, endpoint: str) -> str:
        """Create a unique key for rate limiting"""
        combined = f"{identifier}:{endpoint}"
        return hashlib.md5(combined.encode()).hexdigest()

    async def get_current_usage(
        self,
        identifier: str,
        endpoint: str,
        window_minutes: int = 1,
    ) -> Dict[str, Any]:
        """
        Get current rate limit usage for an identifier

        Args:
            identifier: Identifier to check
            endpoint: API endpoint
            window_minutes: Size of the rate-limit window (minutes)

        Returns:
            Current usage statistics
        """
        if not self._initialized:
            await self.initialize()

        now = datetime.now(timezone.utc)
        window_start = _compute_window_start(now, window_minutes)

        try:
            repo = self._get_rate_limits_repo()
            current_count = await repo.get_rate_limit_count(
                identifier=identifier,
                endpoint=endpoint,
                window_start=window_start,
            )
            current_count = current_count or 0

            return {
                "identifier": identifier,
                "endpoint": endpoint,
                "current_count": current_count,
                "limit": self.default_limit,
                "remaining": max(0, self.default_limit - current_count),
                "window_start": window_start.isoformat(),
                "window_end": (window_start + timedelta(minutes=window_minutes)).isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get rate limit usage: {e}")
            return {"error": "Failed to retrieve usage"}


#######################################################################################################################
#
# Module Functions

# Global instance
_rate_limiter: Optional[RateLimiter] = None


async def get_rate_limiter() -> RateLimiter:
    """Get rate limiter singleton instance"""
    global _rate_limiter
    if not _rate_limiter:
        _rate_limiter = RateLimiter()
        await _rate_limiter.initialize()
    return _rate_limiter


async def check_rate_limit(
    identifier: str,
    endpoint: str,
    limit: Optional[int] = None
) -> Tuple[bool, Dict[str, Any]]:
    """Convenience function to check rate limit"""
    limiter = await get_rate_limiter()
    return await limiter.check_rate_limit(identifier, endpoint, limit)


#
# End of rate_limiter.py
#######################################################################################################################
