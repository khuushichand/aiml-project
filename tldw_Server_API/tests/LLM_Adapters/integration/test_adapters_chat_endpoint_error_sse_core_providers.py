"""
Endpoint SSE error-path tests for OpenAI, Anthropic, Groq, and OpenRouter adapters.

Ensures a provider-side error during streaming results in exactly one structured
SSE error frame in the response and a single [DONE] sentinel.
"""

from __future__ import annotations

import pytest

# Ensure chat fixtures (client/auth) are registered as pytest fixtures
from tldw_Server_API.tests._plugins import chat_fixtures as _chat_pl  # noqa: F401


@pytest.fixture(autouse=True)
def _enable_adapters(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")
    monkeypatch.setenv("STREAMS_UNIFIED", "1")
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    yield


def _payload(provider: str) -> dict:
    model = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-sonnet",
        "groq": "llama3-groq-8b",
        "openrouter": "openrouter/auto",
    }[provider]
    return {
        "api_provider": provider,
        "model": model,
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
    }


@pytest.mark.integration
def test_chat_endpoint_streaming_error_openai(monkeypatch, authenticated_client):
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint
    chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "openai": "sk-openai-test"}

    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError
    import tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter as openai_mod

    def _stream_raises(*args, **kwargs):
        raise ChatBadRequestError(provider="openai", message="invalid input")

    monkeypatch.setattr(openai_mod.OpenAIAdapter, "stream", _stream_raises, raising=True)

    client = authenticated_client
    with client.stream("POST", "/api/v1/chat/completions", json=_payload("openai")) as resp:
        assert resp.status_code == 200
        lines = list(resp.iter_lines())
        saw_error = any((ln.startswith("data:") and '"error"' in ln) for ln in lines)
        saw_done = sum(1 for ln in lines if ln.strip().lower() == "data: [done]") == 1
        assert saw_error, f"Expected SSE error, got: {lines[:5]}"
        assert saw_done, "Expected a single [DONE] sentinel"


@pytest.mark.integration
def test_chat_endpoint_streaming_error_anthropic(monkeypatch, authenticated_client):
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint
    chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "anthropic": "sk-ant-test"}

    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as ant_mod

    def _stream_raises(*args, **kwargs):
        raise ChatProviderError(provider="anthropic", message="server error", status_code=500)

    monkeypatch.setattr(ant_mod.AnthropicAdapter, "stream", _stream_raises, raising=True)

    client = authenticated_client
    with client.stream("POST", "/api/v1/chat/completions", json=_payload("anthropic")) as resp:
        assert resp.status_code == 200
        lines = list(resp.iter_lines())
        saw_error = any((ln.startswith("data:") and '"error"' in ln) for ln in lines)
        saw_done = sum(1 for ln in lines if ln.strip().lower() == "data: [done]") == 1
        assert saw_error, f"Expected SSE error, got: {lines[:5]}"
        assert saw_done, "Expected a single [DONE] sentinel"


@pytest.mark.integration
def test_chat_endpoint_streaming_error_groq(monkeypatch, authenticated_client):
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint
    chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "groq": "sk-groq-test"}

    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatRateLimitError
    import tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter as groq_mod

    def _stream_raises(*args, **kwargs):
        raise ChatRateLimitError(provider="groq", message="too many requests")

    monkeypatch.setattr(groq_mod.GroqAdapter, "stream", _stream_raises, raising=True)

    client = authenticated_client
    with client.stream("POST", "/api/v1/chat/completions", json=_payload("groq")) as resp:
        assert resp.status_code == 200
        lines = list(resp.iter_lines())
        saw_error = any((ln.startswith("data:") and '"error"' in ln) for ln in lines)
        saw_done = sum(1 for ln in lines if ln.strip().lower() == "data: [done]") == 1
        assert saw_error, f"Expected SSE error, got: {lines[:5]}"
        assert saw_done, "Expected a single [DONE] sentinel"


@pytest.mark.integration
def test_chat_endpoint_streaming_error_openrouter(monkeypatch, authenticated_client):
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint
    chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "openrouter": "sk-or-test"}

    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatAuthenticationError
    import tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter as or_mod

    def _stream_raises(*args, **kwargs):
        raise ChatAuthenticationError(provider="openrouter", message="bad key")

    monkeypatch.setattr(or_mod.OpenRouterAdapter, "stream", _stream_raises, raising=True)

    client = authenticated_client
    with client.stream("POST", "/api/v1/chat/completions", json=_payload("openrouter")) as resp:
        assert resp.status_code == 200
        lines = list(resp.iter_lines())
        saw_error = any((ln.startswith("data:") and '"error"' in ln) for ln in lines)
        saw_done = sum(1 for ln in lines if ln.strip().lower() == "data: [done]") == 1
        assert saw_error, f"Expected SSE error, got: {lines[:5]}"
        assert saw_done, "Expected a single [DONE] sentinel"
