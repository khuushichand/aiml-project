import pytest

from tldw_Server_API.app.core.LLM_Calls.routing.candidate_pool import RoutingCandidate
from tldw_Server_API.app.core.LLM_Calls.routing.models import RouterRequest, RoutingOverride
from tldw_Server_API.app.core.LLM_Calls.routing.policy import resolve_routing_policy
from tldw_Server_API.app.core.LLM_Calls.routing.service import route_model


@pytest.mark.unit
def test_model_router_service_marks_routed_decision_as_canonical():
    decision = route_model(
        request=RouterRequest(model="auto", surface="chat"),
        policy=resolve_routing_policy(
            request_model="auto",
            explicit_provider=None,
            server_default_provider="openai",
        ),
        candidates=[RoutingCandidate(provider="openai", model="gpt-4.1")],
    )

    assert decision is not None
    assert decision.canonical is True
    assert decision.provider == "openai"
    assert decision.model == "gpt-4.1"


@pytest.mark.unit
def test_model_router_service_honors_rules_strategy_over_llm_choice():
    decision = route_model(
        request=RouterRequest(model="auto", surface="chat"),
        policy=resolve_routing_policy(
            request_model="auto",
            explicit_provider=None,
            routing_override=RoutingOverride(strategy="rules_router"),
            server_default_provider="openai",
        ),
        candidates=[
            RoutingCandidate(provider="openai", model="gpt-4.1", quality_rank=10),
            RoutingCandidate(provider="openai", model="gpt-4.1-mini", quality_rank=20),
        ],
        llm_router_choice={"provider": "openai", "model": "gpt-4.1-mini"},
    )

    assert decision is not None
    assert decision.provider == "openai"
    assert decision.model == "gpt-4.1"
    assert decision.decision_source == "rules_router"


@pytest.mark.unit
def test_model_router_service_returns_none_when_failure_mode_requires_error():
    decision = route_model(
        request=RouterRequest(model="auto", surface="chat"),
        policy=resolve_routing_policy(
            request_model="auto",
            explicit_provider=None,
            routing_override=RoutingOverride(failure_mode="error"),
            server_default_provider="openai",
        ),
        candidates=[
            RoutingCandidate(provider="openai", model="gpt-4.1", quality_rank=10),
            RoutingCandidate(provider="openai", model="gpt-4.1-mini", quality_rank=20),
        ],
        llm_router_choice={"provider": "openai", "model": "missing-model"},
    )

    assert decision is None
