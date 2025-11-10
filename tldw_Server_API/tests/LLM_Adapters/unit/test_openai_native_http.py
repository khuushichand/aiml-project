from __future__ import annotations

import os
from typing import Any, Dict, List

import pytest


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_obj: Dict[str, Any] | None = None, lines: List[str] | None = None):
        self.status_code = status_code
        self._json = json_obj or {}
        self._lines = lines or []

    def raise_for_status(self):
        if 400 <= self.status_code:
            import httpx
            request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        return self._json

    def iter_lines(self):
        for l in self._lines:
            yield l


class _FakeStreamCtx:
    def __init__(self, response: _FakeResponse):
        self._resp = response

    def __enter__(self):
        return self._resp

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.last_post = None
        self.last_stream = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, json: Dict[str, Any], headers: Dict[str, str]):
        self.last_post = {"url": url, "json": json, "headers": headers}
        return _FakeResponse(200, {"object": "chat.completion", "choices": [{"message": {"content": "ok"}}]})

    def stream(self, method: str, url: str, json: Dict[str, Any], headers: Dict[str, str]):
        self.last_stream = {"method": method, "url": url, "json": json, "headers": headers}
        lines = [
            "data: {\"choices\":[{\"delta\":{\"content\":\"a\"}}]}",
            "data: [DONE]",
        ]
        return _FakeStreamCtx(_FakeResponse(200, lines=lines))


@pytest.fixture(autouse=True)
def _enable_native_http(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_OPENAI", "1")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    yield


def test_openai_adapter_native_http_non_streaming(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter import OpenAIAdapter
    # Patch adapter factory to return our fake client
    import tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter as openai_mod
    monkeypatch.setattr(openai_mod, "http_client_factory", lambda *a, **k: _FakeClient(*a, **k))

    adapter = OpenAIAdapter()
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "gpt-4o-mini",
        "api_key": "sk-test",
        "temperature": 0.1,
    }
    resp = adapter.chat(req)
    assert resp.get("object") == "chat.completion"


def test_openai_adapter_native_http_streaming(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter import OpenAIAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter as openai_mod
    monkeypatch.setattr(openai_mod, "http_client_factory", lambda *a, **k: _FakeClient(*a, **k))

    adapter = OpenAIAdapter()
    req = {
        "messages": [{"role": "user", "content": "hello"}],
        "model": "gpt-4o-mini",
        "api_key": "sk-test",
        "temperature": 0.2,
        "stream": True,
    }
    chunks = list(adapter.stream(req))
    # Should produce SSE lines with double newlines
    assert any(c.startswith("data: ") for c in chunks)
    assert sum(1 for c in chunks if "[DONE]" in c) == 1
