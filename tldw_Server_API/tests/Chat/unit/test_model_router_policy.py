import pytest

from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import (
    ChatCompletionRequest,
    ChatCompletionUserMessageParam,
)
from tldw_Server_API.app.core.LLM_Calls.routing.policy import resolve_routing_policy


@pytest.mark.unit
def test_policy_defaults_to_server_default_provider_boundary():
    policy = resolve_routing_policy(
        request_model="auto",
        explicit_provider=None,
        server_default_provider="openai",
    )

    assert policy.boundary_mode == "server_default_provider"
    assert policy.objective == "highest_quality"
    assert policy.mode == "per_turn"
    assert policy.server_default_provider == "openai"


@pytest.mark.unit
def test_chat_completion_request_accepts_routing_override_model():
    request = ChatCompletionRequest(
        model="auto",
        messages=[ChatCompletionUserMessageParam(role="user", content="hello")],
        routing={"mode": "per_turn", "cross_provider": False},
    )

    assert request.routing is not None
    assert request.routing.mode == "per_turn"
    assert request.routing.cross_provider is False
