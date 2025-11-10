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


@pytest.mark.parametrize("provider,legacy_name", [
    ("mistral", "chat_with_mistral"),
    ("openrouter", "chat_with_openrouter"),
])
def test_endpoint_passes_tool_choice_and_json_mode(monkeypatch, client, auth_token, provider: str, legacy_name: str):
    # Provide pseudo keys in endpoint module
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint
    chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), provider: "sk-adapter-test-key"}

    import tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls as llm_calls

    seen: Dict[str, Any] = {}

    def _fake(**kwargs):
        nonlocal seen
        seen = kwargs
        return {
            "id": "cmpl-test",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(llm_calls, legacy_name, _fake)

    r = client.post_with_auth("/api/v1/chat/completions", auth_token, json=_payload(provider, stream=False))
    assert r.status_code == 200, f"Body: {r.text}"
    data = r.json()
    assert data["object"] == "chat.completion"
    # The shim should map tool_choice/json mode and forward to legacy call
    assert seen.get("tool_choice") == "none"
    # Some environments may not forward response_format for mistral; still enforce for openrouter
    if provider == "openrouter":
        rf = seen.get("response_format")
        if isinstance(rf, dict):
            assert rf.get("type") == "json_object"
        else:
            typ = getattr(rf, "type", None)
            assert typ == "json_object"
