import pytest

pytestmark = pytest.mark.rate_limit

from tldw_Server_API.app.core.Resource_Governance import RedisResourceGovernor, RGRequest


class _BrokenClient:
    async def evalsha(self, *a, **k):
        raise RuntimeError("boom")
    async def script_load(self, *a, **k):
        raise RuntimeError("boom")
    async def zadd(self, *a, **k):
        raise RuntimeError("boom")
    async def zremrangebyscore(self, *a, **k):
        raise RuntimeError("boom")
    async def zcard(self, *a, **k):
        raise RuntimeError("boom")
    async def set(self, *a, **k):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_fail_open_tokens_allows_on_error(monkeypatch):
    class _Loader:
        def get_policy(self, pid):
                     return {"tokens": {"per_min": 1, "fail_mode": "fail_open"}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns="rg_fail_open")

    async def _broken():
        return _BrokenClient()

    monkeypatch.setattr(rg, "_client_get", _broken)
    d, h = await rg.reserve(RGRequest(entity="user:x", categories={"tokens": {"units": 1}}, tags={"policy_id": "p"}))
    assert d.allowed and h


@pytest.mark.asyncio
async def test_fail_closed_requests_denies_on_error(monkeypatch):
    class _Loader:
        def get_policy(self, pid):
                     return {"requests": {"rpm": 1, "fail_mode": "fail_closed"}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns="rg_fail_closed")

    async def _broken():
        return _BrokenClient()

    monkeypatch.setattr(rg, "_client_get", _broken)
    d, h = await rg.reserve(RGRequest(entity="user:x", categories={"requests": {"units": 1}}, tags={"policy_id": "p"}))
    assert (not d.allowed) and (h is None)


@pytest.mark.asyncio
async def test_fallback_memory_requests_allows_when_redis_broken(monkeypatch):
    class _Loader:
        def get_policy(self, pid):
                     return {"requests": {"rpm": 1, "fail_mode": "fallback_memory"}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns="rg_fallback_mem")

    async def _broken():
        return _BrokenClient()

    monkeypatch.setattr(rg, "_client_get", _broken)
    req = RGRequest(entity="user:x", categories={"requests": {"units": 1}}, tags={"policy_id": "p"})
    d1, h1 = await rg.reserve(req, op_id="f1")
    assert d1.allowed and h1
    d2, h2 = await rg.reserve(req, op_id="f2")
    # Memory fallback should enforce rpm=1
    assert (not d2.allowed) and (h2 is None)
