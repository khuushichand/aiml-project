import warnings

import pytest

from tldw_Server_API.app.core.Embeddings import rate_limiter


@pytest.mark.asyncio
async def test_async_rate_limiter_allows_when_rg_disabled(monkeypatch):
    """Phase 2: RG disabled → fail-open (allow all) + deprecation warning."""
    limiter = rate_limiter.UserRateLimiter(
        default_limit=2,
        window_seconds=60,
        premium_limit=2,
    )
    async_limiter = rate_limiter.AsyncRateLimiter(rate_limiter=limiter)

    monkeypatch.setattr(rate_limiter, "_rg_embeddings_enabled", lambda: False)
    monkeypatch.setattr(rate_limiter, "_EMBEDDINGS_DEPRECATION_WARNED", False)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # All requests should be allowed (no counters in Phase 2 shim)
        for _ in range(5):
            allowed, retry_after = await async_limiter.check_rate_limit_async("user-1")
            assert allowed is True
            assert retry_after is None

        # Deprecation warning should have been emitted (at least once)
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1
        assert "Phase 2" in str(deprecation_warnings[0].message)


@pytest.mark.asyncio
async def test_async_rate_limiter_uses_rg_when_enabled(monkeypatch):
    limiter = rate_limiter.UserRateLimiter(
        default_limit=1,
        window_seconds=60,
        premium_limit=1,
    )
    async_limiter = rate_limiter.AsyncRateLimiter(rate_limiter=limiter)

    monkeypatch.setattr(rate_limiter, "_rg_embeddings_enabled", lambda: True)

    async def _fake_rg(*args, **kwargs):
        return {"allowed": False, "retry_after": 7, "policy_id": "test"}

    monkeypatch.setattr(rate_limiter, "_maybe_enforce_with_rg", _fake_rg)

    allowed, retry_after = await async_limiter.check_rate_limit_async("user-2")
    assert allowed is False
    assert retry_after == 7


@pytest.mark.asyncio
async def test_async_rate_limiter_allows_when_rg_unavailable(monkeypatch):
    """Phase 2: RG enabled but returns None → fail-open + deprecation warning."""
    async_limiter = rate_limiter.AsyncRateLimiter()

    monkeypatch.setattr(rate_limiter, "_rg_embeddings_enabled", lambda: True)
    monkeypatch.setattr(rate_limiter, "_rg_embeddings_fallback_logged", False)
    monkeypatch.setattr(rate_limiter, "_EMBEDDINGS_DEPRECATION_WARNED", False)

    async def _fake_rg(*args, **kwargs):
        return None

    monkeypatch.setattr(rate_limiter, "_maybe_enforce_with_rg", _fake_rg)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        allowed, retry_after = await async_limiter.check_rate_limit_async("user-3")
        assert allowed is True
        assert retry_after is None

        # Second call should also allow
        allowed, retry_after = await async_limiter.check_rate_limit_async("user-3")
        assert allowed is True
        assert retry_after is None

        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1
