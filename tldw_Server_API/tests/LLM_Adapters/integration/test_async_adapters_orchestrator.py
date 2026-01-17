"""
Async integration tests for chat_orchestrator.chat_api_call_async routing
through adapter-backed async shims with adapters enabled.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest


@pytest.fixture(autouse=True)
def _enable_async_adapters(monkeypatch):
    # Ensure native HTTP path stays off for these tests
    monkeypatch.delenv("LLM_ADAPTERS_NATIVE_HTTP_OPENAI", raising=False)
    yield


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_obj: Dict[str, Any] | None = None, lines: List[str] | None = None):
        self.status_code = status_code
        self._json = json_obj or {
            "id": "cmpl-test",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        }
        self._lines = lines or [
            "data: {\"choices\":[{\"delta\":{\"content\":\"x\"}}]}\n\n",
            "data: [DONE]\n\n",
        ]

    def raise_for_status(self):
        if 400 <= self.status_code:
            import httpx
            req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            resp = httpx.Response(self.status_code, request=req)
            raise httpx.HTTPStatusError("err", request=req, response=resp)

    def json(self):
        return self._json

    def iter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamCtx:
    def __init__(self, resp: _FakeResponse):
        self._resp = resp

    def __enter__(self):
        return self._resp

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):
        return _FakeResponse()

    def stream(self, *args, **kwargs):
        return _FakeStreamCtx(_FakeResponse())


async def test_chat_api_call_async_non_streaming(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter as openai_mod
    monkeypatch.setattr(openai_mod, "http_client_factory", lambda *a, **k: _FakeClient())

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
    import tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter as openai_mod
    monkeypatch.setattr(openai_mod, "http_client_factory", lambda *a, **k: _FakeClient())

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
