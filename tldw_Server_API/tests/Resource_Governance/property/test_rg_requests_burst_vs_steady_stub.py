import os
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

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
@settings(deadline=None, max_examples=12, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    rpm=st.integers(min_value=1, max_value=10),
    steady_gap=st.integers(min_value=5, max_value=30),
)
async def test_requests_burst_vs_steady_monotonic_retry_after_under_stub(monkeypatch, rpm, steady_gap):
    # Force stub rate paths to avoid real-redis timing variance
    monkeypatch.setenv("RG_TEST_FORCE_STUB_RATE", "1")

    class _Loader:
        def get_policy(self, pid):
                     return {"requests": {"rpm": int(rpm)}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    ns = "rg_p_req_stub"
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns=ns)
    e = "user:req"
    pol = {"requests": {"units": 1}}

    # Burst: allow up to rpm, then deny
    for _ in range(rpm):
        d, h = await rg.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
        assert d.allowed and h
    d_deny, h_deny = await rg.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
    assert (not d_deny.allowed) and (h_deny is None)
    ra1 = int(d_deny.retry_after or 0)
    assert 1 <= ra1 <= 60

    # Advance some seconds; retry_after should decrease but remain > 0 until a minute from first admit
    advance_s = min(steady_gap, 59)
    ft.advance(float(advance_s))
    d_again, _ = await rg.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
    ra2 = int(d_again.retry_after or 0)
    assert (not d_again.allowed) and (0 < ra2 <= ra1)

    # After full minute since initial burst, should allow again
    ft.advance(60.0)
    d_ok, h_ok = await rg.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
    assert d_ok.allowed and h_ok

    # Steady: rate spread at ~60/rpm seconds should not deny
    ft2 = FakeTime(0.0)
    rg2 = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft2, ns=ns + "_steady")
    step = max(1, int(60 / max(1, rpm)))
    for _ in range(rpm):
        d, h = await rg2.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
        assert d.allowed and h
        ft2.advance(float(step))
    d_last, h_last = await rg2.reserve(RGRequest(entity=e, categories=pol, tags={"policy_id": "p"}))
    assert d_last.allowed and h_last
