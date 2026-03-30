import pytest

from tldw_Server_API.app.core.LLM_Calls.routing.candidate_pool import (
    build_candidate_pool,
    choose_ranked_candidate,
)


@pytest.mark.unit
def test_candidate_pool_filters_models_outside_pinned_provider():
    candidates = build_candidate_pool(
        boundary_mode="pinned_provider",
        pinned_provider="openai",
        requested_capabilities={"tools": True},
        catalog=[
            {"provider": "openai", "model": "gpt-4.1", "tool_support": True},
            {"provider": "anthropic", "model": "claude-sonnet-4.5", "tool_support": True},
            {"provider": "openai", "model": "gpt-4.1-mini", "tool_support": False},
        ],
    )

    assert [(candidate.provider, candidate.model) for candidate in candidates] == [
        ("openai", "gpt-4.1"),
    ]


@pytest.mark.unit
def test_candidate_pool_uses_admin_order_when_quality_rank_missing():
    chosen = choose_ranked_candidate(
        candidates=[
            {"provider": "openai", "model": "gpt-4.1-mini"},
            {"provider": "openai", "model": "gpt-4.1"},
        ],
        provider_order={"openai": ["gpt-4.1", "gpt-4.1-mini"]},
        objective="highest_quality",
    )

    assert chosen is not None
    assert chosen.model == "gpt-4.1"


@pytest.mark.unit
def test_candidate_pool_rejects_unknown_context_window_when_minimum_is_required():
    candidates = build_candidate_pool(
        boundary_mode="cross_provider",
        requested_capabilities={"context_window": 64000},
        catalog=[
            {"provider": "openai", "model": "gpt-4.1-mini", "context_window": None},
            {"provider": "anthropic", "model": "claude-sonnet-4.5", "context_window": 200000},
        ],
    )

    assert [(candidate.provider, candidate.model) for candidate in candidates] == [
        ("anthropic", "claude-sonnet-4.5"),
    ]


@pytest.mark.unit
def test_choose_ranked_candidate_balances_quality_latency_and_cost():
    chosen = choose_ranked_candidate(
        candidates=[
            {
                "provider": "provider-a",
                "model": "quality-only",
                "quality_rank": 10,
                "latency_rank": 90,
                "cost_rank": 90,
            },
            {
                "provider": "provider-b",
                "model": "balanced-winner",
                "quality_rank": 30,
                "latency_rank": 20,
                "cost_rank": 20,
            },
        ],
        objective="balanced",
    )

    assert chosen is not None
    assert chosen.model == "balanced-winner"
