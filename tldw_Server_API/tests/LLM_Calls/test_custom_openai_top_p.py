import pytest
from unittest.mock import MagicMock, patch

from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local import (
    chat_with_custom_openai,
    chat_with_custom_openai_2,
)


def _base_settings() -> dict:
    """Minimal configuration structure for custom OpenAI providers."""
    return {
        "custom_openai_api": {
            "api_ip": "http://localhost:9000",
            "api_key": "cfg-key-1",
            "model": "cfg-model-1",
            "temperature": 0.5,
            "streaming": False,
            "max_tokens": 1024,
            "api_timeout": 30,
            "api_retries": 1,
            "api_retry_delay": 1,
        },
        "custom_openai_api_2": {
            "api_ip": "http://localhost:9100",
            "api_key": "cfg-key-2",
            "model": "cfg-model-2",
            "temperature": 0.5,
            "streaming": False,
            "max_tokens": 1024,
            "api_timeout": 30,
            "api_retries": 1,
            "api_retry_delay": 1,
        },
    }


@pytest.mark.unit
def test_custom_openai_handler_accepts_topp():
    settings = _base_settings()
    with patch(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local.load_settings",
        return_value=settings,
    ), patch(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local._chat_with_openai_compatible_local_server"
    ) as mock_chat:
        mock_chat.return_value = {"choices": []}

        chat_with_custom_openai(
            input_data=[{"role": "user", "content": "ping"}],
            api_key="test-key",
            model="test-model",
            topp=0.33,
        )

    assert mock_chat.call_count == 1
    kwargs = mock_chat.call_args.kwargs
    assert kwargs["top_p"] == 0.33


@pytest.mark.unit
def test_custom_openai_handler_prefers_maxp_when_both_provided():
    settings = _base_settings()
    with patch(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local.load_settings",
        return_value=settings,
    ), patch(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local._chat_with_openai_compatible_local_server"
    ) as mock_chat:
        mock_chat.return_value = {"choices": []}

        chat_with_custom_openai(
            input_data=[{"role": "user", "content": "ping"}],
            api_key="test-key",
            model="test-model",
            topp=0.12,
            maxp=0.45,
        )

    kwargs = mock_chat.call_args.kwargs
    assert kwargs["top_p"] == 0.45


@pytest.mark.unit
def test_custom_openai_2_handler_accepts_topp():
    settings = _base_settings()
    with patch(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local.load_settings",
        return_value=settings,
    ), patch(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local._chat_with_openai_compatible_local_server"
    ) as mock_chat:
        mock_chat.return_value = {"choices": []}

        chat_with_custom_openai_2(
            input_data=[{"role": "user", "content": "ping"}],
            api_key="key-2",
            model="model-2",
            topp=0.27,
        )

    kwargs = mock_chat.call_args.kwargs
    assert kwargs["top_p"] == 0.27
