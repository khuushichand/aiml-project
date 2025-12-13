import asyncio
import os
import time

import pytest

from tldw_Server_API.app.core.AuthNZ import rate_limiter as auth_rl
from tldw_Server_API.app.core.Character_Chat import character_rate_limiter as char_rl
from tldw_Server_API.app.core.Evaluations import user_rate_limiter as evals_rl
from tldw_Server_API.app.core.Web_Scraping import enhanced_web_scraping as web_rl


class _FakeDecision:
    def __init__(self, allowed: bool, retry_after: int | None = None):
        self.allowed = allowed
        self.retry_after = retry_after
        self.details = {}


class _FakeGovernor:
    def __init__(self, allowed: bool = True, retry_after: int | None = None):
        self.allowed = allowed
        self.retry_after = retry_after
        self.reserved = []
        self.commits = []

    async def reserve(self, req, op_id=None):
        self.reserved.append((req.entity, req.categories, op_id, req.tags))
        return _FakeDecision(self.allowed, self.retry_after), "handle-1"

    async def commit(self, handle_id, actuals=None, op_id=None):
        self.commits.append((handle_id, actuals, op_id))


@pytest.mark.asyncio
async def test_evaluations_rg_denies(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    fake = _FakeGovernor(allowed=False, retry_after=5)
    monkeypatch.setattr(evals_rl, "_rg_evals_governor", fake)
    monkeypatch.setattr(evals_rl, "_rg_evals_loader", None)

    limiter = evals_rl.UserRateLimiter()

    allowed, meta = await limiter.check_rate_limit(
        user_id="user-123",
        endpoint="/api/v1/evaluations",
    )

    assert allowed is False
    assert meta.get("retry_after") == 5
    assert meta.get("policy_id") == "evals.default"
    assert fake.reserved
    entity, categories, _op_id, tags = fake.reserved[-1]
    assert entity == "user:user-123"
    assert categories == {"evaluations": {"units": 1}}
    assert tags.get("module") == "evaluations"


@pytest.mark.asyncio
async def test_evaluations_rg_allows_bypasses_legacy_denies(monkeypatch):
    """
    When RG returns an allow decision, Evaluations must not deny based on the
    legacy per-minute/daily checks. Those legacy checks are treated as
    shadow-only (drift signals).
    """
    monkeypatch.setenv("RG_ENABLED", "1")
    fake = _FakeGovernor(allowed=True, retry_after=None)
    monkeypatch.setattr(evals_rl, "_rg_evals_governor", fake)
    monkeypatch.setattr(evals_rl, "_rg_evals_loader", None)

    limiter = evals_rl.UserRateLimiter()

    async def _deny_minute(*args, **kwargs):  # noqa: ARG001
        return False, {"error": "legacy minute deny"}

    async def _deny_daily(*args, **kwargs):  # noqa: ARG001
        return False, {"error": "legacy daily deny"}

    monkeypatch.setattr(limiter, "_check_minute_limit", _deny_minute)
    monkeypatch.setattr(limiter, "_check_daily_limits", _deny_daily)

    allowed, meta = await limiter.check_rate_limit(
        user_id="user-123",
        endpoint="/api/v1/evaluations",
        tokens_requested=123,
        estimated_cost=0.0,
    )

    assert allowed is True
    assert meta.get("policy_id") == "evals.default"
    assert meta.get("rate_limit_source") == "resource_governor"


@pytest.mark.asyncio
async def test_authnz_rg_denies(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    fake = _FakeGovernor(allowed=False, retry_after=7)
    monkeypatch.setattr(auth_rl, "_rg_authnz_governor", fake)
    monkeypatch.setattr(auth_rl, "_rg_authnz_loader", None)

    limiter = auth_rl.RateLimiter()
    # Use a small explicit limit to keep legacy path simple; RG denial should take precedence.
    allowed, meta = await limiter.check_rate_limit(
        identifier="user:42",
        endpoint="/api/v1/auth/login",
        limit=10,
    )

    assert allowed is False
    assert meta.get("retry_after") == 7
    assert meta.get("policy_id") == "authnz.default"
    assert fake.reserved
    entity, categories, _op_id, tags = fake.reserved[-1]
    assert entity == "user:42"
    assert categories == {"requests": {"units": 1}}
    assert tags.get("module") == "authnz"
    assert tags.get("endpoint") == "/api/v1/auth/login"


@pytest.mark.asyncio
async def test_authnz_rg_allows_bypasses_legacy_denies(monkeypatch):
    """
    When RG returns an allow decision, AuthNZ must not deny (or consume counters)
    via the legacy DB/Redis rate limiter. Legacy behavior is shadow-only.
    """
    monkeypatch.setenv("RG_ENABLED", "1")
    monkeypatch.setenv("RG_SHADOW_AUTHNZ", "0")  # avoid backend peeks in this unit test
    fake = _FakeGovernor(allowed=True, retry_after=None)
    monkeypatch.setattr(auth_rl, "_rg_authnz_governor", fake)
    monkeypatch.setattr(auth_rl, "_rg_authnz_loader", None)

    limiter = auth_rl.RateLimiter()

    async def _boom(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("legacy limiter should not run when RG is available")

    monkeypatch.setattr(limiter, "_check_redis_rate_limit", _boom)
    monkeypatch.setattr(limiter, "_check_database_rate_limit", _boom)

    allowed, meta = await limiter.check_rate_limit(
        identifier="user:42",
        endpoint="/api/v1/auth/login",
        limit=10,
    )

    assert allowed is True
    assert meta.get("policy_id") == "authnz.default"
    assert meta.get("rate_limit_source") == "resource_governor"


@pytest.mark.asyncio
async def test_character_chat_rg_denies(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    fake = _FakeGovernor(allowed=False, retry_after=3)
    monkeypatch.setattr(char_rl, "_rg_char_governor", fake)
    monkeypatch.setattr(char_rl, "_rg_char_loader", None)

    limiter = char_rl.CharacterRateLimiter(redis_client=None, max_operations=100)

    with pytest.raises(Exception) as exc:
        await limiter.check_rate_limit(user_id=123, operation="character_op")

    assert "Rate limit exceeded" in str(exc.value)
    assert fake.reserved
    entity, categories, _op_id, tags = fake.reserved[-1]
    assert entity == "user:123"
    assert categories == {"requests": {"units": 1}}
    assert tags.get("module") == "character_chat"
    assert tags.get("operation") == "character_op"


@pytest.mark.asyncio
async def test_character_chat_rg_allows_bypasses_legacy_denies(monkeypatch):
    """
    When RG returns an allow decision, Character Chat must not deny (or consume
    counters) via the legacy limiter.
    """
    monkeypatch.setenv("RG_ENABLED", "1")
    fake = _FakeGovernor(allowed=True, retry_after=None)
    monkeypatch.setattr(char_rl, "_rg_char_governor", fake)
    monkeypatch.setattr(char_rl, "_rg_char_loader", None)

    limiter = char_rl.CharacterRateLimiter(redis_client=None, max_operations=1, window_seconds=3600)
    # Prime memory store to force legacy deny if it were consulted.
    limiter.memory_store[123] = [time.time()]

    allowed, remaining = await limiter.check_rate_limit(user_id=123, operation="character_op")

    assert allowed is True
    assert isinstance(remaining, int)


@pytest.mark.asyncio
async def test_web_scraping_rg_denies(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    fake = _FakeGovernor(allowed=False, retry_after=1)
    monkeypatch.setattr(web_rl, "_rg_web_governor", fake)
    monkeypatch.setattr(web_rl, "_rg_web_loader", None)

    limiter = web_rl.RateLimiter(max_requests_per_second=100.0, max_requests_per_minute=1000, max_requests_per_hour=1000)

    # Ensure acquire completes quickly despite the artificial sleep; monkeypatch time if needed.
    start = asyncio.get_event_loop().time()
    await limiter.acquire()
    elapsed = asyncio.get_event_loop().time() - start

    assert fake.reserved
    entity, categories, _op_id, tags = fake.reserved[-1]
    assert entity == "service:web_scraping"
    assert categories == {"requests": {"units": 1}}
    assert tags.get("module") == "web_scraping"
    # We do not assert strict timing here to avoid flakiness, just that the call returned.
