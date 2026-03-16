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
