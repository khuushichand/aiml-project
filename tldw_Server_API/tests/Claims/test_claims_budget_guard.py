import pytest

from tldw_Server_API.app.core.Claims_Extraction.budget_guard import (
    ClaimsJobBudget,
    resolve_claims_job_budget,
)
from tldw_Server_API.app.core.Claims_Extraction import monitoring
from tldw_Server_API.app.core import config


@pytest.mark.unit
def test_claims_job_budget_reserve_exhausts_cost():
    budget = ClaimsJobBudget(max_cost_usd=1.0, max_tokens=100, strict=True)
    assert budget.reserve(cost_usd=0.4, tokens=40)
    assert budget.used_cost_usd == pytest.approx(0.4)
    assert budget.used_tokens == 40
    assert budget.reserve(cost_usd=0.7) is False
    snapshot = budget.snapshot()
    assert snapshot["exhausted"] is True
    assert snapshot["exhausted_reason"] == "cost_usd"


@pytest.mark.unit
def test_resolve_claims_job_budget_respects_enabled():
    cfg = {
        "CLAIMS_JOB_BUDGET_ENABLED": "false",
        "CLAIMS_JOB_MAX_COST_USD": "1.0",
        "CLAIMS_JOB_MAX_TOKENS": "100",
    }
    budget = resolve_claims_job_budget(settings=cfg)
    assert budget is None

    override = resolve_claims_job_budget(settings=cfg, max_tokens=25)
    assert override is not None
    assert override.max_tokens == 25


@pytest.mark.unit
def test_should_throttle_claims_provider_latency(monkeypatch):
    monkeypatch.setitem(config.settings, "CLAIMS_ADAPTIVE_THROTTLE_ENABLED", True)
    monkeypatch.setitem(config.settings, "CLAIMS_ADAPTIVE_THROTTLE_LATENCY_MS", 100)
    monkeypatch.setitem(config.settings, "CLAIMS_ADAPTIVE_THROTTLE_ERROR_RATE", 0)
    monkeypatch.setitem(config.settings, "CLAIMS_ADAPTIVE_THROTTLE_BUDGET_RATIO", 0)

    monitoring._CLAIMS_PROVIDER_STATS.clear()
    monitoring._update_claims_provider_stats(
        provider="test-provider",
        model="test-model",
        latency_s=0.2,
        error=None,
        estimated_cost=None,
    )
    throttle, reason = monitoring.should_throttle_claims_provider(
        provider="test-provider",
        model="test-model",
    )
    assert throttle is True
    assert reason == "latency"


@pytest.mark.unit
def test_suggest_claims_concurrency_budget_ratio(monkeypatch):
    monkeypatch.setitem(config.settings, "CLAIMS_ADAPTIVE_THROTTLE_ENABLED", True)
    monkeypatch.setitem(config.settings, "CLAIMS_ADAPTIVE_THROTTLE_LATENCY_MS", 0)
    monkeypatch.setitem(config.settings, "CLAIMS_ADAPTIVE_THROTTLE_ERROR_RATE", 0)
    monkeypatch.setitem(config.settings, "CLAIMS_ADAPTIVE_THROTTLE_BUDGET_RATIO", 0.2)

    monitoring._CLAIMS_PROVIDER_STATS.clear()
    suggested = monitoring.suggest_claims_concurrency(
        provider="test-provider",
        model="test-model",
        requested=4,
        budget_ratio=0.1,
    )
    assert suggested == 1
