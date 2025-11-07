"""
Async integration tests for Bedrock adapter dispatch via chat_api_call_async.
"""

from __future__ import annotations

import pytest


class _FakeResp:
    def __init__(self, lines):
        self._lines = list(lines)
        self.status_code = 200

    def raise_for_status(self):
        return None

    def iter_lines(self):
        for l in self._lines:
            yield l


class _FakeStreamCtx:
    def __init__(self, resp):
        self._r = resp

    def __enter__(self):
        return self._r

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeClient:
    def __init__(self, *, lines, calls=None):
        self._lines = list(lines)
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):
        # Non-streaming path not covered here
        class _R:
            status_code = 200
            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}
            def raise_for_status(self):
                return None
        return _R()

    def stream(self, *args, **kwargs):
        if self._calls is not None:
            self._calls["n"] = self._calls.get("n", 0) + 1
        return _FakeStreamCtx(_FakeResp(self._lines))


async def _collect_async(it):
    out = []
    async for x in it:  # type: ignore[union-attr]
        out.append(x)
    return out


@pytest.mark.unit
async def test_bedrock_async_stream_via_orchestrator(monkeypatch):
    # Patch Bedrock adapter http client to emit fake SSE lines
    import tldw_Server_API.app.core.LLM_Calls.providers.bedrock_adapter as bedrock_mod
    lines = [
        b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n',
        b'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
    ]
    monkeypatch.setattr(bedrock_mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=lines))

    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async

    it = await chat_api_call_async(
        api_endpoint="bedrock",
        messages_payload=[{"role": "user", "content": "hi"}],
        api_key="x",
        model="meta.llama3-8b-instruct",
        streaming=True,
    )
    chunks = await _collect_async(it)
    assert chunks[-1].strip() == "data: [DONE]"
    assert "hello" in "".join(chunks)


@pytest.mark.unit
async def test_bedrock_async_non_stream_via_orchestrator(monkeypatch):
    # Patch Bedrock adapter client to control post response
    import tldw_Server_API.app.core.LLM_Calls.providers.bedrock_adapter as bedrock_mod
    monkeypatch.setattr(bedrock_mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=[]))

    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call_async

    resp = await chat_api_call_async(
        api_endpoint="bedrock",
        messages_payload=[{"role": "user", "content": "hi"}],
        api_key="x",
        model="meta.llama3-8b-instruct",
        streaming=False,
    )
    assert isinstance(resp, dict)
    # Minimal shape check
    assert "choices" in resp

