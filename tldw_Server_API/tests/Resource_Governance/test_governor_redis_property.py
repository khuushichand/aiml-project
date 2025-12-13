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
            # requests allow 1 per minute; tokens allow 1 per minute.
            # We pre-consume the tokens budget, then attempt a combined reserve.
            return {"requests": {"rpm": 1}, "tokens": {"per_min": 1}, "scopes": ["global", "user"]}

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

    # Pre-consume the tokens window so the combined reserve will be denied.
    d0, h0 = await rg.reserve(RGRequest(entity="user:1", categories={"tokens": {"units": 1}}, tags={"policy_id": "p"}))
    assert d0.allowed and h0

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


@pytest.mark.asyncio
async def test_requests_retry_after_monotonic_and_burst_vs_steady():
    pytest.xfail("FIXME: stabilize Redis requests RA monotonicity across burst/steady patterns")
    class _Loader:
        def get_policy(self, pid):
            # Allow 3 req/min; default scopes global+user
            return {"requests": {"rpm": 3}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_req_ra"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    e = "user:reqra"
    pol = {"requests": {"units": 1}}

    # Burst 3 allowed, 4th denied with retry_after ~ 60
    for _ in range(3):
        d, h = await rg.reserve(RGRequest(entity=e, categories={"requests": {"units": 1}}, tags={"policy_id": "p"}))
        assert d.allowed and h
    d4, h4 = await rg.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
    assert not d4.allowed and h4 is None
    ra1 = int(d4.retry_after or 0)
    assert 1 <= ra1 <= 60

    # Advance time: retry_after should decrease and stay > 0 until window passes
    ft.advance(20)
    d5, _ = await rg.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
    ra2 = int(d5.retry_after or 0)
    assert ra2 <= ra1 and ra2 > 0

    # After full minute, next should be allowed
    ft.advance(60)
    d6, h6 = await rg.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
    assert d6.allowed and h6

    # Steady scenario: 3 spaced requests → never denied
    ns2 = "rg_t_req_steady"
    ft2 = FakeTime(0.0)
    rg2 = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft2, ns=ns2)
    for _ in range(3):
        d, h = await rg2.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
        assert d.allowed and h
        # advance ~20s to keep rate <= 3/min
        ft2.advance(20)
    d_last, h_last = await rg2.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
    assert d_last.allowed and h_last


@pytest.mark.asyncio
async def test_tokens_steady_rate_no_denials():
    class _Loader:
        def get_policy(self, pid):
            # 6 tokens per minute → one every 10s should always pass
            return {"tokens": {"per_min": 6}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_t_tok_steady"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    e = "user:toksteady"
    allowed = 0
    for i in range(12):
        d, h = await rg.reserve(RGRequest(entity=e, categories={"tokens": {"units": 1}}, tags={"policy_id": "p"}))
        assert d.allowed and h
        allowed += 1
        ft.advance(10.0)
    assert allowed == 12
