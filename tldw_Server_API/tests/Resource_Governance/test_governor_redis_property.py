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
async def test_atomic_multi_category_rollback_on_denial():
    class _Loader:
        def get_policy(self, pid):
            # requests allow 1 per minute; tokens deny (0) -> overall must deny and requests should not be incremented
            return {"requests": {"rpm": 1}, "tokens": {"per_min": 0}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_atomic"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    client = await rg._client_get()

    # Cleanup keys
    for pat in (f"{ns}:win:p:requests*", f"{ns}:win:p:tokens*"):
        try:
            _cur, keys = await client.scan(match=pat)
            for k in keys:
                await client.delete(k)
        except Exception:
            pass

    req = RGRequest(entity="user:1", categories={"requests": {"units": 1}, "tokens": {"units": 1}}, tags={"policy_id": "p"})
    dec, hid = await rg.reserve(req)
    assert not dec.allowed and hid is None

    # Ensure no increments occurred for requests key either (atomic rollback)
    cnt = await client.zcard(f"{ns}:win:p:requests:global:*")
    assert cnt == 0


@pytest.mark.asyncio
async def test_retry_after_decreases_with_time_for_tokens():
    class _Loader:
        def get_policy(self, pid):
            return {"tokens": {"per_min": 1, "burst": 1.0}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_ra"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    req = RGRequest(entity="user:x", categories={"tokens": {"units": 1}}, tags={"policy_id": "p"})
    d1, _ = await rg.reserve(req)
    assert d1.allowed
    d2, _ = await rg.reserve(req)
    assert not d2.allowed and d2.retry_after is not None
    ra1 = int(d2.retry_after)
    assert ra1 >= 50  # roughly a minute
    ft.advance(30)
    d3, _ = await rg.reserve(req)
    ra2 = int(d3.retry_after or 0)
    assert ra2 <= ra1 and ra2 > 0
    ft.advance(31)
    d4, _ = await rg.reserve(req)
    assert d4.allowed


@pytest.mark.asyncio
async def test_token_refund_allows_subsequent_requests():
    class _Loader:
        def get_policy(self, pid):
            return {"tokens": {"per_min": 2, "burst": 1.0}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_refund"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    req = RGRequest(entity="user:tok", categories={"tokens": {"units": 2}}, tags={"policy_id": "p"})
    d, h = await rg.reserve(req)
    assert d.allowed and h

    # Commit only 1 used -> refund 1 unit
    await rg.commit(h, actuals={"tokens": 1})

    # We should be able to reserve one more immediately within the window
    d2, h2 = await rg.reserve(RGRequest(entity="user:tok", categories={"tokens": {"units": 1}}, tags={"policy_id": "p"}))
    assert d2.allowed and h2

