import pytest

pytestmark = pytest.mark.rate_limit

from tldw_Server_API.app.core.Resource_Governance import MemoryResourceGovernor, RGRequest
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.asyncio
async def test_rg_metrics_cardinality_and_counters():
    pols = {"p": {"requests": {"rpm": 1}, "tokens": {"per_min": 1}, "scopes": ["global", "user"]}}
    rg = MemoryResourceGovernor(policies=pols)
    reg = get_metrics_registry()

    # Baseline stats
    before_allow = reg.get_metric_stats("rg_decisions_total")
    before_denials = reg.get_metric_stats("rg_denials_total")
    before_refunds = reg.get_metric_stats("rg_refunds_total")

    e = "user:card"
    # Allow one request
    d1, h1 = await rg.reserve(RGRequest(entity=e, categories={"requests": {"units": 1}}, tags={"policy_id": "p"}))
    assert d1.allowed and h1
    # Deny next request
    d2, _ = await rg.reserve(RGRequest(entity=e, categories={"requests": {"units": 1}}, tags={"policy_id": "p"}))
    assert not d2.allowed
    # Refund path via tokens: reserve then commit fewer
    d3, h3 = await rg.reserve(RGRequest(entity=e, categories={"tokens": {"units": 1}}, tags={"policy_id": "p"}))
    assert d3.allowed and h3
    await rg.commit(h3, actuals={"tokens": 0})

    # Assertions: counters moved
    after_allow = reg.get_metric_stats("rg_decisions_total")
    after_denials = reg.get_metric_stats("rg_denials_total")
    after_refunds = reg.get_metric_stats("rg_refunds_total")
    assert (not before_allow) or after_allow["count"] >= before_allow["count"] + 2
    assert (not before_denials) or after_denials["count"] >= before_denials["count"] + 1
    assert (not before_refunds) or after_refunds["count"] >= before_refunds["count"] + 1

    # Cardinality guard: ensure no entity label recorded on these metrics
    vals = reg.values.get("rg_decisions_total", [])
    assert all("entity" not in mv.labels for mv in vals)
    vals_deny = reg.values.get("rg_denials_total", [])
    assert all("entity" not in mv.labels for mv in vals_deny)
    vals_ref = reg.values.get("rg_refunds_total", [])
    assert all("entity" not in mv.labels for mv in vals_ref)

