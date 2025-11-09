"""
Async orchestrator tests for adapter-backed shims of Google (Gemini) and Mistral.

Validates that chat_api_call_async returns async streams yielding SSE lines
and exactly one terminal [DONE].
"""

from __future__ import annotations

import os
import pytest
from typing import AsyncIterator


@pytest.fixture(autouse=True)
def _enable_adapters(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")
    # Ensure unified SSE path if relevant parts rely on it
    monkeypatch.setenv("STREAMS_UNIFIED", "1")
    # Avoid TEST_MODE shortcuts that may bypass provider dispatch
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    yield


@pytest.mark.asyncio
async def test_google_async_streaming(monkeypatch):
    """chat_api_call_async for google returns async iterator yielding SSE lines."""
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import tldw_Server_API.app.core.LLM_Calls.providers.google_adapter as google_mod

    async def _fake_astream(_self, request, *, timeout=None) -> AsyncIterator[str]:  # type: ignore[no-redef]
        yield "data: {\"choices\":[{\"delta\":{\"content\":\"g\"}}]}\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(google_mod.GoogleAdapter, "astream", _fake_astream, raising=True)

    stream = await chat_api_call_async(
        api_endpoint="google",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="gemini-1.5-pro",
        streaming=True,
    )
    lines = []
    async for ln in stream:  # type: ignore[union-attr]
        lines.append(ln)
    assert any(l.startswith("data: ") and "[DONE]" not in l for l in lines)
    assert sum(1 for l in lines if l.strip() == "data: [DONE]") == 1


@pytest.mark.asyncio
async def test_mistral_async_streaming(monkeypatch):
    """chat_api_call_async for mistral returns async iterator yielding SSE lines."""
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter as mistral_mod

    async def _fake_astream(_self, request, *, timeout=None) -> AsyncIterator[str]:  # type: ignore[no-redef]
        yield "data: {\"choices\":[{\"delta\":{\"content\":\"m\"}}]}\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(mistral_mod.MistralAdapter, "astream", _fake_astream, raising=True)

    stream = await chat_api_call_async(
        api_endpoint="mistral",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="mistral-large-latest",
        streaming=True,
    )
    parts = []
    async for ln in stream:  # type: ignore[union-attr]
        parts.append(ln)
    assert any(p.startswith("data: ") and "[DONE]" not in p for p in parts)
    assert sum(1 for p in parts if p.strip() == "data: [DONE]") == 1
