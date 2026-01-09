"""
Async integration tests for chat_orchestrator.chat_api_call_async routing
through adapter-backed async shims with adapters enabled.
"""

from __future__ import annotations

import os
import asyncio
from typing import AsyncIterator, Iterator

import pytest


@pytest.fixture(autouse=True)
def _enable_async_adapters(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")
    monkeypatch.setenv("LLM_ADAPTERS_OPENAI", "1")
    # Ensure native HTTP path stays off for these tests
    monkeypatch.delenv("LLM_ADAPTERS_NATIVE_HTTP_OPENAI", raising=False)
    yield


async def test_chat_api_call_async_non_streaming(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async

    # Patch legacy sync path used by adapter to avoid network
    import tldw_Server_API.app.core.LLM_Calls.legacy_chat_calls as llm_calls

    def _fake_openai(**kwargs):
        assert kwargs.get("streaming") in (False, None)
        return {
            "id": "cmpl-test",
            "object": "chat.completion",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
            ],
        }

    monkeypatch.setattr(llm_calls, "chat_with_openai", _fake_openai)

    resp = await chat_api_call_async(
        api_endpoint="openai",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        streaming=False,
    )
    assert isinstance(resp, dict)
    assert resp.get("object") == "chat.completion"
    assert resp.get("choices", [{}])[0].get("message", {}).get("content") == "ok"


async def test_chat_api_call_async_streaming(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async

    import tldw_Server_API.app.core.LLM_Calls.legacy_chat_calls as llm_calls

    def _fake_stream(**kwargs) -> Iterator[str]:
        assert kwargs.get("streaming") is True
        yield "data: {\"choices\":[{\"delta\":{\"content\":\"x\"}}]}\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(llm_calls, "chat_with_openai", _fake_stream)

    stream = await chat_api_call_async(
        api_endpoint="openai",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        streaming=True,
    )
    # Should be an async iterator yielding SSE lines
    chunks = []
    async for line in stream:  # type: ignore[union-attr]
        chunks.append(line)
    assert any("data:" in c for c in chunks)
    assert sum(1 for c in chunks if "[DONE]" in c) == 1
