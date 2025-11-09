from __future__ import annotations

import pytest


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_obj=None, lines=None):
        self.status_code = status_code
        self._json = json_obj or {"object": "chat.completion", "choices": [{"message": {"content": "ok"}}]}
        self._lines = lines or [
            "data: {\"type\":\"content_block_delta\",\"delta\":{\"type\":\"text_delta\",\"text\":\"x\"}}",
            "data: [DONE]",
        ]

    def raise_for_status(self):
        if 400 <= self.status_code:
            import httpx
            req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
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
def _enable_anthropic_native(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")
    monkeypatch.setenv("LLM_ADAPTERS_ANTHROPIC", "1")
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_ANTHROPIC", "1")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
    yield


async def test_orchestrator_async_anthropic_native_non_stream(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import httpx
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    resp = await chat_api_call_async(
        api_endpoint="anthropic",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="claude-sonnet",
        streaming=False,
    )
    assert isinstance(resp, dict)
    assert resp.get("object") == "chat.completion"


async def test_orchestrator_async_anthropic_native_stream(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async
    import httpx
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    stream = await chat_api_call_async(
        api_endpoint="anthropic",
        messages_payload=[{"role": "user", "content": "hi"}],
        model="claude-sonnet",
        streaming=True,
    )
    chunks = []
    async for ch in stream:  # type: ignore
        chunks.append(ch)
    assert any(c.startswith("data: ") for c in chunks)
    assert sum(1 for c in chunks if "[DONE]" in c) == 1
