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
def test_ollama_top_p_is_coerced_to_float():
    # top_p provided as a string in config should be coerced to float in payload
    fake_settings = {
        "ollama_api": {
            "api_url": "http://localhost:11434/v1/chat/completions",
            "streaming": False,
            "top_p": "0.9",
            "model": "phi3:mini",
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

        chat_api_call(
            api_endpoint="ollama",
            api_key=None,
            messages_payload=[{"role": "user", "content": "hello"}],
            streaming=False,
            model="phi3:mini",
        )

    assert "top_p" in captured_payload
    assert isinstance(captured_payload["top_p"], float)
    assert captured_payload["top_p"] == 0.9
