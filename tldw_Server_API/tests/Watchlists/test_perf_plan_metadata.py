from __future__ import annotations

import pytest


pytestmark = pytest.mark.unit

WATCHLISTS_SCALE_GUARDRAILS: dict[str, float] = {
    "filter_eval_large_rule_set_seconds": 8.0,
    "sources_listing_seconds": 0.45,
    "jobs_listing_seconds": 0.40,
}

WATCHLISTS_SCALE_SCENARIOS: dict[str, dict[str, int]] = {
    "filter_eval_large_rule_set": {
        "rule_count": 120,
        "evaluation_iterations": 600,
    },
    "watchlists_db_listing": {
        "source_count": 1500,
        "job_count": 900,
        "page_size": 200,
    },
}


def test_watchlists_perf_markers_registered(pytestconfig):
    markers = "\n".join(pytestconfig.getini("markers"))
    assert "performance" in markers  # nosec B101
    assert "load" in markers  # nosec B101


def test_watchlists_perf_guardrail_thresholds_are_defined():
    assert WATCHLISTS_SCALE_GUARDRAILS["filter_eval_large_rule_set_seconds"] <= 10.0  # nosec B101
    assert WATCHLISTS_SCALE_GUARDRAILS["sources_listing_seconds"] <= 1.0  # nosec B101
    assert WATCHLISTS_SCALE_GUARDRAILS["jobs_listing_seconds"] <= 1.0  # nosec B101
    assert all(value > 0 for value in WATCHLISTS_SCALE_GUARDRAILS.values())  # nosec B101


def test_watchlists_perf_scale_scenarios_are_documented():
    filter_scenario = WATCHLISTS_SCALE_SCENARIOS["filter_eval_large_rule_set"]
    listing_scenario = WATCHLISTS_SCALE_SCENARIOS["watchlists_db_listing"]

    assert filter_scenario["rule_count"] >= 100  # nosec B101
    assert filter_scenario["evaluation_iterations"] >= 500  # nosec B101
    assert listing_scenario["source_count"] >= 1000  # nosec B101
    assert listing_scenario["job_count"] >= 500  # nosec B101
    assert listing_scenario["page_size"] >= 100  # nosec B101
