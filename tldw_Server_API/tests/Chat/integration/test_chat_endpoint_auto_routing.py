import pytest
from fastapi import status
from unittest.mock import patch

from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import (
    ChatCompletionRequest,
    ChatCompletionUserMessageParam,
)
from tldw_Server_API.app.core.LLM_Calls.routing.models import RoutingDecision


@pytest.mark.integration
def test_chat_endpoint_routes_auto_before_provider_normalization(
    authenticated_client,
    mock_chacha_db,
    setup_dependencies,
):
    request_data = ChatCompletionRequest(
        model="auto",
        api_provider="openrouter",
        messages=[ChatCompletionUserMessageParam(role="user", content="Summarize this")],
    )
    captured: dict[str, object] = {}

    async def fake_execute_non_stream_call(**kwargs):
        captured["selected_provider"] = kwargs.get("selected_provider")
        captured["model"] = kwargs.get("model")
        return {
            "id": "chatcmpl-auto-routing",
            "object": "chat.completion",
            "model": kwargs.get("model"),
            "choices": [
                {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
            ],
        }

    with (
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.route_model",
            return_value=RoutingDecision(
                provider="openrouter",
                model="anthropic/claude-4.5-sonnet",
                canonical=True,
                decision_source="rules_router",
            ),
        ),
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.get_configured_providers",
            return_value={
                "providers": [
                    {
                        "name": "openrouter",
                        "models_info": [
                            {
                                "name": "anthropic/claude-4.5-sonnet",
                                "tool_support": True,
                                "vision_support": True,
                                "quality_rank": 20,
                            }
                        ],
                    }
                ],
                "default_provider": "openrouter",
            },
        ),
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.execute_non_stream_call",
            side_effect=fake_execute_non_stream_call,
        ),
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.API_KEYS",
            {"openrouter": "test-key"},
        ),
    ):
        response = authenticated_client.post("/api/v1/chat/completions", json=request_data.model_dump())

    assert response.status_code == status.HTTP_200_OK
    assert captured["selected_provider"] == "openrouter"
    assert captured["model"] == "anthropic/claude-4.5-sonnet"
    assert response.json()["model"] == "anthropic/claude-4.5-sonnet"
