import pytest

from tldw_Server_API.app.core.LLM_Calls.routing.accounting import (
    RoutingUsageContext,
    build_routing_telemetry_payload,
    get_router_operation_name,
    log_model_router_usage,
)
from tldw_Server_API.app.core.LLM_Calls.routing.models import RoutingDecision


def test_get_router_operation_name_is_surface_specific():
    assert get_router_operation_name("chat") == "chat_router"


def test_build_routing_telemetry_payload_separates_router_and_execution_models():
    payload = build_routing_telemetry_payload(
        decision=RoutingDecision(provider="openai", model="gpt-4.1", decision_source="llm_router"),
        execution_provider="openai",
        execution_model="gpt-4.1-mini",
        fallback_used=True,
    )

    assert payload["router_selected_provider"] == "openai"
    assert payload["router_selected_model"] == "gpt-4.1"
    assert payload["execution_provider"] == "openai"
    assert payload["execution_model"] == "gpt-4.1-mini"
    assert payload["fallback_used"] is True


@pytest.mark.asyncio
async def test_log_model_router_usage_records_router_operation():
    calls: list[dict[str, object]] = []

    async def fake_usage_logger(**kwargs):
        calls.append(kwargs)

    await log_model_router_usage(
        context=RoutingUsageContext(
            surface="chat",
            endpoint="POST:/api/v1/chat/completions",
            user_id=1,
            key_id=2,
            request_id="req-router",
            conversation_id="conv-1",
        ),
        provider="openai",
        model="gpt-4.1-mini",
        prompt_tokens=10,
        completion_tokens=2,
        total_cost_usd=0.001,
        usage_logger=fake_usage_logger,
    )

    assert len(calls) == 1
    assert calls[0]["operation"] == "chat_router"
    assert calls[0]["provider"] == "openai"
    assert calls[0]["model"] == "gpt-4.1-mini"
    assert calls[0]["conversation_id"] == "conv-1"
