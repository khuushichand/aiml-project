from __future__ import annotations

import pytest


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_obj=None, lines=None):
        self.status_code = status_code
        self._json = json_obj or {"object": "chat.completion", "choices": [{"message": {"content": "ok"}}]}
        self._lines = lines or [
            "data: chunk",
            "data: [DONE]",
        ]

    def raise_for_status(self):
        if 400 <= self.status_code:
            import httpx
            req = httpx.Request("POST", "https://example.com")
            resp = httpx.Response(self.status_code, request=req)
            raise httpx.HTTPStatusError("err", request=req, response=resp)

    def json(self):
        return self._json

    def iter_lines(self):
        for l in self._lines:
            yield l


class _FakeStreamCtx:
    def __init__(self, r: _FakeResponse):
        self._r = r

    def __enter__(self):
        return self._r

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json, headers):
        return _FakeResponse(200)

    def stream(self, method, url, json, headers):
        return _FakeStreamCtx(_FakeResponse(200))


@pytest.fixture(autouse=True)
def _enable_native(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_GROQ", "1")
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_OPENROUTER", "1")
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    yield


async def test_orchestrator_async_groq_native(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import httpx
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    resp = await chat_api_call_async(
        api_endpoint="groq",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="llama3-8b",
        streaming=False,
    )
    assert resp.get("object") == "chat.completion"
    stream = await chat_api_call_async(
        api_endpoint="groq",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="llama3-8b",
        streaming=True,
    )
    chunks = []
    async for ch in stream:  # type: ignore
        chunks.append(ch)
    assert any(c.startswith("data: ") for c in chunks)
    assert sum(1 for c in chunks if "[DONE]" in c) == 1


async def test_orchestrator_async_openrouter_native(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import httpx
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    resp = await chat_api_call_async(
        api_endpoint="openrouter",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="meta-llama/llama-3-8b",
        streaming=False,
    )
    assert resp.get("object") == "chat.completion"
    stream = await chat_api_call_async(
        api_endpoint="openrouter",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="meta-llama/llama-3-8b",
        streaming=True,
    )
    parts = []
    async for ch in stream:  # type: ignore
        parts.append(ch)
    assert any(p.startswith("data: ") for p in parts)
    assert sum(1 for p in parts if "[DONE]" in p) == 1
