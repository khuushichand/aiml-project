"""Unit tests for chat_service call parameter construction."""

import pytest

from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import ChatCompletionRequest
from tldw_Server_API.app.core.LLM_Calls import adapter_registry
from tldw_Server_API.app.core.Chat.chat_service import build_call_params_from_request


pytestmark = pytest.mark.unit


@pytest.mark.unit
def test_build_call_params_excludes_extension_fields() -> None:
    """Ensure extension-only fields are stripped from call params."""
    req = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        history_message_limit=5,
        history_message_order="desc",
        slash_command_injection_mode="preface",
    )

    params = build_call_params_from_request(
        request_data=req,
        target_api_provider="openai",
        provider_api_key="test-key",
        templated_llm_payload=[{"role": "user", "content": "hi"}],
        final_system_message=None,
        app_config=None,
    )

    assert "history_message_limit" not in params
    assert "history_message_order" not in params
    assert "slash_command_injection_mode" not in params
    assert params["api_endpoint"] == "openai"
    assert params["api_key"] == "test-key"
    assert params["messages_payload"]


@pytest.mark.unit
def test_build_call_params_excludes_research_context() -> None:
    """Ensure attached research context stays out of raw provider call params."""
    req = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        research_context={
            "run_id": "run_123",
            "query": "battery recycling supply chain",
            "question": "What changed in the battery recycling market?",
            "outline": [{"title": "Overview"}],
            "key_claims": [{"text": "Claim one"}],
            "unresolved_questions": ["What changed in Europe?"],
            "verification_summary": {"unsupported_claim_count": 0},
            "source_trust_summary": {"high_trust_count": 3},
            "research_url": "/research?run=run_123",
        },
    )

    params = build_call_params_from_request(
        request_data=req,
        target_api_provider="openai",
        provider_api_key="test-key",
        templated_llm_payload=[{"role": "user", "content": "hi"}],
        final_system_message=None,
        app_config=None,
    )

    assert "research_context" not in params


@pytest.mark.unit
def test_build_call_params_negotiates_structured_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure shared call-param construction downgrades unsupported json_schema requests."""

    class _JsonObjectOnlyAdapter:
        def capabilities(self):
            return {"response_format_types": ["json_object"]}

    class _Registry:
        def get_adapter(self, _provider: str):
            return _JsonObjectOnlyAdapter()

    monkeypatch.setattr(adapter_registry, "get_registry", lambda: _Registry())

    req = ChatCompletionRequest(
        model="gpt-4o-mini",
        api_provider="openai",
        messages=[{"role": "user", "content": "return structured"}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "answer_schema",
                "schema": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                },
            },
        },
    )

    params = build_call_params_from_request(
        request_data=req,
        target_api_provider="openai",
        provider_api_key="test-key",
        templated_llm_payload=[{"role": "user", "content": "return structured"}],
        final_system_message=None,
        app_config=None,
    )

    assert params["response_format"] == {"type": "json_object"}
    assert params["_structured_requested_response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "answer_schema",
            "schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            },
        },
    }
