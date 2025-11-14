"""
Endpoint SSE mid-stream error tests for all adapter-backed providers.

Simulate a provider that emits some normal SSE chunks then fails mid-stream.
Verify the endpoint returns exactly one structured SSE error frame and one
terminal [DONE], with earlier normal chunks preserved.
"""

from __future__ import annotations

from typing import AsyncIterator, Iterator, Tuple
import pytest

# Ensure chat fixtures (client/auth) are registered
from tldw_Server_API.tests._plugins import chat_fixtures as _chat_pl  # noqa: F401


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")
    monkeypatch.setenv("STREAMS_UNIFIED", "1")
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    monkeypatch.delenv("TEST_MODE", raising=False)
    yield


_CASES: Tuple[Tuple[str, str, str, str], ...] = (
    ("openai", "tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter", "OpenAIAdapter", "sk-openai-test"),
    ("anthropic", "tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter", "AnthropicAdapter", "sk-ant-test"),
    ("groq", "tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter", "GroqAdapter", "sk-groq-test"),
    ("openrouter", "tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter", "OpenRouterAdapter", "sk-or-test"),
    ("google", "tldw_Server_API.app.core.LLM_Calls.providers.google_adapter", "GoogleAdapter", "sk-gemini-test"),
    ("mistral", "tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter", "MistralAdapter", "sk-mist-test"),
    ("qwen", "tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter", "QwenAdapter", "sk-qwen-test"),
    ("deepseek", "tldw_Server_API.app.core.LLM_Calls.providers.deepseek_adapter", "DeepSeekAdapter", "sk-deepseek-test"),
    ("huggingface", "tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter", "HuggingFaceAdapter", "sk-hf-test"),
    ("custom-openai-api", "tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter", "CustomOpenAIAdapter", "sk-custom1-test"),
)


def _payload(provider: str) -> dict:
    model_map = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-sonnet",
        "groq": "llama-3.1-8b-instant",
        "openrouter": "openrouter/auto",
        "google": "gemini-1.5-pro",
        "mistral": "mistral-large-latest",
        "qwen": "qwen2.5:7b",
        "deepseek": "deepseek-chat",
        "huggingface": "meta-llama/Meta-Llama-3-8B-Instruct",
        "custom-openai-api": "my-openai-compatible",
    }
    return {
        "api_provider": provider,
        "model": model_map.get(provider, "dummy"),
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True,
    }


@pytest.mark.integration
@pytest.mark.parametrize("provider, modname, cls_name, key_value", _CASES)
def test_endpoint_midstream_error_single_sse_and_done(monkeypatch, authenticated_client, provider: str, modname: str, cls_name: str, key_value: str):
    # Wire API key in endpoint module
    import tldw_Server_API.app.api.v1.endpoints.chat as chat_endpoint
    chat_endpoint.API_KEYS = {**(chat_endpoint.API_KEYS or {}), provider: key_value}

    # Patch adapter.stream to yield some chunks, then raise a provider error
    mod = __import__(modname, fromlist=[cls_name])
    Adapter = getattr(mod, cls_name)
    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError

    def _stream_miderror(*args, **kwargs):
        def _gen():
            yield "data: {\"choices\":[{\"delta\":{\"content\":\"hello\"}}]}\n\n"
            yield "data: {\"choices\":[{\"delta\":\" world\"}]}\n\n"
            raise ChatProviderError(provider=provider, message="boom")
        return _gen()

    monkeypatch.setattr(Adapter, "stream", _stream_miderror, raising=True)

    client = authenticated_client
    with client.stream("POST", "/api/v1/chat/completions", json=_payload(provider)) as resp:
        assert resp.status_code == 200
        lines = list(resp.iter_lines())
        # Should include normal chunks first
        assert any("\"hello\"" in ln for ln in lines)
        # And then exactly one error and one [DONE]
        assert sum(1 for ln in lines if '"error"' in ln) == 1
        assert sum(1 for ln in lines if ln.strip().lower() == "data: [done]") == 1
