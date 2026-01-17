"""
Endpoint SSE error-path tests for Google (Gemini) and Mistral when adapters are enabled.

Asserts that a provider-side error during streaming emits exactly one structured
SSE error frame and a single terminal [DONE].
"""

from __future__ import annotations

from typing import Iterator
import json
# Ensure chat fixtures (client/auth) are registered as pytest fixtures
from tldw_Server_API.tests._plugins import chat_fixtures as _chat_pl  # noqa: F401
import pytest


@pytest.fixture(autouse=True)
def _enable_adapters(monkeypatch):
    monkeypatch.setenv("STREAMS_UNIFIED", "1")
    # Disable TEST_MODE shunts
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    yield


def _payload(provider: str, *, stream: bool) -> dict:
    model = "gemini-1.5-pro" if provider == "google" else "mistral-large-latest"
    return {
        "api_provider": provider,
        "model": model,
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": stream,
    }


@pytest.mark.integration
def test_chat_endpoint_streaming_error_google(monkeypatch, authenticated_client):
    """Adapter stream raises -> endpoint emits SSE error and [DONE]."""
    # Supply API key at endpoint module
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint
    chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "google": "sk-gemini-test"}

    # Patch GoogleAdapter.stream to raise a ChatBadRequestError (normalized provider error)
    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError
    import tldw_Server_API.app.core.LLM_Calls.providers.google_adapter as google_mod

    def _stream_raises(*args, **kwargs):
        raise ChatBadRequestError(provider="google", message="bad prompt")

    monkeypatch.setattr(google_mod.GoogleAdapter, "stream", _stream_raises, raising=True)

    client = authenticated_client
    with client.stream("POST", "/api/v1/chat/completions", json=_payload("google", stream=True)) as resp:
        assert resp.status_code == 200
        lines = list(resp.iter_lines())
        saw_error = any((ln.startswith("data:") and '"error"' in ln) for ln in lines)
        saw_done = sum(1 for ln in lines if ln.strip().lower() == "data: [done]") == 1
        assert saw_error, f"Expected SSE error, got: {lines[:5]}"
        assert saw_done, "Expected a single [DONE] sentinel"


@pytest.mark.integration
def test_chat_endpoint_streaming_error_mistral(monkeypatch, authenticated_client):
    """Adapter stream raises -> endpoint emits SSE error and [DONE]."""
    # Supply API key at endpoint module
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint
    chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), "mistral": "sk-mistral-test"}

    # Patch MistralAdapter.stream to raise a ChatProviderError (server-side)
    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
    import tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter as mistral_mod

    def _stream_raises(*args, **kwargs):
        raise ChatProviderError(provider="mistral", message="upstream 502", status_code=502)

    monkeypatch.setattr(mistral_mod.MistralAdapter, "stream", _stream_raises, raising=True)

    client = authenticated_client
    with client.stream("POST", "/api/v1/chat/completions", json=_payload("mistral", stream=True)) as resp:
        assert resp.status_code == 200
        lines = list(resp.iter_lines())
        saw_error = any((ln.startswith("data:") and '"error"' in ln) for ln in lines)
        saw_done = sum(1 for ln in lines if ln.strip().lower() == "data: [done]") == 1
        assert saw_error, f"Expected SSE error, got: {lines[:5]}"
        assert saw_done, "Expected a single [DONE] sentinel"
