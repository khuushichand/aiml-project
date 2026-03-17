import pytest

from tldw_Server_API.app.core.LLM_Calls.routing.candidate_pool import RoutingCandidate
from tldw_Server_API.app.core.LLM_Calls.routing.llm_router import validate_llm_router_choice
from tldw_Server_API.app.core.LLM_Calls.routing.runtime import (
    extract_router_choice,
    extract_router_usage,
)


@pytest.mark.unit
def test_llm_router_rejects_choice_outside_candidate_set():
    result = validate_llm_router_choice(
        raw_choice={"provider": "anthropic", "model": "claude-opus-4.1"},
        candidates=[RoutingCandidate(provider="openai", model="gpt-4.1")],
    )

    assert result is None


@pytest.mark.unit
def test_extract_router_choice_uses_first_complete_json_object():
    result = extract_router_choice(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            'I have chosen: {"provider":"openai","model":"gpt-4.1"}. '
                            'This model has capabilities: {"tools": true}'
                        )
                    }
                }
            ]
        }
    )

    assert result == {"provider": "openai", "model": "gpt-4.1"}


@pytest.mark.unit
def test_llm_router_accepts_choice_inside_candidate_set():
    result = validate_llm_router_choice(
        raw_choice={"provider": "openai", "model": "gpt-4.1"},
        candidates=[RoutingCandidate(provider="openai", model="gpt-4.1")],
    )

    assert result is not None
    assert result.provider == "openai"
    assert result.model == "gpt-4.1"


@pytest.mark.unit
def test_llm_router_returns_none_when_choice_is_missing():
    result = validate_llm_router_choice(
        raw_choice=None,
        candidates=[RoutingCandidate(provider="openai", model="gpt-4.1")],
    )

    assert result is None


@pytest.mark.unit
def test_llm_router_returns_none_when_candidates_are_empty():
    result = validate_llm_router_choice(
        raw_choice={"provider": "openai", "model": "gpt-4.1"},
        candidates=[],
    )

    assert result is None


@pytest.mark.unit
def test_extract_router_usage_is_non_throwing_for_invalid_usage_fields():
    usage = extract_router_usage(
        {
            "usage": {
                "prompt_tokens": "invalid",
                "completion_tokens": None,
                "total_tokens": "still-invalid",
            }
        }
    )

    assert usage == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
