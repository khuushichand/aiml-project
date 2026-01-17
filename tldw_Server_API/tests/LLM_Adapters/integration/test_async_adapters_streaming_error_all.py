"""
Async streaming error-path tests for adapter-backed providers.

Each test patches the provider adapter's `astream` method to emit a
single structured SSE error frame followed by one terminal [DONE], and
verifies that `chat_api_call_async` surfaces exactly those two markers
with no duplicates.
"""

from __future__ import annotations

from typing import AsyncIterator, Tuple

import pytest


@pytest.fixture(autouse=True)
def _enable_adapters(monkeypatch):
    # Route via adapters (async shims)
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    yield


_CASES: Tuple[Tuple[str, str, str], ...] = (
    ("openai", "tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter", "OpenAIAdapter"),
    ("anthropic", "tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter", "AnthropicAdapter"),
    ("groq", "tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter", "GroqAdapter"),
    ("openrouter", "tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter", "OpenRouterAdapter"),
    ("google", "tldw_Server_API.app.core.LLM_Calls.providers.google_adapter", "GoogleAdapter"),
    ("mistral", "tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter", "MistralAdapter"),
    ("qwen", "tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter", "QwenAdapter"),
    ("deepseek", "tldw_Server_API.app.core.LLM_Calls.providers.deepseek_adapter", "DeepSeekAdapter"),
    ("huggingface", "tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter", "HuggingFaceAdapter"),
    ("custom-openai-api", "tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter", "CustomOpenAIAdapter"),
    ("custom-openai-api-2", "tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter", "CustomOpenAIAdapter2"),
)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider, modname, cls_name", _CASES)
async def test_async_streaming_error_sse_single_done(monkeypatch, provider: str, modname: str, cls_name: str):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async

    # Patch adapter astrean to emit one structured error and one [DONE]
    mod = __import__(modname, fromlist=[cls_name])
    Adapter = getattr(mod, cls_name)

    async def _fake_astream(_self, request, *, timeout=None) -> AsyncIterator[str]:  # type: ignore
        yield f"data: {{\"error\":{{\"message\":\"boom\",\"type\":\"{provider}_stream_error\"}}}}\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(Adapter, "astream", _fake_astream, raising=True)

    stream = await chat_api_call_async(
        api_endpoint=provider,
        messages_payload=[{"role": "user", "content": "hi"}],
        model="test-model",
        streaming=True,
    )

    lines = []
    async for ln in stream:  # type: ignore[union-attr]
        lines.append(ln)

    # Must include exactly one structured error frame and exactly one [DONE]
    assert sum(1 for l in lines if '"error"' in l) == 1
    assert sum(1 for l in lines if l.strip() == "data: [DONE]") == 1
    # All lines start with 'data: '
    assert all(l.startswith("data: ") for l in lines)
