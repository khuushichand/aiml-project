# character_rate_limiter.py
"""
Rate limiting for character operations to prevent abuse.
Supports both Redis (for distributed deployments) and in-memory (for single-instance).
"""

import time
import uuid
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

# Optional Redis import: allow running without redis-py installed
try:  # pragma: no cover - environment-dependent
    import redis  # type: ignore
except Exception:  # ImportError or environment issues
    redis = None  # type: ignore

from loguru import logger
from fastapi import HTTPException, status


class CharacterRateLimiter:
    """
    Rate limiter for character operations with Redis and in-memory fallback.

    Limits are per-user and apply to character creation, updates, and imports.
    """

    def __init__(
        self,
        redis_client: Optional[object] = None,
        max_operations: int = 100,
        window_seconds: int = 3600,
        max_characters: int = 1000,  # Max total characters per user
        max_import_size_mb: int = 10,  # Max import file size
        # Chat-specific limits
        max_chats_per_user: int = 100,  # Max concurrent chats per user
        max_messages_per_chat: int = 1000,  # Max messages per chat session
        max_chat_completions_per_minute: int = 20,  # Rate limit for chat completions
        max_message_sends_per_minute: int = 60,  # Rate limit for sending messages
        enabled: bool = True,
    ):
        """
        Initialize the rate limiter.

        Args:
            redis_client: Optional Redis client for distributed rate limiting
            max_operations: Maximum operations per window
            window_seconds: Time window in seconds
            max_characters: Maximum total characters per user
            max_import_size_mb: Maximum import file size in MB
            max_chats_per_user: Maximum concurrent chats per user
            max_messages_per_chat: Maximum messages per chat session
            max_chat_completions_per_minute: Rate limit for chat completions
            max_message_sends_per_minute: Rate limit for message sending
        """
        self.redis = redis_client
        self.max_operations = max_operations
        self.window_seconds = window_seconds
        self.max_characters = max_characters
        self.max_import_size_mb = max_import_size_mb

        # Chat-specific limits
        self.max_chats_per_user = max_chats_per_user
        self.max_messages_per_chat = max_messages_per_chat
        self.max_chat_completions_per_minute = max_chat_completions_per_minute
        self.max_message_sends_per_minute = max_message_sends_per_minute
        self.enabled = bool(enabled)

        # In-memory fallback storage (always ready for Redis failures)
        self.memory_store: Dict[int, List[float]] = defaultdict(list)

        logger.info(
            f"CharacterRateLimiter initialized: "
            f"max_ops={max_operations}/{window_seconds}s, "
            f"max_chars={max_characters}, "
            f"max_chats={max_chats_per_user}, "
            f"redis={'enabled' if redis_client else 'disabled (using memory)'}"
        )

    async def check_rate_limit(self, user_id: int, operation: str = "character_op") -> Tuple[bool, int]:
        """
        Check if user has exceeded rate limit.

        Args:
            user_id: User ID to check
            operation: Type of operation (for logging)

        Returns:
            Tuple of (allowed, remaining_operations)

        Raises:
            HTTPException: If rate limit exceeded
        """
        if not self.enabled:
            return True, self.max_operations
        key = f"rate_limit:character:{user_id}"

        if self.redis:
            member_token: Optional[str] = None
            try:
                # Use Redis for distributed rate limiting
                pipe = self.redis.pipeline()
                now = time.time()
                window_start = now - self.window_seconds
                member_token = f"{now:.9f}:{uuid.uuid4().hex}"

                # Remove old entries and count current
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                pipe.zadd(key, {member_token: now})
                pipe.expire(key, self.window_seconds)

                results = pipe.execute()
                current_count = results[1]

                if current_count >= self.max_operations:
                    if member_token:
                        try:
                            self.redis.zrem(key, member_token)
                        except Exception as cleanup_err:  # pragma: no cover - defensive
                            logger.debug(
                                "Failed to remove rate-limit token %s during rejection: %s",
                                member_token,
                                cleanup_err,
                            )
                    logger.warning(
                        f"Rate limit exceeded for user {user_id}: "
                        f"{current_count}/{self.max_operations} operations"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Max {self.max_operations} character operations per hour."
                    )

                remaining = max(self.max_operations - (current_count + 1), 0)
                logger.debug(f"Rate limit check for user {user_id}: {remaining} operations remaining (redis)")
                return True, remaining

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Redis error in rate limiter: {e}. Falling back to memory.")
                # Fall through to in-memory implementation

        # In-memory fallback
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries
        self.memory_store[user_id] = [
            t for t in self.memory_store[user_id]
            if t > window_start
        ]

        current_count = len(self.memory_store[user_id])

        if current_count >= self.max_operations:
            logger.warning(
                f"Rate limit exceeded for user {user_id} (memory): "
                f"{current_count}/{self.max_operations} operations"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.max_operations} character operations per hour."
            )

        self.memory_store[user_id].append(now)
        remaining = self.max_operations - current_count - 1
        logger.debug(f"Rate limit check for user {user_id} (memory): {remaining} operations remaining")
        return True, remaining

    async def check_character_limit(self, user_id: int, current_count: int) -> bool:
        """
        Check if user has exceeded maximum character limit.

        Args:
            user_id: User ID to check
            current_count: Current number of characters

        Returns:
            True if under limit, raises exception if over

        Raises:
            HTTPException: If character limit exceeded
        """
        if not self.enabled:
            return True
        if current_count >= self.max_characters:
            logger.warning(
                f"Character limit exceeded for user {user_id}: "
                f"{current_count}/{self.max_characters} characters"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Character limit exceeded. Maximum {self.max_characters} characters allowed."
            )
        return True

    def check_import_size(self, file_size_bytes: int) -> bool:
        """
        Check if import file size is within limits.

        Args:
            file_size_bytes: File size in bytes

        Returns:
            True if under limit, raises exception if over

        Raises:
            HTTPException: If file size exceeds limit
        """
        if not self.enabled:
            return True
        max_bytes = self.max_import_size_mb * 1024 * 1024
        if file_size_bytes > max_bytes:
            logger.warning(
                f"Import file too large: {file_size_bytes} bytes "
                f"(max: {max_bytes} bytes)"
            )
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File too large. Maximum size is {self.max_import_size_mb}MB."
            )
        return True

    async def get_usage_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get current usage statistics for a user.

        Args:
            user_id: User ID to check

        Returns:
            Dictionary with usage statistics
        """
        if not self.enabled:
            now = time.time()
            return {
                "operations_used": 0,
                "operations_limit": self.max_operations,
                "operations_remaining": self.max_operations,
                "window_seconds": self.window_seconds,
                "reset_time": now + self.window_seconds,
            }
        key = f"rate_limit:character:{user_id}"
        now = time.time()
        window_start = now - self.window_seconds

        if self.redis:
            try:
                try:
                    self.redis.zremrangebyscore(key, 0, window_start)
                except Exception:
                    logger.debug("Rate limiter stats: unable to prune Redis window for key {}", key)
                count = self.redis.zcount(key, window_start, "+inf")
                count_int = int(count)
                earliest_entry_score: Optional[float] = None
                if count_int:
                    try:
                        earliest_entry = self.redis.zrange(key, 0, 0, withscores=True)
                    except Exception:
                        earliest_entry = []
                    if earliest_entry:
                        # redis-py returns list of (member, score)
                        earliest_entry_score = float(earliest_entry[0][1])
                reset_time_val = (
                    earliest_entry_score + self.window_seconds
                    if earliest_entry_score is not None
                    else now
                )
                return {
                    "operations_used": count_int,
                    "operations_limit": self.max_operations,
                    "operations_remaining": max(0, self.max_operations - count_int),
                    "window_seconds": self.window_seconds,
                    "reset_time": reset_time_val,
                }
            except Exception:
                pass

        # In-memory fallback
        self.memory_store[user_id] = [
            t for t in self.memory_store[user_id]
            if t > window_start
        ]
        current_window_events = self.memory_store[user_id]
        count = len(current_window_events)
        earliest_timestamp = min(current_window_events) if current_window_events else None
        reset_time_val = (
            earliest_timestamp + self.window_seconds if earliest_timestamp is not None else now
        )

        return {
            "operations_used": count,
            "operations_limit": self.max_operations,
            "operations_remaining": max(0, self.max_operations - count),
            "window_seconds": self.window_seconds,
            "reset_time": reset_time_val
        }

    # ========== Chat-specific rate limiting methods ==========

    async def check_chat_limit(self, user_id: int, current_chat_count: int) -> bool:
        """
        Check if user has exceeded maximum chat limit.

        Args:
            user_id: User ID to check
            current_chat_count: Current number of active chats

        Returns:
            True if under limit

        Raises:
            HTTPException: If chat limit exceeded
        """
        if not self.enabled:
            return True
        if current_chat_count >= self.max_chats_per_user:
            logger.warning(
                f"Chat limit exceeded for user {user_id}: "
                f"{current_chat_count}/{self.max_chats_per_user} chats"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Chat limit exceeded. Maximum {self.max_chats_per_user} concurrent chats allowed."
            )
        return True

    async def check_message_limit(self, chat_id: str, current_message_count: int) -> bool:
        """
        Check if chat has exceeded maximum message limit.

        Args:
            chat_id: Chat session ID
            current_message_count: Current number of messages in chat

        Returns:
            True if under limit

        Raises:
            HTTPException: If message limit exceeded
        """
        if not self.enabled:
            return True
        if current_message_count > self.max_messages_per_chat:
            logger.warning(
                f"Message limit exceeded for chat {chat_id}: "
                f"{current_message_count}/{self.max_messages_per_chat} messages"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Message limit exceeded. Maximum {self.max_messages_per_chat} messages per chat."
            )
        return True

    async def check_chat_completion_rate(self, user_id: int) -> Tuple[bool, int]:
        """
        Check rate limit for chat completion requests.

        Args:
            user_id: User ID to check

        Returns:
            Tuple of (allowed, remaining_requests)

        Raises:
            HTTPException: If rate limit exceeded
        """
        if not self.enabled:
            return True, self.max_chat_completions_per_minute
        return await self._check_specific_rate(
            user_id,
            "chat_completion",
            self.max_chat_completions_per_minute,
            60  # 1 minute window
        )

    async def check_message_send_rate(self, user_id: int) -> Tuple[bool, int]:
        """
        Check rate limit for message sending.

        Args:
            user_id: User ID to check

        Returns:
            Tuple of (allowed, remaining_messages)

        Raises:
            HTTPException: If rate limit exceeded
        """
        if not self.enabled:
            return True, self.max_message_sends_per_minute
        return await self._check_specific_rate(
            user_id,
            "message_send",
            self.max_message_sends_per_minute,
            60  # 1 minute window
        )

    async def _check_specific_rate(
        self,
        user_id: int,
        operation_type: str,
        max_count: int,
        window: int
    ) -> Tuple[bool, int]:
        """
        Generic rate limit checker for specific operation types.

        Args:
            user_id: User ID to check
            operation_type: Type of operation (e.g., "chat_completion", "message_send")
            max_count: Maximum operations allowed
            window: Time window in seconds

        Returns:
            Tuple of (allowed, remaining_operations)

        Raises:
            HTTPException: If rate limit exceeded
        """
        if not self.enabled:
            return True, max_count
        key = f"rate_limit:{operation_type}:{user_id}"

        if self.redis:
            member_token: Optional[str] = None
            try:
                pipe = self.redis.pipeline()
                now = time.time()
                window_start = now - window
                member_token = f"{operation_type}:{now:.9f}:{uuid.uuid4().hex}"

                # Remove old entries and count current
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                pipe.zadd(key, {member_token: now})
                pipe.expire(key, window)

                results = pipe.execute()
                current_count = results[1]

                if current_count >= max_count:
                    if member_token:
                        try:
                            self.redis.zrem(key, member_token)
                        except Exception as cleanup_err:  # pragma: no cover - defensive
                            logger.debug(
                                "Failed to remove rate-limit token %s during rejection: %s",
                                member_token,
                                cleanup_err,
                            )
                    logger.warning(
                        f"Rate limit exceeded for {operation_type} by user {user_id}: "
                        f"{current_count}/{max_count} operations"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Max {max_count} {operation_type} operations per {window} seconds."
                    )

                remaining = max(max_count - (current_count + 1), 0)
                return True, remaining

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Redis error in rate limiter: {e}. Falling back to memory.")

        # In-memory fallback - use operation-specific store
        if not hasattr(self, 'operation_stores'):
            self.operation_stores = defaultdict(lambda: defaultdict(list))

        now = time.time()
        window_start = now - window

        # Clean old entries
        self.operation_stores[operation_type][user_id] = [
            t for t in self.operation_stores[operation_type][user_id]
            if t > window_start
        ]

        current_count = len(self.operation_stores[operation_type][user_id])

        if current_count >= max_count:
            logger.warning(
                f"Rate limit exceeded for {operation_type} by user {user_id} (memory): "
                f"{current_count}/{max_count} operations"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {max_count} {operation_type} operations per {window} seconds."
            )

        self.operation_stores[operation_type][user_id].append(now)
        remaining = max_count - current_count - 1
        return True, remaining


# Global instance (initialized in dependencies)
_rate_limiter: Optional[CharacterRateLimiter] = None


def get_character_rate_limiter() -> CharacterRateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter

    # Honor TEST_MODE by returning a permissive, in-memory limiter with huge limits
    # to prevent rate-limit related flakiness during test runs.
    import os
    test_mode = str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "on"}

    if test_mode:
        # If an existing limiter is not a test-mode limiter, replace it; otherwise reuse it.
        if _rate_limiter is None or not getattr(_rate_limiter, "_is_test_mode", False):
            _rate_limiter = CharacterRateLimiter(
                redis_client=None,                 # Force in-memory
                max_operations=1_000_000_000,      # Effectively unlimited
                window_seconds=3600,
                max_characters=1_000_000_000,      # Avoid 403s from character count
                max_import_size_mb=1_000,          # Generous import size for tests
                # Chat-specific limits
                max_chats_per_user=1_000_000_000,
                max_messages_per_chat=1_000_000_000,
                max_chat_completions_per_minute=1_000_000_000,
                max_message_sends_per_minute=1_000_000_000,
                enabled=True,
            )
            # Tag the instance so we can detect/reuse it in future calls
            setattr(_rate_limiter, "_is_test_mode", True)
        return _rate_limiter

    if _rate_limiter is None:
        # Initialize with Redis if available
        from tldw_Server_API.app.core.config import settings

        def _env_int(name: str, configured_value: Any, fallback: int) -> int:
            raw = os.getenv(name)
            if raw is not None:
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    logger.warning(f"Invalid environment override for {name}: {raw!r}. Using defaults.")
            if configured_value is not None:
                try:
                    return int(configured_value)
                except (TypeError, ValueError):
                    logger.warning(f"Invalid configured value for {name}: {configured_value!r}. Using fallback {fallback}.")
            return fallback

        redis_client = None
        if settings.get("REDIS_ENABLED", False):
            try:
                from tldw_Server_API.app.core.Infrastructure.redis_factory import create_sync_redis_client

                redis_client = create_sync_redis_client(
                    preferred_url=settings.get("REDIS_URL", None),
                    decode_responses=False,
                    context="character_rate_limiter",
                )
                logger.info("Redis connected for character rate limiting")
            except Exception as e:
                logger.warning(f"Redis not available for rate limiting: {e}. Using in-memory fallback.")
                redis_client = None

        default_max_ops = settings.get("CHARACTER_RATE_LIMIT_OPS", 100)
        default_window = settings.get("CHARACTER_RATE_LIMIT_WINDOW", 3600)
        default_max_chars = settings.get("MAX_CHARACTERS_PER_USER", 1000)
        default_import_size = settings.get("MAX_CHARACTER_IMPORT_SIZE_MB", 10)
        default_max_chats = settings.get("MAX_CHATS_PER_USER", 100)
        default_max_messages = settings.get("MAX_MESSAGES_PER_CHAT", 1000)
        default_chat_completions = settings.get("MAX_CHAT_COMPLETIONS_PER_MINUTE", 20)
        default_message_sends = settings.get("MAX_MESSAGE_SENDS_PER_MINUTE", 60)

        # Compute enabled flag (toggleable). Default: disabled in single-user unless explicitly enabled
        def _env_bool(name: str, configured_value: Any, fallback: bool) -> bool:
            raw = os.getenv(name)
            if raw is not None:
                s = str(raw).strip().lower()
                if s in {"1", "true", "yes", "on"}:
                    return True
                if s in {"0", "false", "no", "off"}:
                    return False
            if configured_value is not None:
                try:
                    return bool(configured_value)
                except Exception:
                    pass
            return fallback

        single_user_mode = bool(settings.get("SINGLE_USER_MODE", False))
        configured_enabled = settings.get("CHARACTER_RATE_LIMIT_ENABLED", None)
        if configured_enabled is None:
            configured_enabled = settings.get("RATE_LIMIT_ENABLED", None)
        default_enabled = not single_user_mode

        enabled_flag = _env_bool("CHARACTER_RATE_LIMIT_ENABLED", configured_enabled, default_enabled)

        _rate_limiter = CharacterRateLimiter(
            redis_client=redis_client,
            max_operations=_env_int("CHARACTER_RATE_LIMIT_OPS", default_max_ops, 100),
            window_seconds=_env_int("CHARACTER_RATE_LIMIT_WINDOW", default_window, 3600),
            max_characters=_env_int("MAX_CHARACTERS_PER_USER", default_max_chars, 1000),
            max_import_size_mb=_env_int("MAX_CHARACTER_IMPORT_SIZE_MB", default_import_size, 10),
            # Chat-specific limits
            max_chats_per_user=_env_int("MAX_CHATS_PER_USER", default_max_chats, 100),
            max_messages_per_chat=_env_int("MAX_MESSAGES_PER_CHAT", default_max_messages, 1000),
            max_chat_completions_per_minute=_env_int("MAX_CHAT_COMPLETIONS_PER_MINUTE", default_chat_completions, 20),
            max_message_sends_per_minute=_env_int("MAX_MESSAGE_SENDS_PER_MINUTE", default_message_sends, 60),
            enabled=enabled_flag,
        )

    return _rate_limiter
