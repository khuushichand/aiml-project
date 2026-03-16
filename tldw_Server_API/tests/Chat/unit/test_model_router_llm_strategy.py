import pytest

from tldw_Server_API.app.core.LLM_Calls.routing.candidate_pool import RoutingCandidate
from tldw_Server_API.app.core.LLM_Calls.routing.llm_router import validate_llm_router_choice


@pytest.mark.unit
def test_llm_router_rejects_choice_outside_candidate_set():
    result = validate_llm_router_choice(
        raw_choice={"provider": "anthropic", "model": "claude-opus-4.1"},
        candidates=[RoutingCandidate(provider="openai", model="gpt-4.1")],
    )

    assert result is None
