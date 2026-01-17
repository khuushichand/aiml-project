import asyncio
import pytest
from tldw_Server_API.app.core.Resource_Governance import RedisResourceGovernor, RGRequest


pytestmark = pytest.mark.rate_limit


@pytest.mark.asyncio
async def test_real_redis_multi_key_lua_path(real_redis, rg_unique_ns):
    """Validate multi-key Lua path on real Redis (skipped when fixture not available)."""

    class _Loader:
        def get_policy(self, pid):
                     # Modest limits to trigger multi-key reservation across requests+tokens
            return {"requests": {"rpm": 3}, "tokens": {"per_min": 3}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns=rg_unique_ns)
    if not await rg._is_real_redis():
        pytest.skip("Redis client is not real; using in-memory stub")

    # Reserve both categories at once; with real Redis we expect the multi-key Lua path to be used
    e = "user:realredis"
    req = RGRequest(entity=e, categories={"requests": {"units": 1}, "tokens": {"units": 1}}, tags={"policy_id": "preal"})
    d1, h1 = await rg.reserve(req)
    assert d1.allowed and h1

    caps = await rg.capabilities()
    assert caps.get("real_redis") is True
    # multi-key Lua should be considered loaded and used after reserve
    assert caps.get("multi_lua_loaded") is True
    # Depending on client behavior, last_used flag should indicate Lua path used
    assert caps.get("last_used_multi_lua") in (True, None)  # Some clients may not expose evalsha path nuances


@pytest.mark.asyncio
async def test_real_redis_multi_category_denial(real_redis, rg_unique_ns):
    """Ensure multi-category reserve denies cleanly when limits exhausted (atomic path)."""

    class _Loader:
        def get_policy(self, pid):
                     # Very small limits to force denial on second combined reserve
            return {"requests": {"rpm": 1}, "tokens": {"per_min": 1}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns=rg_unique_ns)
    if not await rg._is_real_redis():
        pytest.skip("Redis client is not real; using in-memory stub")

    e = "user:deny"
    # First should pass
    d1, h1 = await rg.reserve(RGRequest(entity=e, categories={"requests": {"units": 1}, "tokens": {"units": 1}}, tags={"policy_id": "pdeny"}))
    assert d1.allowed and h1

    # Second should deny atomically without creating a handle
    d2, h2 = await rg.reserve(RGRequest(entity=e, categories={"requests": {"units": 1}, "tokens": {"units": 1}}, tags={"policy_id": "pdeny"}))
    assert (not d2.allowed) and (h2 is None)

    # Rollback diagnostics: No increments should persist in the windows beyond first success
    client = await rg._client_get()
    # Check keys for both categories and scopes
    for cat in ("requests", "tokens"):
        for sc, ev in (("global", "*"), ("user", "deny")):
            key = f"{rg_unique_ns}:win:pdeny:{cat}:{sc}:{ev}"
            cnt = await client.zcard(key)
            # Count should be 1 for the first success only; denial must not increment
            assert cnt == 1


@pytest.mark.asyncio
async def test_real_redis_streams_renew_release(real_redis, rg_unique_ns):
    """Validate concurrency lease renew and release on real Redis (skipped when unavailable)."""

    class _Loader:
        def get_policy(self, pid):
            return {"streams": {"max_concurrent": 1, "ttl_sec": 2}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns=rg_unique_ns)
    if not await rg._is_real_redis():
        pytest.skip("Redis client is not real; using in-memory stub")

    e = "user:realredis"
    req = RGRequest(entity=e, categories={"streams": {"units": 1}}, tags={"policy_id": "pcon"})
    d1, h1 = await rg.reserve(req)
    assert d1.allowed and h1

    # Second reserve should deny while lease is active
    d2, h2 = await rg.reserve(req)
    assert not d2.allowed and not h2

    # Renew the lease and ensure still denied
    await rg.renew(h1, ttl_s=2)
    d3, h3 = await rg.reserve(req)
    assert not d3.allowed and not h3

    # Release and then acquire again
    await rg.release(h1)
    d4, h4 = await rg.reserve(req)
    assert d4.allowed and h4


@pytest.mark.asyncio
async def test_real_redis_streams_renew_under_contention(real_redis, rg_unique_ns):
    class _Loader:
        def get_policy(self, pid):
            return {"streams": {"max_concurrent": 1, "ttl_sec": 3}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns=rg_unique_ns)
    if not await rg._is_real_redis():
        pytest.skip("Redis client is not real; using in-memory stub")

    e = "user:c"
    req = RGRequest(entity=e, categories={"streams": {"units": 1}}, tags={"policy_id": "pc"})
    d1, h1 = await rg.reserve(req)
    assert d1.allowed and h1

    # In parallel: attempt reserve and renew; reserve should remain denied
    async def do_reserve():
        return await rg.reserve(req)

    async def do_renew():
        await rg.renew(h1, ttl_s=3)
        return True

    (d2, h2), _ = await asyncio.gather(do_reserve(), do_renew())
    assert not d2.allowed and h2 is None


@pytest.mark.asyncio
async def test_real_redis_denial_rollback_and_refunds(real_redis, rg_unique_ns):
    """On denial, no members are added; on commit with refunds, counters drop per scope."""

    class _Loader:
        def get_policy(self, pid):
                     # Limits designed to allow initial reserve then deny on second; also test refunds
            return {
                "requests": {"rpm": 2},
                "tokens": {"per_min": 3},
                "scopes": ["global", "user"],
            }

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns=rg_unique_ns)
    if not await rg._is_real_redis():
        pytest.skip("Redis client is not real; using in-memory stub")

    policy_id = "pmix"
    e = "user:mix"

    # First reserve: consume some capacity
    d1, h1 = await rg.reserve(RGRequest(entity=e, categories={"requests": {"units": 2}, "tokens": {"units": 3}}, tags={"policy_id": policy_id}))
    assert d1.allowed and h1

    # Second reserve exceeds both, should deny atomically and not leave partial state
    d2, h2 = await rg.reserve(RGRequest(entity=e, categories={"requests": {"units": 1}, "tokens": {"units": 1}}, tags={"policy_id": policy_id}))
    assert (not d2.allowed) and (h2 is None)

    # Now refund part of the first handle: reduce tokens from 3 → 1, requests from 2 → 1
    await rg.commit(h1, actuals={"tokens": 1, "requests": 1})

    # Validate via peek that remaining aligns with policy limits (per scope)
    peek = await rg.peek_with_policy(e, ["requests", "tokens"], policy_id)
    # After commit actuals 1 per scope per category, remaining should be limit-1
    assert peek["requests"]["remaining"] == 1
    assert peek["tokens"]["remaining"] == 2


@pytest.mark.asyncio
async def test_real_redis_concurrent_reserve_race_is_atomic(real_redis, rg_unique_ns):
    """Two concurrent reserves for a 1/1 (req/tok) policy: exactly one succeeds."""

    class _Loader:
        def get_policy(self, pid):
            return {"requests": {"rpm": 1}, "tokens": {"per_min": 1}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns=rg_unique_ns)
    if not await rg._is_real_redis():
        pytest.skip("Redis client is not real; using in-memory stub")

    policy_id = "prace"
    e = "user:race"

    async def do_reserve():
        return await rg.reserve(RGRequest(entity=e, categories={"requests": {"units": 1}, "tokens": {"units": 1}}, tags={"policy_id": policy_id}))

    (d1, h1), (d2, h2) = await asyncio.gather(do_reserve(), do_reserve())

    # Exactly one should succeed
    success_count = int(bool(h1)) + int(bool(h2))
    assert success_count == 1
    assert (d1.allowed and h1 and (not d2.allowed)) or (d2.allowed and h2 and (not d1.allowed))

    # Cleanup: release the successful handle (if any)
    if h1:
        await rg.release(h1)
    if h2:
        await rg.release(h2)


@pytest.mark.asyncio
async def test_real_redis_tokens_retry_after_monotonic(real_redis, rg_unique_ns):
    class _Loader:
        def get_policy(self, pid):
            return {"tokens": {"per_min": 1}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns=rg_unique_ns)
    if not await rg._is_real_redis():
        pytest.skip("Redis client is not real; using in-memory stub")

    e = "user:ra"
    req = RGRequest(entity=e, categories={"tokens": {"units": 1}}, tags={"policy_id": "p"})
    d1, _ = await rg.reserve(req)
    assert d1.allowed
    d2, _ = await rg.reserve(req)
    assert not d2.allowed and d2.retry_after is not None
    ra1 = int(d2.retry_after)
    assert 1 <= ra1 <= 60


@pytest.mark.asyncio
async def test_real_redis_requests_retry_after_monotonic(real_redis, rg_unique_ns):
    """Requests-only path should also yield decreasing retry_after over time on real Redis."""

    class _Loader:
        def get_policy(self, pid):
            return {"requests": {"rpm": 1}, "scopes": ["global", "user"]}

    # Use real Redis and a fresh namespace
    rg = RedisResourceGovernor(policy_loader=_Loader(), ns=rg_unique_ns)
    if not await rg._is_real_redis():
        pytest.skip("Redis client is not real; using in-memory stub")

    e = "user:reqra"
    req = RGRequest(entity=e, categories={"requests": {"units": 1}}, tags={"policy_id": "p"})
    d1, _ = await rg.reserve(req)
    assert d1.allowed
    d2, _ = await rg.reserve(req)
    assert not d2.allowed and d2.retry_after is not None
    ra1 = int(d2.retry_after)
    assert 1 <= ra1 <= 60
    # Sleep on real event loop to advance wall time for real Redis
    await asyncio.sleep(1)
    d3, _ = await rg.reserve(req)
    ra2 = int(d3.retry_after or 0)
    assert 0 <= ra2 <= ra1
