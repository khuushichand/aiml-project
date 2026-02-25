import pytest
from unittest.mock import patch

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError
from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload


class DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):

        return None

    def json(self):

        return {}

    def close(self):

        return None


@pytest.mark.unit
@pytest.mark.strict_mode
def test_llamacpp_strict_filter_drops_top_k_from_payload_non_streaming():
    fake_settings = {
        "llama_api": {
            "api_ip": "http://localhost:8001/v1/chat/completions",
            "streaming": False,
            "strict_openai_compat": True,
        }
    }

    captured_payload = {}

    class FakeClient:
        def __init__(self):
            self.closed = False

        def post(self, url, headers=None, json=None, timeout=None):  # noqa: ANN001
            captured_payload.clear()
            if json:
                captured_payload.update(json)
            return DummyResponse({})

        def stream(self, *args, **kwargs):  # noqa: ANN001
            raise AssertionError("Streaming should not be invoked in this test")

        def close(self):

            self.closed = True

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.load_settings",
        return_value=fake_settings,
    ):

        chat_api_call(
            api_endpoint="llama.cpp",
            api_key=None,
            messages_payload=[{"role": "user", "content": "hello"}],
            topk=5,
            streaming=False,
            http_client_factory=lambda timeout: FakeClient(),
        )

    assert "top_k" not in captured_payload
    assert "messages" in captured_payload
    assert "stream" in captured_payload


@pytest.mark.unit
def test_llamacpp_tools_rejected_by_contract():
    with pytest.raises(ChatBadRequestError):
        validate_payload(
            "llama.cpp",
            {
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [{"type": "function", "function": {"name": "x", "parameters": {}}}],
            },
        )
