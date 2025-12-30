import pytest
from unittest.mock import MagicMock, patch

from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call


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
def test_ollama_accepts_system_message_kwarg_and_inserts_message():
    fake_settings = {
        "ollama_api": {
            "api_url": "http://localhost:11434/v1/chat/completions",
            "streaming": False,
            # model is required by the handler; we pass it via call below
        }
    }

    captured_payload = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured_payload.clear()
        if json:
            captured_payload.update(json)
        return DummyResponse({})

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local.load_settings",
        return_value=fake_settings,
    ), patch(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local.httpx.Client"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.side_effect = fake_post
        mock_client.close.return_value = None
        mock_client_cls.return_value = mock_client

        system_text = "You are a helpful assistant."
        chat_api_call(
            api_endpoint="ollama",
            api_key=None,
            messages_payload=[{"role": "user", "content": "hi"}],
            system_message=system_text,
            model="phi3:mini",
            streaming=False,
        )

    assert "messages" in captured_payload
    assert isinstance(captured_payload["messages"], list)
    # The first message should be the injected system message
    first = captured_payload["messages"][0]
    assert first.get("role") == "system"
    assert first.get("content") == system_text
