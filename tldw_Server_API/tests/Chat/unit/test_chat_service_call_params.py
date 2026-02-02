import pytest

from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import ChatCompletionRequest
from tldw_Server_API.app.core.Chat.chat_service import build_call_params_from_request


def test_build_call_params_excludes_extension_fields():
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
