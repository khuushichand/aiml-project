from unittest.mock import MagicMock, patch

import httpx
import pytest

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError, ChatProviderError
from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local import (
    _chat_with_openai_compatible_local_server,
)


def _make_httpx_error(status_code: int, url: str = "http://local/v1/chat/completions") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", url)
    response = httpx.Response(status_code, request=request, content=b'{"error":{"message":"failure"}}')
    return httpx.HTTPStatusError("failure", request=request, response=response)


@pytest.mark.unit
def test_local_openai_raises_bad_request_on_4xx():
    error = _make_httpx_error(400)

    with patch("tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.side_effect = error
        mock_client.close.return_value = None
        mock_client_cls.return_value = mock_client

        with pytest.raises(ChatBadRequestError) as exc:
            _chat_with_openai_compatible_local_server(
                api_base_url="http://localhost:8000",
                model_name="local-model",
                input_data=[{"role": "user", "content": "ping"}],
            )
        assert exc.value.status_code == 400


@pytest.mark.unit
def test_local_openai_raises_provider_error_on_5xx():
    error = _make_httpx_error(502)

    with patch("tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.side_effect = error
        mock_client.close.return_value = None
        mock_client_cls.return_value = mock_client

        with pytest.raises(ChatProviderError) as exc:
            _chat_with_openai_compatible_local_server(
                api_base_url="http://localhost:8000",
                model_name="local-model",
                input_data=[{"role": "user", "content": "ping"}],
            )
        assert exc.value.status_code == 502
