import pytest

from tldw_Server_API.app.core.Embeddings import rate_limiter


@pytest.mark.asyncio
async def test_async_rate_limiter_falls_back_when_rg_disabled(monkeypatch):
    limiter = rate_limiter.UserRateLimiter(
        default_limit=2,
        window_seconds=60,
        premium_limit=2,
    )
    async_limiter = rate_limiter.AsyncRateLimiter(rate_limiter=limiter)

    monkeypatch.setattr(rate_limiter, "_rg_embeddings_enabled", lambda: False)

    allowed, retry_after = await async_limiter.check_rate_limit_async("user-1")
    assert allowed is True
    assert retry_after is None

    allowed, retry_after = await async_limiter.check_rate_limit_async("user-1")
    assert allowed is True
    assert retry_after is None

    allowed, retry_after = await async_limiter.check_rate_limit_async("user-1")
    assert allowed is True
    assert retry_after is None

    allowed, retry_after = await async_limiter.check_rate_limit_async("user-1")
    assert allowed is False
    assert retry_after is not None


@pytest.mark.asyncio
async def test_async_rate_limiter_uses_token_cost_when_rg_disabled(monkeypatch):
    limiter = rate_limiter.UserRateLimiter(
        default_limit=3,
        window_seconds=60,
        premium_limit=3,
        burst_allowance=1.0,
    )
    async_limiter = rate_limiter.AsyncRateLimiter(rate_limiter=limiter)

    monkeypatch.setattr(rate_limiter, "_rg_embeddings_enabled", lambda: False)

    allowed, retry_after = await async_limiter.check_rate_limit_async(
        "user-1",
        tokens_units=2,
    )
    assert allowed is True
    assert retry_after is None

    allowed, retry_after = await async_limiter.check_rate_limit_async(
        "user-1",
        tokens_units=2,
    )
    assert allowed is False
    assert retry_after is not None

@pytest.mark.asyncio
async def test_async_rate_limiter_uses_rg_when_enabled(monkeypatch):
    limiter = rate_limiter.UserRateLimiter(
        default_limit=1,
        window_seconds=60,
        premium_limit=1,
    )
    async_limiter = rate_limiter.AsyncRateLimiter(rate_limiter=limiter)
    async_limiter.shadow_enabled = False

    monkeypatch.setattr(rate_limiter, "_rg_embeddings_enabled", lambda: True)

    async def _fake_rg(*args, **kwargs):
        return {"allowed": False, "retry_after": 7, "policy_id": "test"}

    monkeypatch.setattr(rate_limiter, "_maybe_enforce_with_rg", _fake_rg)

    def _legacy_called(*args, **kwargs):

        raise AssertionError("legacy limiter should not be called when RG is enabled")

    monkeypatch.setattr(limiter, "check_rate_limit", _legacy_called)

    allowed, retry_after = await async_limiter.check_rate_limit_async("user-2")
    assert allowed is False
    assert retry_after == 7


@pytest.mark.asyncio
async def test_async_rate_limiter_falls_back_when_rg_unavailable(monkeypatch):
    limiter = rate_limiter.UserRateLimiter(
        default_limit=1,
        window_seconds=60,
        premium_limit=1,
    )
    async_limiter = rate_limiter.AsyncRateLimiter(rate_limiter=limiter)
    async_limiter.shadow_enabled = False

    monkeypatch.setattr(rate_limiter, "_rg_embeddings_enabled", lambda: True)

    async def _fake_rg(*args, **kwargs):
        return None

    monkeypatch.setattr(rate_limiter, "_maybe_enforce_with_rg", _fake_rg)

    calls = []
    original = limiter.check_rate_limit

    def _wrapped(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(limiter, "check_rate_limit", _wrapped)

    allowed, retry_after = await async_limiter.check_rate_limit_async("user-3")
    assert allowed is True
    assert retry_after is None

    allowed, retry_after = await async_limiter.check_rate_limit_async("user-3")
    assert allowed is False
    assert retry_after is not None
    assert len(calls) >= 2
