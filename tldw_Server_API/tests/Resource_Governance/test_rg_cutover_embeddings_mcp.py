import asyncio
import os
from collections import deque

import pytest

from tldw_Server_API.app.core.MCP_unified.auth.rate_limiter import (
    RateLimitExceeded,
    RateLimiter,
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
async def test_embeddings_shadow_does_not_mutate_legacy_enforcement_state(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    monkeypatch.setenv("RG_SHADOW_EMBEDDINGS", "1")
    fake = _FakeGovernor(allowed=True)
    monkeypatch.setattr(emb_rl, "_rg_embeddings_governor", fake)
    monkeypatch.setattr(emb_rl, "_rg_embeddings_loader", None)

    legacy = emb_rl.UserRateLimiter(default_limit=2, window_seconds=60)
    limiter = emb_rl.AsyncRateLimiter(rate_limiter=legacy)

    assert len(legacy.user_requests.get("u123", deque())) == 0

    allowed, retry_after = await limiter.check_rate_limit_async("u123", tokens_units=7)
    assert allowed is True
    assert retry_after is None

    # RG-first means the legacy enforcement queue should not be consumed.
    assert len(legacy.user_requests.get("u123", deque())) == 0
    # Shadow comparisons should track their own queue for drift metrics.
    shadow_store = getattr(legacy, "_shadow_user_requests", {})
    assert len(shadow_store.get("u123", deque())) == 1


@pytest.mark.asyncio
async def test_mcp_rg_denies(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    fake = _FakeGovernor(allowed=False, retry_after=3)
    monkeypatch.setattr(mcp_rl, "_rg_mcp_governor", fake)
    monkeypatch.setattr(mcp_rl, "_rg_mcp_loader", None)

    limiter = RateLimiter()

    with pytest.raises(RateLimitExceeded) as exc:
        await limiter.check_rate_limit("client-abc", category="default")

    assert exc.value.retry_after == 3
    assert fake.reserved
    entity, categories, _ = fake.reserved[-1]
    assert entity == "client:client-abc"
    assert categories == {"requests": {"units": 1}}
