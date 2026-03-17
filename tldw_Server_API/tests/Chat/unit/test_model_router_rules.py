import pytest

from tldw_Server_API.app.core.LLM_Calls.routing.candidate_pool import RoutingCandidate
from tldw_Server_API.app.core.LLM_Calls.routing.rules_router import route_with_rules


@pytest.mark.unit
def test_rules_router_prefers_highest_quality_candidate_for_default_objective():
    decision = route_with_rules(
        objective="highest_quality",
        candidates=[
            RoutingCandidate(provider="openai", model="gpt-4.1-mini", quality_rank=20),
            RoutingCandidate(provider="openai", model="gpt-4.1", quality_rank=10),
        ],
    )

    assert decision is not None
    assert decision.model == "gpt-4.1"
