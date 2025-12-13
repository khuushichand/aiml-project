import asyncio
import os

import pytest

from tldw_Server_API.app.core.MCP_unified.auth.rate_limiter import (
    RateLimitExceeded,
    RateLimiter,
    TokenBucketRateLimiter,
)
from tldw_Server_API.app.core.Embeddings import rate_limiter as emb_rl
from tldw_Server_API.app.core.MCP_unified.auth import rate_limiter as mcp_rl


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
        self.reserved.append((req.entity, req.categories, op_id))
        return _FakeDecision(self.allowed, self.retry_after), "handle-1"

    async def commit(self, handle_id, actuals=None, op_id=None):
        self.commits.append((handle_id, actuals, op_id))


@pytest.mark.asyncio
async def test_embeddings_rg_enforced_and_commits(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    fake = _FakeGovernor(allowed=True)
    monkeypatch.setattr(emb_rl, "_rg_embeddings_governor", fake)
    monkeypatch.setattr(emb_rl, "_rg_embeddings_loader", None)

    limiter = emb_rl.AsyncRateLimiter(rate_limiter=emb_rl.UserRateLimiter(default_limit=2, window_seconds=60))
    allowed, retry_after = await limiter.check_rate_limit_async("u123", tokens_units=7)

    assert allowed is True
    assert retry_after is None
    assert fake.reserved and fake.commits
    entity, categories, _ = fake.reserved[-1]
    assert entity == "user:u123"
    assert categories == {"tokens": {"units": 7}}


@pytest.mark.asyncio
async def test_mcp_rg_denies(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    fake = _FakeGovernor(allowed=False, retry_after=3)
    monkeypatch.setattr(mcp_rl, "_rg_mcp_governor", fake)
    monkeypatch.setattr(mcp_rl, "_rg_mcp_loader", None)

    limiter = RateLimiter()

    with pytest.raises(RateLimitExceeded) as exc:
        await limiter.check_rate_limit("client-abc", limiter=limiter.default_limiter)

    assert exc.value.retry_after == 3
    assert fake.reserved
    entity, categories, _ = fake.reserved[-1]
    assert entity == "client:client-abc"
    assert categories == {"requests": {"units": 1}}


class _SpyLimiter:
    def __init__(self, *, peek_allowed: bool = True):
        self.is_allowed_calls = 0
        self.peek_calls = 0
        self._peek_allowed = peek_allowed

    async def is_allowed(self, key: str) -> tuple[bool, int]:
        self.is_allowed_calls += 1
        return (True, 0)

    async def peek_allowed(self, key: str) -> tuple[bool, int]:
        self.peek_calls += 1
        return (self._peek_allowed, 0)


@pytest.mark.asyncio
async def test_mcp_shadow_compare_uses_peek_without_consuming(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    async def _fake_rg_decision(*, key: str, category: str):
        return {"allowed": True, "retry_after": None, "policy_id": f"mcp.{category}"}

    monkeypatch.setattr(mcp_rl, "_maybe_enforce_with_rg_mcp", _fake_rg_decision)

    limiter = RateLimiter()
    spy = _SpyLimiter(peek_allowed=True)

    await limiter.check_rate_limit("client-shadow", limiter=spy)

    assert spy.peek_calls == 1
    assert spy.is_allowed_calls == 0


@pytest.mark.asyncio
async def test_mcp_token_bucket_peek_allowed_is_side_effect_free():
    limiter = TokenBucketRateLimiter(rate=2, per=60, burst=2)
    key = "client-1"

    await limiter.is_allowed(key)

    allowance_before = dict(limiter.allowance)
    last_check_before = dict(limiter.last_check)

    await limiter.peek_allowed(key)

    assert limiter.allowance == allowance_before
    assert limiter.last_check == last_check_before

    await limiter.peek_allowed("new-key")
    assert limiter.allowance == allowance_before
    assert limiter.last_check == last_check_before
