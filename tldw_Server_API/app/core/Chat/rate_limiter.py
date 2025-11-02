# rate_limiter.py
# Description: Advanced rate limiting with per-conversation and per-user limits
#
# Imports
import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import os
from loguru import logger

#######################################################################################################################
#
# Types:

@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    global_rpm: int = 60  # Global requests per minute
    per_user_rpm: int = 20  # Per-user requests per minute
    per_conversation_rpm: int = 10  # Per-conversation requests per minute
    per_user_tokens_per_minute: int = 10000  # Token limit per user
    burst_multiplier: float = 1.5  # Allow burst up to 1.5x normal rate

@dataclass
class UsageStats:
    """Usage statistics for tracking."""
    request_count: int = 0
    token_count: int = 0
    last_request_time: Optional[float] = None
    conversation_request_counts: Dict[str, int] = None

    def __post_init__(self):
        if self.conversation_request_counts is None:
            self.conversation_request_counts = {}

#######################################################################################################################
#
# Classes:

class TokenBucket:
    """
    Token bucket algorithm for rate limiting with burst support.
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were available, False otherwise
        """
        async with self._lock:
            # Refill bucket
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            # Try to consume
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def wait_for_tokens(self, tokens: int = 1, timeout: float = 60) -> bool:
        """
        Wait for tokens to become available.

        Args:
            tokens: Number of tokens needed
            timeout: Maximum wait time

        Returns:
            True if tokens obtained, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if await self.consume(tokens):
                return True

            # Calculate wait time
            needed = tokens - self.tokens
            wait_time = min(needed / self.refill_rate, 1.0)
            await asyncio.sleep(wait_time)

        return False

    async def refund(self, tokens: int = 1) -> None:
        """
        Safely return tokens to the bucket using the internal lock.

        Args:
            tokens: Number of tokens to return (clamped to capacity)
        """
        if tokens <= 0:
            return
        async with self._lock:
            self.tokens = min(self.capacity, self.tokens + tokens)


class ConversationRateLimiter:
    """
    Rate limiter with per-conversation, per-user, and global limits.
    """

    def __init__(self, config: RateLimitConfig):
        """
        Initialize the rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config

        # Token buckets for different scopes
        self.global_bucket = TokenBucket(
            capacity=int(config.global_rpm * config.burst_multiplier),
            refill_rate=config.global_rpm / 60
        )

        self.user_buckets: Dict[str, TokenBucket] = {}
        self.conversation_buckets: Dict[str, TokenBucket] = {}
        self.user_token_buckets: Dict[str, TokenBucket] = {}

        # Usage tracking
        self.usage_stats: Dict[str, UsageStats] = defaultdict(UsageStats)

        # Sliding window for more accurate tracking
        self.request_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Idle cleanup support
        self._last_cleanup: float = time.time()
        self._idle_threshold_seconds: int = 3600  # default: purge buckets idle > 1h

    def _get_or_create_bucket(
        self,
        bucket_dict: Dict[str, TokenBucket],
        key: str,
        capacity: int,
        refill_rate: float
    ) -> TokenBucket:
        """Get or create a token bucket."""
        if key not in bucket_dict:
            bucket_dict[key] = TokenBucket(capacity, refill_rate)
        return bucket_dict[key]

    async def check_rate_limit(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        estimated_tokens: int = 0
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if request is within rate limits.

        Args:
            user_id: User identifier
            conversation_id: Optional conversation identifier
            estimated_tokens: Estimated token count for the request

        Returns:
            Tuple of (allowed, error_message)
        """
        # Opportunistic idle cleanup every 5 minutes
        now = time.time()
        if now - self._last_cleanup > 300:
            try:
                self.cleanup_idle_buckets(self._idle_threshold_seconds)
            finally:
                self._last_cleanup = now

        # Check global rate limit
        if not await self.global_bucket.consume():
            return False, "Global rate limit exceeded"

        # Check per-user rate limit
        user_bucket = self._get_or_create_bucket(
            self.user_buckets,
            user_id,
            int(self.config.per_user_rpm * self.config.burst_multiplier),
            self.config.per_user_rpm / 60
        )

        if not await user_bucket.consume():
            # Return token to global bucket since we're not using it
            await self.global_bucket.refund(1)
            return False, f"User rate limit exceeded for {user_id}"

        # Check per-conversation rate limit if specified
        if conversation_id:
            conv_bucket = self._get_or_create_bucket(
                self.conversation_buckets,
                conversation_id,
                int(self.config.per_conversation_rpm * self.config.burst_multiplier),
                self.config.per_conversation_rpm / 60
            )

            if not await conv_bucket.consume():
                # Return tokens
                await self.global_bucket.refund(1)
                await user_bucket.refund(1)
                return False, f"Conversation rate limit exceeded for {conversation_id}"

        # Check token limit if specified
        if estimated_tokens > 0:
            token_bucket = self._get_or_create_bucket(
                self.user_token_buckets,
                user_id,
                int(self.config.per_user_tokens_per_minute * self.config.burst_multiplier),
                self.config.per_user_tokens_per_minute / 60
            )

            if not await token_bucket.consume(estimated_tokens):
                # Return tokens
                await self.global_bucket.refund(1)
                await user_bucket.refund(1)
                if conversation_id:
                    # conv_bucket is defined above when conversation_id is provided
                    await conv_bucket.refund(1)  # type: ignore[name-defined]
                return False, f"Token limit exceeded for user {user_id}"

        # Update usage stats
        stats = self.usage_stats[user_id]
        stats.request_count += 1
        stats.token_count += estimated_tokens
        stats.last_request_time = time.time()
        if conversation_id:
            stats.conversation_request_counts[conversation_id] = \
                stats.conversation_request_counts.get(conversation_id, 0) + 1

        # Record in sliding window
        self.request_windows[user_id].append((time.time(), estimated_tokens))

        return True, None

    async def wait_for_capacity(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        estimated_tokens: int = 0,
        timeout: float = 60
    ) -> Tuple[bool, Optional[str]]:
        """
        Wait for rate limit capacity to become available.

        Args:
            user_id: User identifier
            conversation_id: Optional conversation identifier
            estimated_tokens: Estimated token count
            timeout: Maximum wait time

        Returns:
            Tuple of (allowed, error_message)
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            allowed, error = await self.check_rate_limit(
                user_id, conversation_id, estimated_tokens
            )

            if allowed:
                return True, None

            # Wait a bit before retrying
            await asyncio.sleep(0.5)

        return False, f"Timeout waiting for rate limit capacity"

    def get_usage_stats(self, user_id: str) -> Dict[str, any]:
        """
        Get usage statistics for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with usage statistics
        """
        stats = self.usage_stats.get(user_id, UsageStats())
        window = self.request_windows.get(user_id, deque())

        # Calculate rates over last minute
        now = time.time()
        minute_ago = now - 60
        recent_requests = [(t, tokens) for t, tokens in window if t > minute_ago]

        requests_per_minute = len(recent_requests)
        tokens_per_minute = sum(tokens for _, tokens in recent_requests)

        # Get current bucket states
        user_bucket = self.user_buckets.get(user_id)
        user_tokens_available = user_bucket.tokens if user_bucket else self.config.per_user_rpm
        token_bucket = self.user_token_buckets.get(user_id)
        user_token_capacity = token_bucket.tokens if token_bucket else self.config.per_user_tokens_per_minute

        return {
            "total_requests": stats.request_count,
            "total_tokens": stats.token_count,
            "requests_per_minute": requests_per_minute,
            "tokens_per_minute": tokens_per_minute,
            "tokens_available": user_token_capacity,
            "last_request": stats.last_request_time,
            "conversation_counts": dict(stats.conversation_request_counts),
            "limits": {
                "per_user_rpm": self.config.per_user_rpm,
                "per_conversation_rpm": self.config.per_conversation_rpm,
                "per_user_tokens_per_minute": self.config.per_user_tokens_per_minute
            }
        }

    def reset_user_limits(self, user_id: str):
        """
        Reset rate limits for a specific user.

        Args:
            user_id: User identifier
        """
        if user_id in self.user_buckets:
            self.user_buckets[user_id].tokens = self.user_buckets[user_id].capacity

        if user_id in self.user_token_buckets:
            self.user_token_buckets[user_id].tokens = self.user_token_buckets[user_id].capacity

        # Clear conversation buckets for this user
        stats = self.usage_stats.get(user_id)
        if stats:
            for conv_id in stats.conversation_request_counts:
                if conv_id in self.conversation_buckets:
                    self.conversation_buckets[conv_id].tokens = \
                        self.conversation_buckets[conv_id].capacity

        logger.info(f"Reset rate limits for user {user_id}")

    def cleanup_idle_buckets(self, max_idle_seconds: int = 3600) -> int:
        """Remove idle user and conversation buckets and windows.

        Args:
            max_idle_seconds: Threshold of inactivity to purge entries

        Returns:
            Count of purged entries
        """
        cutoff = time.time() - max_idle_seconds
        removed = 0

        # Users
        for uid in list(self.usage_stats.keys()):
            last = self.usage_stats[uid].last_request_time or 0
            if last and last < cutoff:
                # Purge buckets and windows
                if uid in self.user_buckets:
                    del self.user_buckets[uid]
                if uid in self.user_token_buckets:
                    del self.user_token_buckets[uid]
                if uid in self.request_windows:
                    del self.request_windows[uid]
                del self.usage_stats[uid]
                removed += 1

        # Conversations
        # Remove conversation buckets with no recent activity based on any user's conversation counts
        active_conversations = set()
        for stats in self.usage_stats.values():
            for cid, _cnt in stats.conversation_request_counts.items():
                active_conversations.add(cid)
        for cid in list(self.conversation_buckets.keys()):
            if cid not in active_conversations:
                del self.conversation_buckets[cid]
                removed += 1

        if removed:
            logger.debug(f"ConversationRateLimiter cleanup removed {removed} idle entries")
        return removed


# Global rate limiter instance
_rate_limiter: Optional[ConversationRateLimiter] = None

def get_rate_limiter() -> Optional[ConversationRateLimiter]:
    """Get the global rate limiter instance."""
    return _rate_limiter

def initialize_rate_limiter(config: Optional[RateLimitConfig] = None) -> ConversationRateLimiter:
    """
    Initialize the global rate limiter.

    Args:
        config: Rate limit configuration (uses defaults if None)

    Returns:
        The initialized rate limiter
    """
    global _rate_limiter
    config = config or RateLimitConfig()
    # Test-mode overrides via environment for deterministic integration testing
    try:
        if os.getenv("TEST_MODE", "").lower() == "true":
            per_user = os.getenv("TEST_CHAT_PER_USER_RPM")
            per_conv = os.getenv("TEST_CHAT_PER_CONVERSATION_RPM")
            global_rpm = os.getenv("TEST_CHAT_GLOBAL_RPM")
            tokens_per_min = os.getenv("TEST_CHAT_TOKENS_PER_MINUTE")
            # Deterministic tests: disable burst by default in TEST_MODE unless explicitly overridden
            burst_mult = os.getenv("TEST_CHAT_BURST_MULTIPLIER")
            if per_user:
                config.per_user_rpm = max(1, int(per_user))
            if per_conv:
                config.per_conversation_rpm = max(1, int(per_conv))
            if global_rpm:
                config.global_rpm = max(1, int(global_rpm))
            if tokens_per_min:
                config.per_user_tokens_per_minute = max(1, int(tokens_per_min))
            # Default burst to 1.0 in TEST_MODE to make 429s deterministic on the N+1th call
            config.burst_multiplier = float(burst_mult) if burst_mult is not None else 1.0
    except Exception:
        # Ignore env parse errors and use defaults
        pass
    _rate_limiter = ConversationRateLimiter(config)
    return _rate_limiter
