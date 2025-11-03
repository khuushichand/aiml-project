"""
Integration tests for /api/v1/chat/completions using adapter shims with
adapters enabled. Provider HTTP calls are mocked by monkeypatching legacy
handler functions (adapters currently delegate to legacy for parity).
"""

import os
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def _enable_adapters(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")
    # Avoid endpoint-internal mock path that bypasses provider handlers
    monkeypatch.delenv("TEST_MODE", raising=False)
    yield


def _payload(stream: bool = False):
    return {
        "api_provider": "openai",
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": stream,
    }


def test_chat_completions_non_streaming_via_adapter(monkeypatch, client_user_only):
    # Provide a non-mock key via module-level API_KEYS so config is not required
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint
    chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "openai": "sk-adapter-test-key"}

    # Patch legacy call used by adapters to avoid real network
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

    client = client_user_only
    r = client.post("/api/v1/chat/completions", json=_payload(stream=False))
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "Hello there"


def test_chat_completions_streaming_via_adapter(monkeypatch, client_user_only):
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint
    chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "openai": "sk-adapter-test-key"}

    import tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls as llm_calls

    def _fake_stream_openai(**kwargs) -> Iterator[str]:
        assert kwargs.get("streaming") is True
        yield "data: {\"choices\":[{\"delta\":{\"content\":\"chunk\"}}]}\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(llm_calls, "chat_with_openai", _fake_stream_openai)

    client = client_user_only
    with client.stream("POST", "/api/v1/chat/completions", json=_payload(stream=True)) as resp:
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "").lower()
        assert ct.startswith("text/event-stream")
        lines = list(resp.iter_lines())
        # Should include chunks and single DONE
        assert any(l.startswith("data: ") and "[DONE]" not in l for l in lines)
        assert sum(1 for l in lines if l.strip().lower() == "data: [done]") == 1

