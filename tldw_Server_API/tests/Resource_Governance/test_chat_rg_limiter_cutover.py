import warnings

import pytest

from tldw_Server_API.app.core.Chat import rate_limiter as chat_rl
from tldw_Server_API.app.core.Chat.rate_limiter import ConversationRateLimiter, RateLimitConfig


pytestmark = pytest.mark.rate_limit


@pytest.mark.asyncio
async def test_chat_rate_limiter_uses_rg_decision(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")

    async def fake_rg_chat(**_: object) -> dict[str, object]:
        return {"allowed": False, "policy_id": "chat.test", "retry_after": 2}

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.rate_limiter._maybe_enforce_with_rg_chat",
        fake_rg_chat,
        raising=False,
    )

    limiter = ConversationRateLimiter(
        RateLimitConfig(
            global_rpm=100,
            per_user_rpm=100,
            per_conversation_rpm=100,
            per_user_tokens_per_minute=100000,
            burst_multiplier=1.0,
        )
    )

    allowed, error = await limiter.check_rate_limit(
        user_id="user-primary",
        conversation_id="conv-primary",
        estimated_tokens=10,
    )

    assert allowed is False
    assert error is not None
    assert "ResourceGovernor policy=chat.test" in error
    assert "retry_after=2s" in error


@pytest.mark.asyncio
async def test_chat_rate_limiter_fail_open_when_rg_disabled(monkeypatch):
    """Phase 2: RG disabled → fail-open with deprecation warning."""
    monkeypatch.setenv("RG_ENABLED", "0")
    monkeypatch.setattr(chat_rl, "_CHAT_DEPRECATION_WARNED", False)

    limiter = ConversationRateLimiter(
        RateLimitConfig(
            global_rpm=1,
            per_user_rpm=1,
            per_conversation_rpm=1,
            per_user_tokens_per_minute=1,
            burst_multiplier=1.0,
        )
    )

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Even with very low limits, Phase 2 shim fails open
        for _ in range(5):
            allowed, error = await limiter.check_rate_limit(
                user_id="user-fallback",
                conversation_id="conv-fallback",
                estimated_tokens=0,
            )
            assert allowed is True
            assert error is None

        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1


@pytest.mark.asyncio
async def test_chat_rate_limiter_rg_unavailable_fail_open(monkeypatch):
    """Phase 2: RG enabled but returns None → fail-open with deprecation warning."""
    monkeypatch.setenv("RG_ENABLED", "1")
    monkeypatch.setattr(chat_rl, "_rg_chat_fallback_logged", False)
    monkeypatch.setattr(chat_rl, "_CHAT_DEPRECATION_WARNED", False)

    async def fake_rg_chat(**_: object) -> None:
        return None

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.rate_limiter._maybe_enforce_with_rg_chat",
        fake_rg_chat,
        raising=False,
    )

    limiter = ConversationRateLimiter(
        RateLimitConfig(
            global_rpm=1,
            per_user_rpm=1,
            per_conversation_rpm=1,
            per_user_tokens_per_minute=1,
            burst_multiplier=1.0,
        )
    )

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        allowed, error = await limiter.check_rate_limit(
            user_id="user-diagnostics",
            conversation_id="conv-diagnostics",
            estimated_tokens=10,
        )

        assert allowed is True
        assert error is None

        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1
