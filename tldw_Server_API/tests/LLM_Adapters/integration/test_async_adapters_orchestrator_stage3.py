"""
Async orchestrator tests for adapter-backed shims of Stage 3 providers:
Qwen, DeepSeek, HuggingFace, and Custom OpenAI-compatible.
"""

from __future__ import annotations

import os
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def _enable_stage3_async(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")
    monkeypatch.setenv("LLM_ADAPTERS_QWEN", "1")
    monkeypatch.setenv("LLM_ADAPTERS_DEEPSEEK", "1")
    monkeypatch.setenv("LLM_ADAPTERS_HUGGINGFACE", "1")
    monkeypatch.setenv("LLM_ADAPTERS_CUSTOM_OPENAI", "1")
    yield


@pytest.mark.asyncio
async def test_qwen_async_non_streaming(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls as llm_calls

    def _fake_qwen(**kwargs):
        return {"object": "chat.completion", "choices": [{"index": 0, "message": {"content": "ok"}}]}

    monkeypatch.setattr(llm_calls, "chat_with_qwen", _fake_qwen)

    resp = await chat_api_call_async(
        api_endpoint="qwen",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="qwen-2",
        streaming=False,
    )
    assert resp.get("object") == "chat.completion"


@pytest.mark.asyncio
async def test_deepseek_async_streaming(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls as llm_calls

    def _fake_stream(**kwargs) -> Iterator[str]:
        yield "data: {\"choices\":[{\"delta\":{\"content\":\"x\"}}]}\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(llm_calls, "chat_with_deepseek", _fake_stream)

    stream = await chat_api_call_async(
        api_endpoint="deepseek",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="deepseek-chat",
        streaming=True,
    )
    chunks = []
    async for line in stream:  # type: ignore[union-attr]
        chunks.append(line)
    assert any("data:" in c for c in chunks)
    assert sum(1 for c in chunks if "[DONE]" in c) == 1


@pytest.mark.asyncio
async def test_huggingface_async_non_streaming(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls as llm_calls

    def _fake_hf(**kwargs):
        return {"object": "chat.completion", "choices": [{"index": 0, "message": {"content": "ok"}}]}

    monkeypatch.setattr(llm_calls, "chat_with_huggingface", _fake_hf)

    resp = await chat_api_call_async(
        api_endpoint="huggingface",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="meta-llama/Meta-Llama-3-8B-Instruct",
        streaming=False,
    )
    assert resp.get("object") == "chat.completion"


@pytest.mark.asyncio
async def test_custom_openai_async_streaming(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local as llm_local

    def _fake_stream(**kwargs) -> Iterator[str]:
        yield "data: {\"choices\":[{\"delta\":{\"content\":\"y\"}}]}\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(llm_local, "chat_with_custom_openai", _fake_stream)

    stream = await chat_api_call_async(
        api_endpoint="custom-openai-api",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="my-openai-compatible",
        streaming=True,
    )
    lines = []
    async for ch in stream:  # type: ignore[union-attr]
        lines.append(ch)
    assert any("data:" in l for l in lines)
    assert sum(1 for l in lines if "[DONE]" in l) == 1

