import pytest
from fastapi import status
from unittest.mock import patch

from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import (
    ChatCompletionRequest,
    ChatCompletionUserMessageParam,
)
from tldw_Server_API.app.core.LLM_Calls.routing.decision_store import InMemoryRoutingDecisionStore
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


@pytest.mark.integration
def test_chat_endpoint_auto_routing_runs_llm_router_logs_usage_and_wires_sticky_mode(
    authenticated_client,
    mock_chacha_db,
    setup_dependencies,
):
    injected_store = InMemoryRoutingDecisionStore()
    authenticated_client.app.state.routing_decision_store = injected_store
    request_data = ChatCompletionRequest(
        model="auto",
        api_provider="openrouter",
        conversation_id="conv-router",
        routing={"mode": "sticky_session"},
        messages=[ChatCompletionUserMessageParam(role="user", content="Summarize this")],
    )
    captured: dict[str, object] = {}

    async def fake_router_call(**kwargs):
        captured["router_call"] = kwargs
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"provider":"openrouter","model":"anthropic/claude-4.5-sonnet"}'
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 3,
                "total_tokens": 14,
            },
        }

    async def fake_router_usage(**kwargs):
        captured.setdefault("router_usage", []).append(kwargs)

    def fake_route_model(**kwargs):
        captured["route_model_kwargs"] = kwargs
        decision = RoutingDecision(
            provider="openrouter",
            model="anthropic/claude-4.5-sonnet",
            canonical=True,
            decision_source="llm_router",
        )
        sticky_store = kwargs.get("sticky_store")
        request = kwargs.get("request")
        if sticky_store is not None and request is not None:
            sticky_store.save(
                scope=request.scope,
                fingerprint="persisted-for-test",
                provider=decision.provider,
                model=decision.model,
            )
        return decision

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
            "tldw_Server_API.app.api.v1.endpoints.chat.get_configured_providers",
            return_value={
                "providers": [
                    {
                        "name": "openrouter",
                        "default_model": "anthropic/claude-4.5-sonnet",
                        "models_info": [
                            {
                                "name": "anthropic/claude-4.5-sonnet",
                                "tool_support": True,
                                "vision_support": True,
                                "quality_rank": 20,
                            },
                            {
                                "name": "openai/gpt-4.1-mini",
                                "tool_support": True,
                                "vision_support": True,
                                "quality_rank": 10,
                            },
                        ],
                    }
                ],
                "default_provider": "openrouter",
            },
        ),
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call_async",
            side_effect=fake_router_call,
            create=True,
        ),
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.log_model_router_usage",
            side_effect=fake_router_usage,
            create=True,
        ),
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.route_model",
            side_effect=fake_route_model,
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
    assert captured["route_model_kwargs"]["sticky_store"] is injected_store
    assert captured["route_model_kwargs"]["llm_router_choice"] == {
        "provider": "openrouter",
        "model": "anthropic/claude-4.5-sonnet",
    }
    assert captured["router_call"]["model"] == "anthropic/claude-4.5-sonnet"
    assert captured["router_usage"][0]["provider"] == "openrouter"
