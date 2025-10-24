from unittest.mock import MagicMock, patch

import pytest

from tldw_Server_API.app.core.LLM_Calls.Local_Summarization_Lib import (
    _resolve_local_llm_url,
    summarize_with_local_llm,
)


@pytest.mark.unit
def test_resolve_local_llm_url_handles_various_inputs():
    assert _resolve_local_llm_url(None) == "http://127.0.0.1:8080/v1/chat/completions"
    assert _resolve_local_llm_url("http://host:9000") == "http://host:9000/v1/chat/completions"
    assert _resolve_local_llm_url("http://host:9000/v1") == "http://host:9000/v1/chat/completions"
    assert _resolve_local_llm_url("http://host:9000/v1/chat/completions") == "http://host:9000/v1/chat/completions"


@pytest.mark.unit
def test_summarize_with_local_llm_uses_configured_endpoint():
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "choices": [
            {"message": {"content": "summary result"}}
        ]
    }

    client_ctx = MagicMock()
    client_ctx.post.return_value = fake_response
    client_ctx.__enter__.return_value = client_ctx
    client_ctx.__exit__.return_value = False

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.Local_Summarization_Lib.httpx.Client",
        return_value=client_ctx,
    ), patch(
        "tldw_Server_API.app.core.LLM_Calls.Local_Summarization_Lib.load_settings",
        return_value={"local_llm": {"api_ip": "http://configured-host:8888"}},
    ):
        summarize_with_local_llm("text to summarize", "instruction", temp=0.5)

    assert client_ctx.post.call_count == 1
    called_url = client_ctx.post.call_args.args[0]
    assert called_url == "http://configured-host:8888/v1/chat/completions"
