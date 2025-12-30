import pytest

from tldw_Server_API.app.core.Resource_Governance import RedisResourceGovernor, RGRequest
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


class FakeTime:
    def __init__(self, t0: float = 0.0):
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


@pytest.mark.asyncio
async def test_rg_denials_counter_increments_on_reserve_denial(monkeypatch):
    # Force stub rate paths for determinism
    monkeypatch.setenv("RG_TEST_FORCE_STUB_RATE", "1")

    class _Loader:
        def get_policy(self, pid):
            return {"requests": {"rpm": 1}, "scopes": ["global", "user"]}

    ft = FakeTime(0.0)
    rg = RedisResourceGovernor(policy_loader=_Loader(), time_source=ft, ns="rg_micro_denial")
    reg = get_metrics_registry()

    before = reg.get_metric_stats("rg_denials_total")

    e = "user:micro"
    req = RGRequest(entity=e, categories={"requests": {"units": 1}}, tags={"policy_id": "p"})

    # First should allow
    d1, h1 = await rg.reserve(req)
    assert d1.allowed and h1

    # Second should deny (rpm=1 within same window)
    d2, h2 = await rg.reserve(req)
    assert not d2.allowed and h2 is None

    after = reg.get_metric_stats("rg_denials_total")
    if before:
        assert after["count"] >= before["count"] + 1
    else:
        assert after["count"] >= 1
