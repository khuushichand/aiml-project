import time
import pytest

from tldw_Server_API.app.core.Chat.rate_limiter import (
    ConversationRateLimiter,
    RateLimitConfig,
)


@pytest.mark.unit
def test_idle_cleanup_removes_stale_entries():
    cfg = RateLimitConfig(
        global_rpm=60,
        per_user_rpm=10,
        per_conversation_rpm=5,
        per_user_tokens_per_minute=1000,
        burst_multiplier=1.0,
    )
    limiter = ConversationRateLimiter(cfg)

    # Simulate activity for user and conversation
    uid = "user-abc"
    cid_active = "conv-active"
    cid_stale = "conv-stale"

    # Touch buckets
    limiter.user_buckets[uid] = limiter._get_or_create_bucket(limiter.user_buckets, uid, 10, cfg.per_user_rpm / 60)
    limiter.user_token_buckets[uid] = limiter._get_or_create_bucket(
        limiter.user_token_buckets, uid, 1000, cfg.per_user_tokens_per_minute / 60
    )
    limiter.conversation_buckets[cid_active] = limiter._get_or_create_bucket(
        limiter.conversation_buckets, cid_active, 5, cfg.per_conversation_rpm / 60
    )
    # Create a stale conversation bucket with no references in usage_stats
    limiter.conversation_buckets[cid_stale] = limiter._get_or_create_bucket(
        limiter.conversation_buckets, cid_stale, 5, cfg.per_conversation_rpm / 60
    )

    # Mark user usage as recent so user is retained
    limiter.usage_stats[uid].last_request_time = time.time()
    limiter.request_windows[uid].append((time.time(), 0))
    # Mark this conversation as active in stats mapping so it won't be removed
    limiter.usage_stats[uid].conversation_request_counts[cid_active] = 1

    # Cleanup entries idle more than 1 second
    removed = limiter.cleanup_idle_buckets(max_idle_seconds=1)
    assert removed == 1  # stale conversation removed; user retained

    # User-specific structures retained (user is active)
    assert uid in limiter.user_buckets
    assert uid in limiter.user_token_buckets
    assert uid in limiter.request_windows
    assert uid in limiter.usage_stats

    # Stale conversation removed; active remains
    assert cid_stale not in limiter.conversation_buckets
    assert cid_active in limiter.conversation_buckets
