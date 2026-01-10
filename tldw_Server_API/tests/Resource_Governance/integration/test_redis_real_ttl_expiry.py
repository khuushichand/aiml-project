import asyncio
import pytest

pytestmark = pytest.mark.rate_limit

from tldw_Server_API.app.core.Resource_Governance import RedisResourceGovernor, RGRequest


@pytest.mark.asyncio
async def test_real_redis_streams_ttl_expiry_allows_later(real_redis, rg_unique_ns):
    """Acquire a lease with a short TTL and ensure capacity becomes available
    again after TTL expiry without an explicit release.

    Skips when real Redis is unavailable.
    """

    class _Loader:
        def get_policy(self, pid):
            return {"streams": {"max_concurrent": 1, "ttl_sec": 2}, "scopes": ["global", "user"]}

    rg = RedisResourceGovernor(policy_loader=_Loader(), ns=rg_unique_ns)
    if not await rg._is_real_redis():
        pytest.skip("Redis client is not real; using in-memory stub")

    e = "user:ttl"
    req = RGRequest(entity=e, categories={"streams": {"units": 1}}, tags={"policy_id": "pcon"})

    # Reserve once
    d1, h1 = await rg.reserve(req)
    assert d1.allowed and h1

    # While active, deny
    d2, h2 = await rg.reserve(req)
    assert (not d2.allowed) and (h2 is None)

    # Wait past TTL and try again
    await asyncio.sleep(3)
    d3, h3 = await rg.reserve(req)
    assert d3.allowed and h3
