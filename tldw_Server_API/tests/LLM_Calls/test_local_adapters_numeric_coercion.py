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
@pytest.mark.parametrize(
    "provider_name, cfg_section, url_key",
    [
        ("vllm", "vllm_api", "api_ip"),
        ("local-llm", "local_llm", "api_ip"),
        ("ooba", "ooba_api", "api_ip"),
        ("llama.cpp", "llama_api", "api_ip"),
        ("tabbyapi", "tabby_api", "api_ip"),
        ("aphrodite", "aphrodite_api", "api_ip"),
    ],
)
def test_local_like_adapters_coerce_numeric_types(provider_name, cfg_section, url_key):
    fake_settings = {
        cfg_section: {
            url_key: "http://localhost:1234/v1",  # openai-compatible path ok
            "streaming": False,
            "top_p": "0.9",
            "top_k": "50",
            "model": "dummy",
        }
    }

    captured_payload = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured_payload.clear()
        if json:
            captured_payload.update(json)
        return DummyResponse({})

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.load_settings",
        return_value=fake_settings,
    ), patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters._hc_create_client"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.side_effect = fake_post
        mock_client.close.return_value = None
        mock_client_cls.return_value = mock_client

        chat_api_call(
            api_endpoint=provider_name,
            api_key=None,
            messages_payload=[{"role": "user", "content": "hello"}],
            streaming=False,
            model="dummy",
        )

    assert "top_p" in captured_payload and isinstance(captured_payload["top_p"], float)
    # top_k is not part of strict OpenAI spec but most local servers accept it; check when present
    if "top_k" in captured_payload:
        assert isinstance(captured_payload["top_k"], int)


@pytest.mark.unit
def test_kobold_coerces_numeric_types():
    fake_settings = {
        "kobold_api": {
            "api_ip": "http://localhost:5000/api/v1/generate",
            "streaming": False,
            "top_p": "0.92",
            "top_k": "80",
            "max_length": "128",
        }
    }

    captured_payload = {}

    class Dummy:
        status_code = 200

        def json(self):
            return {"results": [{"text": "ok"}]}

    def fake_fetch(method, url, headers=None, json=None, retry=None):
        captured_payload.clear()
        if json:
            captured_payload.update(json)
        return Dummy()

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.load_settings",
        return_value=fake_settings,
    ), patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters._hc_fetch",
        side_effect=fake_fetch,
    ):
        chat_api_call(
            api_endpoint="kobold",
            api_key=None,
            messages_payload=[{"role": "user", "content": "hello"}],
            streaming=False,
        )

    assert isinstance(captured_payload.get("top_p"), float)
    assert captured_payload.get("top_p") == 0.92
    assert isinstance(captured_payload.get("top_k"), int)
    assert captured_payload.get("top_k") == 80
