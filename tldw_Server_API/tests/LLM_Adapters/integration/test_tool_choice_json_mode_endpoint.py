import os
from typing import Any, Dict, List

import pytest


@pytest.fixture(autouse=True)
def _enable_adapters(monkeypatch):
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    yield


NETWORK_TESTS_ENABLED = os.getenv("ENABLE_NETWORK_TESTS", "").lower() in {"1", "true", "yes", "on"}


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_obj: Dict[str, Any] | None = None):
        self.status_code = status_code
        self._json = json_obj or {
            "id": "cmpl-test",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        }

    def raise_for_status(self):
        if 400 <= self.status_code:
            import httpx
            req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            resp = httpx.Response(self.status_code, request=req)
            raise httpx.HTTPStatusError("err", request=req, response=resp)

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, capture: Dict[str, Any]):
        self._capture = capture

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, json: Dict[str, Any], headers: Dict[str, str]):
        self._capture["json"] = json
        return _FakeResponse()


def _payload(provider: str, stream: bool = False):
    return {
        "api_provider": provider,
        "model": "dummy",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": stream,
        "tools": [{"type": "function", "function": {"name": "do", "parameters": {}}}],
        "tool_choice": "none",
        "response_format": {"type": "json_object"},
    }


def _env_key_for(provider: str) -> str | None:
    mapping = {
        "mistral": ["MISTRAL_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY", "OPENROUTER_API_KEY_READ"],
    }
    for k in mapping.get(provider, []):
        v = os.getenv(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


@pytest.mark.parametrize("provider", [
    "mistral",
    "openrouter",
])
def test_endpoint_passes_tool_choice_and_json_mode(monkeypatch, client, auth_token, provider: str):
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint

    real_key = _env_key_for(provider) if NETWORK_TESTS_ENABLED else None
    if real_key:
        # Real key present: exercise live adapter path.
        # Use monkeypatch to isolate mutations to API_KEYS and ensure cleanup.
        base = chat_endpoint.API_KEYS if isinstance(chat_endpoint.API_KEYS, dict) else {}
        copied = dict(base)
        monkeypatch.setattr(chat_endpoint, "API_KEYS", copied, raising=False)
        monkeypatch.setitem(chat_endpoint.API_KEYS, provider, real_key)
        r = client.post_with_auth("/api/v1/chat/completions", auth_token, json=_payload(provider, stream=False))
        assert r.status_code == 200, f"Body: {r.text}"
        data = r.json()
        # Shape-only assertions; provider behavior may vary
        assert data.get("object") == "chat.completion"
        assert isinstance(data.get("choices"), list)
    else:
        base = chat_endpoint.API_KEYS if isinstance(chat_endpoint.API_KEYS, dict) else {}
        copied = dict(base)
        monkeypatch.setattr(chat_endpoint, "API_KEYS", copied, raising=False)
        monkeypatch.setitem(chat_endpoint.API_KEYS, provider, f"sk-{provider}-test")
        capture: Dict[str, Any] = {}
        if provider == "mistral":
            import tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter as provider_mod
        else:
            import tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter as provider_mod
        monkeypatch.setattr(provider_mod, "http_client_factory", lambda *a, **k: _FakeClient(capture))
        r = client.post_with_auth("/api/v1/chat/completions", auth_token, json=_payload(provider, stream=False))
        assert r.status_code == 200, f"Body: {r.text}"
        data = r.json()
        assert data.get("object") == "chat.completion"
        assert isinstance(data.get("choices"), list)
        sent = capture.get("json") or {}
        assert sent.get("tool_choice") == "none"
        assert sent.get("response_format", {}).get("type") == "json_object"
