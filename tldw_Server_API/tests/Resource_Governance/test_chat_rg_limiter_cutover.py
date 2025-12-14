import pytest

from tldw_Server_API.app.core.Chat.rate_limiter import ConversationRateLimiter, RateLimitConfig


pytestmark = pytest.mark.rate_limit


@pytest.mark.asyncio
async def test_chat_rate_limiter_uses_rg_decision_and_skips_legacy(monkeypatch):
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

    async def _legacy_should_not_run(*args: object, **kwargs: object):  # pragma: no cover
        raise AssertionError("legacy limiter should be bypassed when RG is enabled and returns a decision")

    monkeypatch.setattr(limiter, "_check_legacy_rate_limit", _legacy_should_not_run, raising=True)

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
async def test_chat_rate_limiter_is_noop_when_rg_disabled(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "0")

    async def fake_rg_chat(**_: object) -> None:
        return None

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

    async def _legacy_should_not_run(*args: object, **kwargs: object):  # pragma: no cover
        raise AssertionError("legacy limiter should not run when RG is disabled (no-op shim)")

    monkeypatch.setattr(limiter, "_check_legacy_rate_limit", _legacy_should_not_run, raising=True)

    allowed, error = await limiter.check_rate_limit(
        user_id="user-fallback",
        conversation_id="conv-fallback",
        estimated_tokens=0,
    )

    assert allowed is True
    assert error is None
