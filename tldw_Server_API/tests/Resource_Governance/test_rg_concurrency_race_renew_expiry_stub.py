import asyncio
import pytest

pytestmark = pytest.mark.rate_limit

from tldw_Server_API.app.core.Resource_Governance import RedisResourceGovernor, RGRequest


class FakeTime:
    def __init__(self, t0: float = 0.0):
        self.t = t0

    def __call__(self) -> float:

             return self.t

    def advance(self, s: float) -> None:
        self.t += s


@pytest.mark.asyncio
async def test_concurrency_race_renew_and_ttl_expiry_behavior():
    class _Loader:
        def get_policy(self, pid):
                     # Short TTL to exercise expiry without release
            return {"streams": {"max_concurrent": 1, "ttl_sec": 3}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_c_stub"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    e = "user:cstub"
    req = RGRequest(entity=e, categories={"streams": {"units": 1}}, tags={"policy_id": "p"})

    # First acquire succeeds
    d1, h1 = await rg.reserve(req)
    assert d1.allowed and h1

    # Parallel reserve while held must deny
    d2, h2 = await rg.reserve(req)
    assert (not d2.allowed) and (h2 is None)

    # Renew keeps denial
    await rg.renew(h1, ttl_s=3)
    d3, h3 = await rg.reserve(req)
    assert (not d3.allowed) and (h3 is None)

    # Advance FakeTime beyond TTL → capacity should be freed automatically (stub TTL GC)
    ft.advance(4.0)
    d4, h4 = await rg.reserve(req)
    assert d4.allowed and h4
