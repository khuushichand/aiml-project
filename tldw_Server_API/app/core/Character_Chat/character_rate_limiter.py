# character_rate_limiter.py
"""
Rate limiting for character operations to prevent abuse.
Supports both Redis (for distributed deployments) and in-memory (for single-instance),
with optional ResourceGovernor integration.
"""

import asyncio
import os
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

# Optional Redis import: allow running without redis-py installed
try:  # pragma: no cover - environment-dependent
    import redis  # type: ignore
except Exception:  # ImportError or environment issues
    redis = None  # type: ignore

from fastapi import HTTPException, status
from loguru import logger

# Constants for rate limiting
RATE_LIMIT_WINDOW_SECONDS = 60
MAX_RATE_LIMIT_OPS_DEFAULT = 100

# Lua script for atomic rate limiting
# This script atomically:
# 1. Cleans old entries outside the window
# 2. Checks current count
# 3. Only adds the new member if under the limit
# 4. Returns [allowed (1/0), current_count]
RATE_LIMIT_LUA_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_count = tonumber(ARGV[3])
local member = ARGV[4]
local window_start = now - window

-- Clean old entries outside the window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Get current count AFTER cleanup
local current = redis.call('ZCARD', key)

-- Check limit before adding
if current >= max_count then
    return {0, current}  -- Denied, return current count
end

-- Add new member and set expiry
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window)

return {1, current + 1}  -- Allowed, return new count
"""

# Optional Resource Governor integration (gated by global RG_ENABLED/config)
try:  # pragma: no cover - RG is optional
    from tldw_Server_API.app.core.Resource_Governance import (  # type: ignore
        MemoryResourceGovernor,
        RedisResourceGovernor,
        RGRequest,
    )
    from tldw_Server_API.app.core.Resource_Governance.metrics_rg import (  # type: ignore
        record_shadow_mismatch,
    )
    from tldw_Server_API.app.core.Resource_Governance.policy_loader import (  # type: ignore
        PolicyLoader,
        PolicyReloadConfig,
        default_policy_loader,
    )
    from tldw_Server_API.app.core.config import rg_enabled  # type: ignore
except Exception:  # pragma: no cover - safe fallback when RG not installed
    MemoryResourceGovernor = None  # type: ignore
    RedisResourceGovernor = None  # type: ignore
    RGRequest = None  # type: ignore
    PolicyLoader = None  # type: ignore
    PolicyReloadConfig = None  # type: ignore
    default_policy_loader = None  # type: ignore
    rg_enabled = None  # type: ignore
    record_shadow_mismatch = None  # type: ignore


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
        self.shadow_enabled = os.getenv("RG_SHADOW_CHARACTER_CHAT", "0").lower() in {"1", "true", "yes", "on"}

        # In-memory fallback storage (always ready for Redis failures)
        self.memory_store: Dict[int, List[float]] = defaultdict(list)

        # Register Lua script for atomic rate limiting (if Redis available)
        self._rate_limit_script = None
        if self.redis is not None:
            try:
                self._rate_limit_script = self.redis.register_script(RATE_LIMIT_LUA_SCRIPT)
                logger.debug("Registered atomic rate limit Lua script with Redis")
            except Exception as e:
                logger.warning("Failed to register Lua script, falling back to pipeline: {}", e)
                self._rate_limit_script = None

        logger.info(
            "CharacterRateLimiter initialized: "
            "max_ops={}/{}, max_chars={}, max_chats={}, redis={}",
            max_operations, window_seconds, max_characters, max_chats_per_user,
            "enabled" if redis_client else "disabled (using memory)"
        )

    async def check_rate_limit(self, user_id: int, operation: str = "character_op") -> Tuple[bool, int]:
        """
        Check if user has exceeded rate limit using ResourceGovernor.

        When ResourceGovernor is enabled, this method delegates rate limiting to RG.
        When RG is disabled or unavailable, the legacy limiter (Redis or in-memory) is enforced.

        Args:
            user_id: User ID to check
            operation: Type of operation (for logging/tagging)

        Returns:
            Tuple of (allowed, remaining_operations).

        Raises:
            HTTPException(429): If rate limit exceeded (RG denied the request)
            HTTPException(429): If rate limit exceeded (legacy limiter)
        """
        if not _rg_character_enabled():
            return await self._check_legacy_rate_limit(user_id=user_id)

        rg_decision = await _maybe_enforce_with_rg_character(
            user_id=user_id,
            operation=operation,
        )
        if rg_decision is not None:
            rg_allowed = bool(rg_decision.get("allowed", False))
            policy_id = str(rg_decision.get("policy_id", "character_chat.default"))

            # Shadow mismatch (best-effort): compare to legacy without consuming counters.
            if self.shadow_enabled and record_shadow_mismatch is not None and self.enabled:
                try:
                    legacy_allowed: Optional[bool]
                    now = time.time()
                    window_start = now - float(self.window_seconds)
                    key = f"rate_limit:character:{user_id}"
                    if self.redis:
                        try:
                            current_count = int(self.redis.zcount(key, window_start, "+inf"))
                        except Exception:
                            current_count = 0
                    else:
                        # Prune old entries without charging a new operation
                        self.memory_store[user_id] = [t for t in self.memory_store[user_id] if t > window_start]
                        current_count = len(self.memory_store[user_id])
                    legacy_allowed = bool(current_count < int(self.max_operations))
                    legacy_dec = "allow" if legacy_allowed else "deny"
                    rg_dec = "allow" if rg_allowed else "deny"
                    if legacy_dec != rg_dec:
                        record_shadow_mismatch(
                            module="character_chat",
                            route=str(operation),
                            policy_id=policy_id,
                            legacy=legacy_dec,
                            rg=rg_dec,
                        )
                except Exception:
                    pass

            if not rg_allowed:
                retry_after = rg_decision.get("retry_after") or 60
                logger.warning(
                    "Character rate limit exceeded by ResourceGovernor for user {}: retry_after={}s",
                    user_id,
                    retry_after,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Rate limit exceeded. "
                        f"Policy {policy_id} denied request."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )

            # RG allow → RG is the sole enforcer. Legacy counters are not consumed.
            return True, self.max_operations

        _log_rg_character_fallback("rg_decision_unavailable")
        return await self._check_legacy_rate_limit(user_id=user_id)

    async def _check_legacy_rate_limit(self, user_id: int) -> Tuple[bool, int]:
        # Fallback enforcement when RG is disabled or cannot provide a decision.
        if not self.enabled:
            return True, self.max_operations

        now = time.time()
        window_start = now - float(self.window_seconds)

        if self.redis is not None:
            # Use Redis for distributed rate limiting. Delegate to the shared
            # helper so semantics (remaining counts, cleanup) match the
            # per-operation paths used for chat/message limits.
            try:
                allowed, remaining = await self._check_specific_rate(
                    user_id=user_id,
                    operation_type="character",
                    max_count=int(self.max_operations),
                    window=int(self.window_seconds),
                )
                return allowed, remaining
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("Redis rate limit check failed, falling back to memory: {}", e)
                # Fall through to memory-based limiting

        # In-memory rate limiting fallback
        self.memory_store[user_id] = [t for t in self.memory_store[user_id] if t > window_start]
        current_count = len(self.memory_store[user_id])

        if current_count >= self.max_operations:
            logger.warning(
                "Character rate limit exceeded for user {} (memory fallback): {}/{} ops",
                user_id, current_count, self.max_operations
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.max_operations} operations per {self.window_seconds}s.",
                headers={"Retry-After": str(self.window_seconds)},
            )

        self.memory_store[user_id].append(now)
        return True, self.max_operations - current_count - 1

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
        Get current usage statistics for a user based on local counters.

        This helper reports a simple view derived from the legacy
        rate-limit storage (Redis ZSET or in-memory list) and does not
        depend on ResourceGovernor. It is primarily intended for API
        status endpoints and tests.

        Args:
            user_id: User ID to check

        Returns:
            Dictionary with:
              - operations_used: number of operations recorded in the current window
              - operations_remaining: remaining operations before the limit is reached
              - reset_time: Unix timestamp when the current window fully expires,
                or None if no operations have been recorded.
        """
        now = time.time()
        timestamps: List[float] = []

        if self.redis is not None:
            key = f"rate_limit:character:{user_id}"
            try:
                # Prefer a ZSET-style view when available (real Redis or test doubles).
                zrange = getattr(self.redis, "zrange", None)
                if callable(zrange):
                    entries = zrange(key, 0, -1, withscores=True)
                    timestamps = [float(score) for _, score in entries]
                else:
                    # Fallback for simple dict-backed fakes that expose a .store mapping.
                    store = getattr(self.redis, "store", {})
                    bucket = store.get(key, {})
                    try:
                        timestamps = [float(score) for score in bucket.values()]
                    except Exception:
                        timestamps = []
            except Exception:
                timestamps = []
        else:
            try:
                timestamps = [float(t) for t in self.memory_store[int(user_id)]]
            except Exception:
                timestamps = []

        operations_used = len(timestamps)
        operations_remaining = max(int(self.max_operations) - operations_used, 0)

        if timestamps:
            oldest = min(timestamps)
            reset_time = oldest + float(self.window_seconds)
        else:
            reset_time = None

        return {
            "operations_used": operations_used,
            "operations_remaining": operations_remaining,
            "reset_time": reset_time,
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

        Uses an atomic Lua script for Redis to prevent race conditions where
        concurrent requests could exceed the limit.

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
            try:
                now = time.time()
                member_token = f"{operation_type}:{now:.9f}:{uuid.uuid4().hex}"

                # Use atomic Lua script if available (prevents race conditions)
                if self._rate_limit_script is not None:
                    try:
                        result = self._rate_limit_script(
                            keys=[key],
                            args=[now, window, max_count, member_token]
                        )
                        allowed = bool(result[0])
                        current_count = int(result[1])

                        if not allowed:
                            logger.warning(
                                "Rate limit exceeded for {} by user {}: {}/{} operations",
                                operation_type, user_id, current_count, max_count
                            )
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Rate limit exceeded. Max {max_count} {operation_type} operations per {window} seconds."
                            )

                        remaining = max(max_count - current_count, 0)
                        return True, remaining
                    except HTTPException:
                        raise
                    except Exception as script_err:
                        logger.warning(
                            "Lua script execution failed, falling back to pipeline: {}",
                            script_err
                        )
                        # Fall through to pipeline approach

                # Fallback pipeline approach (less atomic but still functional)
                pipe = self.redis.pipeline()
                window_start = now - window

                # Remove old entries and count current
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                pipe.zadd(key, {member_token: now})
                pipe.expire(key, window)

                results = pipe.execute()
                current_count = results[1]

                if current_count >= max_count:
                    # Remove the member we just added
                    try:
                        self.redis.zrem(key, member_token)
                    except Exception as cleanup_err:  # pragma: no cover - defensive
                        logger.debug(
                            "Failed to remove rate-limit token {} during rejection: {}",
                            member_token, cleanup_err,
                        )
                    logger.warning(
                        "Rate limit exceeded for {} by user {}: {}/{} operations",
                        operation_type, user_id, current_count, max_count
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
                logger.error("Redis error in rate limiter: {}. Falling back to memory.", e)

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


# --- Resource Governor plumbing (optional) ---------------------------------
_rg_char_governor = None
_rg_char_loader = None
_rg_char_lock = asyncio.Lock()
_rg_char_init_error: Optional[str] = None
_rg_char_init_error_logged = False
_rg_char_fallback_logged = False


def _rg_character_context() -> Dict[str, str]:
    policy_path = os.getenv(
        "RG_POLICY_PATH",
        "tldw_Server_API/Config_Files/resource_governor_policies.yaml",
    )
    try:
        policy_path_resolved = os.path.abspath(policy_path)
    except Exception:
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


def _log_rg_character_init_failure(exc: Exception) -> None:
    global _rg_char_init_error, _rg_char_init_error_logged
    _rg_char_init_error = repr(exc)
    if _rg_char_init_error_logged:
        return
    _rg_char_init_error_logged = True
    ctx = _rg_character_context()
    logger.exception(
        "Character Chat ResourceGovernor init failed; falling back to legacy limiter. "
        "backend={backend} policy_path={policy_path} policy_path_resolved={policy_path_resolved} "
        "policy_store={policy_store} reload_enabled={policy_reload_enabled} "
        "reload_interval={policy_reload_interval} cwd={cwd}",
        **ctx,
    )


def _log_rg_character_fallback(reason: str) -> None:
    global _rg_char_fallback_logged
    if _rg_char_fallback_logged:
        return
    _rg_char_fallback_logged = True
    ctx = _rg_character_context()
    logger.error(
        "Character Chat ResourceGovernor unavailable; falling back to legacy limiter. "
        "reason={} init_error={} backend={backend} policy_path={policy_path} "
        "policy_path_resolved={policy_path_resolved} policy_store={policy_store} "
        "reload_enabled={policy_reload_enabled} reload_interval={policy_reload_interval} cwd={cwd}",
        reason,
        _rg_char_init_error,
        **ctx,
    )


def _rg_character_enabled() -> bool:
    """Return True when RG should gate Character Chat operations."""
    if rg_enabled is not None:
        try:
            return bool(rg_enabled(True))  # type: ignore[func-returns-value]
        except Exception:
            return False
    return False


async def _get_character_rg_governor():
    """Lazily initialize a ResourceGovernor instance for Character Chat."""
    global _rg_char_governor, _rg_char_loader
    if not _rg_character_enabled():
        return None
    if RGRequest is None or PolicyLoader is None:
        _log_rg_character_fallback("rg_components_unavailable")
        return None
    if _rg_char_governor is not None:
        return _rg_char_governor
    async with _rg_char_lock:
        if _rg_char_governor is not None:
            return _rg_char_governor
        try:
            loader = (
                default_policy_loader()
                if default_policy_loader
                else PolicyLoader(
                    os.getenv(
                        "RG_POLICY_PATH",
                        "tldw_Server_API/Config_Files/resource_governor_policies.yaml",
                    ),
                    PolicyReloadConfig(
                        enabled=True,
                        interval_sec=int(
                            os.getenv("RG_POLICY_RELOAD_INTERVAL_SEC", "10") or "10"
                        ),
                    ),
                )
            )
            await loader.load_once()
            _rg_char_loader = loader
            backend = os.getenv("RG_BACKEND", "memory").lower()
            if backend == "redis" and RedisResourceGovernor is not None:
                gov = RedisResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            else:
                gov = MemoryResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            _rg_char_governor = gov
            return gov
        except Exception as exc:  # pragma: no cover - optional path
            _log_rg_character_init_failure(exc)
            return None


async def _maybe_enforce_with_rg_character(
    *,
    user_id: int,
    operation: str,
) -> Optional[Dict[str, object]]:
    """
    Optionally enforce Character Chat operations via ResourceGovernor.

    Returns a decision dict when RG is used, or None when RG is
    unavailable or disabled.
    """
    gov = await _get_character_rg_governor()
    if gov is None:
        return None
    policy_id = os.getenv("RG_CHARACTER_CHAT_POLICY_ID", "character_chat.default")
    op_id = f"character-{user_id}-{operation}-{time.time_ns()}"
    try:
        decision, handle = await gov.reserve(
            RGRequest(
                entity=f"user:{user_id}",
                categories={"requests": {"units": 1}},
                tags={
                    "policy_id": policy_id,
                    "module": "character_chat",
                    "operation": operation,
                },
            ),
            op_id=op_id,
        )
        if decision.allowed:
            if handle:
                try:
                    await gov.commit(handle, None, op_id=op_id)
                except Exception:
                    logger.debug("Character Chat RG commit failed", exc_info=True)
            return {"allowed": True, "retry_after": None, "policy_id": policy_id}
        return {
            "allowed": False,
            "retry_after": decision.retry_after or 1,
            "policy_id": policy_id,
        }
    except Exception as exc:
        logger.debug(
            "Character Chat RG reserve failed: {}", exc
        )
        return None


# Global instance (initialized in dependencies)
_rate_limiter: Optional[CharacterRateLimiter] = None


def get_character_rate_limiter() -> CharacterRateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter

    # Honor TEST_MODE by returning a permissive, in-memory limiter with huge limits
    # to prevent rate-limit related flakiness during test runs.
    import os
    test_mode = str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "on"}

    # Security check: warn if TEST_MODE is enabled in what looks like production
    if test_mode:
        env_name = os.getenv("ENVIRONMENT", os.getenv("ENV", "")).lower()
        prod_flag = os.getenv("tldw_production", "false").lower() in {"1", "true", "yes", "on", "y"}
        if env_name in ("production", "prod", "live") or prod_flag:
            logger.critical(
                "TEST_MODE is enabled in a production environment! "
                "This disables rate limiting and is a security risk. "
                "Unset TEST_MODE environment variable immediately."
            )

    # Helper to get env var as int, with test-mode default
    def _env_int_or_test_default(name: str, test_default: int) -> int:
        raw = os.getenv(name)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
        return test_default

    if test_mode:
        # If an existing limiter is not a test-mode limiter, replace it; otherwise reuse it.
        if _rate_limiter is None or not getattr(_rate_limiter, "_is_test_mode", False):
            # Honor explicit environment overrides even in test mode (allows rate limit tests)
            _rate_limiter = CharacterRateLimiter(
                redis_client=None,                 # Force in-memory
                max_operations=_env_int_or_test_default("CHARACTER_RATE_LIMIT_OPS", 1_000_000_000),
                window_seconds=3600,
                max_characters=_env_int_or_test_default("MAX_CHARACTERS_PER_USER", 1_000_000_000),
                max_import_size_mb=_env_int_or_test_default("MAX_CHARACTER_IMPORT_SIZE_MB", 1_000),
                # Chat-specific limits - use env vars if set, otherwise permissive defaults
                max_chats_per_user=_env_int_or_test_default("MAX_CHATS_PER_USER", 1_000_000_000),
                max_messages_per_chat=_env_int_or_test_default("MAX_MESSAGES_PER_CHAT", 1_000_000_000),
                max_chat_completions_per_minute=_env_int_or_test_default("MAX_CHAT_COMPLETIONS_PER_MINUTE", 1_000_000_000),
                max_message_sends_per_minute=_env_int_or_test_default("MAX_MESSAGE_SENDS_PER_MINUTE", 1_000_000_000),
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
