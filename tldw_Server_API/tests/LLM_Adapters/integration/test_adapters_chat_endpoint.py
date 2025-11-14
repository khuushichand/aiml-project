"""
Integration tests for /api/v1/chat/completions.

Behavior:
- If a real provider API key is detected in the environment, the test will
  make a real API call via the adapter to the provider.
- Otherwise, provider calls are mocked by monkeypatching the legacy handler.

This allows local/dev environments with keys to exercise a live integration
path while keeping CI deterministic and offline.
"""

import os
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def _enable_adapters(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")
    # Avoid endpoint-internal mock path that bypasses provider handlers
    monkeypatch.delenv("TEST_MODE", raising=False)
    # Ensure suite-level env overrides from other tests don't hijack base URL.
    # When a real API key is present, this test should talk to the real OpenAI API.
    for name in (
        "OPENAI_API_BASE_URL",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "MOCK_OPENAI_BASE_URL",
        "CUSTOM_OPENAI_API_IP",
    ):
        monkeypatch.delenv(name, raising=False)
    yield


def _payload(stream: bool = False):
    return {
        "api_provider": "openai",
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": stream,
    }


def _real_key(provider: str) -> str | None:
    env_map = {
        "openai": ["OPENAI_API_KEY"],
    }
    for name in env_map.get(provider, []):
        val = os.getenv(name)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def test_chat_completions_non_streaming_via_adapter(monkeypatch, client, auth_token):
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint

    real = _real_key("openai")
    if real:
        # Use real key; do not monkeypatch provider call
        chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "openai": real}
        r = client.post_with_auth("/api/v1/chat/completions", auth_token, json=_payload(stream=False))
        assert r.status_code == 200, f"Body: {r.text}"
        data = r.json()
        # Shape assertions only (provider-specific content may vary)
        assert data.get("object") == "chat.completion"
        assert isinstance(data.get("choices"), list) and len(data["choices"]) >= 1
    else:
        # Provide a test key and mock legacy call to avoid network
        chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "openai": "sk-adapter-test-key"}
        import tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls as llm_calls

        def _fake_openai(**kwargs):
            assert kwargs.get("model") == "gpt-4o-mini"
            # Ensure request was routed non-streaming (explicit False or None is fine)
            assert kwargs.get("streaming") in (False, None)
            return {
                "id": "cmpl-test",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello there"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

        monkeypatch.setattr(llm_calls, "chat_with_openai", _fake_openai)
        r = client.post_with_auth("/api/v1/chat/completions", auth_token, json=_payload(stream=False))
        assert r.status_code == 200, f"Body: {r.text}"
        data = r.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello there"


def test_chat_completions_streaming_via_adapter(monkeypatch, client, auth_token):
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint

    real = _real_key("openai")
    if real:
        chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "openai": real}
        from tldw_Server_API.tests._plugins.chat_fixtures import get_auth_headers
        headers = get_auth_headers(auth_token, getattr(client, "csrf_token", ""))
        with client.stream("POST", "/api/v1/chat/completions", json=_payload(stream=True), headers=headers) as resp:
            assert resp.status_code == 200
            ct = resp.headers.get("content-type", "").lower()
            assert ct.startswith("text/event-stream")
            lines = list(resp.iter_lines())
            # Should include chunks and single DONE
            assert any(line.startswith("data: ") and "[DONE]" not in line for line in lines)
            assert sum(1 for line in lines if line.strip().lower() == "data: [done]") == 1
    else:
        chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "openai": "sk-adapter-test-key"}
        import tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls as llm_calls

        def _fake_stream_openai(**kwargs) -> Iterator[str]:
            assert kwargs.get("streaming") is True
            yield "data: {\"choices\":[{\"delta\":{\"content\":\"chunk\"}}]}\n\n"
            yield "data: [DONE]\n\n"

        monkeypatch.setattr(llm_calls, "chat_with_openai", _fake_stream_openai)

        from tldw_Server_API.tests._plugins.chat_fixtures import get_auth_headers
        headers = get_auth_headers(auth_token, getattr(client, "csrf_token", ""))
        with client.stream("POST", "/api/v1/chat/completions", json=_payload(stream=True), headers=headers) as resp:
            assert resp.status_code == 200
            ct = resp.headers.get("content-type", "").lower()
            assert ct.startswith("text/event-stream")
            lines = list(resp.iter_lines())
            # Should include chunks and single DONE
            assert any(line.startswith("data: ") and "[DONE]" not in line for line in lines)
            assert sum(1 for line in lines if line.strip().lower() == "data: [done]") == 1
