import json

import pytest


class _FakeResp:
    def __init__(self, status_code=200, json_obj=None, text="", lines=None):
        self.status_code = status_code
        self._json_obj = json_obj if json_obj is not None else {}
        self.text = text
        self._lines = list(lines or [])

    def json(self):
        return self._json_obj

    def raise_for_status(self):
        import requests

        if self.status_code and int(self.status_code) >= 400:
            err = requests.exceptions.HTTPError("HTTP error")
            err.response = self
            raise err
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_lines(self):
        for line in self._lines:
            yield line


class _FakeClient:
    def __init__(self, *, post_resp: _FakeResp | None = None, stream_lines=None):
        self._post_resp = post_resp
        self._stream_lines = list(stream_lines or [])
        self.last_json = None
        self.last_url = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *, headers=None, json=None):
        self.last_url = url
        self.last_json = json
        return self._post_resp or _FakeResp(status_code=200, json_obj={"ok": True})

    def stream(self, method, url, *, headers=None, json=None):
        self.last_url = url
        self.last_json = json
        return _FakeResp(status_code=200, lines=self._stream_lines)


def test_dispatch_to_bedrock_adapter_non_stream(monkeypatch):
    # Patch adapter factory to avoid network
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(
        post_resp=_FakeResp(status_code=200, json_obj={"choices": [{"message": {"content": "ok"}}]})
    )
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)

    from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call

    resp = perform_chat_api_call(
        api_provider="bedrock",
        messages=[{"role": "user", "content": "hi"}],
        model="meta.llama3-8b-instruct",
        api_key="key",
        streaming=False,
    )
    assert isinstance(fake.last_json, dict)
    assert fake.last_json.get("stream") is False
    assert fake.last_url.endswith("/v1/chat/completions")


def test_dispatch_to_bedrock_adapter_stream(monkeypatch):
    # Patch adapter factory to provide streaming lines (no DONE marker)
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    lines = [
        b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        b'data: {"choices":[{"delta":{"content":" Bedrock"}}]}',
    ]
    fake = _FakeClient(stream_lines=lines)
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)

    from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call

    gen = perform_chat_api_call(
        api_provider="bedrock",
        messages=[{"role": "user", "content": "hi"}],
        model="meta.llama3-8b-instruct",
        api_key="key",
        streaming=True,
    )
    chunks = list(gen)
    assert len(chunks) >= 3  # two chunks + DONE
    assert chunks[0].startswith("data: ")
    assert chunks[-1].strip().endswith("[DONE]")
