import pytest
from unittest.mock import patch

from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call


@pytest.mark.unit
def test_local_llm_forwards_response_format_n_user_identifier_via_chat_api_call():
    messages = [{"role": "user", "content": "ping"}]

    # Minimal settings; local_llm handler has sensible defaults
    fake_settings = {
        "local_llm": {
            "api_ip": "http://localhost:8080/v1/chat/completions",
            "streaming": False,
        }
    }

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local.load_settings",
        return_value=fake_settings,
    ), patch(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local._chat_with_openai_compatible_local_server"
    ) as mock_inner:
        mock_inner.return_value = {"choices": []}

        chat_api_call(
            api_endpoint="local-llm",
            api_key=None,
            messages_payload=messages,
            response_format={"type": "json_object"},
            n=3,
            user_identifier="test-user-123",
        )

    # Validate the forwarding into the OpenAI-compatible inner handler
    kwargs = mock_inner.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["n"] == 3
    assert kwargs["user_identifier"] == "test-user-123"
