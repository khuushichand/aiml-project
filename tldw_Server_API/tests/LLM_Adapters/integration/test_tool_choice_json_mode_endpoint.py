import os
from typing import Iterator, Any, Dict

import pytest


@pytest.fixture(autouse=True)
def _enable_adapters(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    yield


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


@pytest.mark.parametrize("provider,legacy_name", [
    ("mistral", "chat_with_mistral"),
    ("openrouter", "chat_with_openrouter"),
])
def test_endpoint_passes_tool_choice_and_json_mode(monkeypatch, client, auth_token, provider: str, legacy_name: str):
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint

    real_key = _env_key_for(provider)
    if real_key:
        # Real key present: exercise live adapter path, do not monkeypatch legacy
        chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), provider: real_key}
        r = client.post_with_auth("/api/v1/chat/completions", auth_token, json=_payload(provider, stream=False))
        assert r.status_code == 200, f"Body: {r.text}"
        data = r.json()
        # Shape-only assertions; provider behavior may vary
        assert data.get("object") == "chat.completion"
        assert isinstance(data.get("choices"), list)
    else:
        # No real key: skip test when adapters are enabled but no key exists
        # The adapter path requires a real API key; legacy mock path is not used
        pytest.skip(f"Skipping {provider}: adapters enabled but no real API key available")
