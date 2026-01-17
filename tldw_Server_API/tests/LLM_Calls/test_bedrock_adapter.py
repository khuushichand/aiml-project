import os

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

    # streaming context manager shape
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


def test_bedrock_adapter_non_stream_uses_factory_and_sets_stream(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=400, json_obj={}, text="bad"))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)

    adapter = mod.BedrockAdapter()
    with pytest.raises(Exception):  # normalized to ChatBadRequestError by adapter
        adapter.chat(
            {
                "messages": [{"role": "user", "content": "hi"}],
                "model": "meta.llama3-8b-instruct",
                "api_key": "key",
            }
        )

    assert isinstance(fake.last_json, dict)
    assert fake.last_json.get("stream") is False


def test_bedrock_adapter_base_url_from_runtime_endpoint(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)

    # Ensure our env var controls the base URL
    monkeypatch.setenv("BEDROCK_RUNTIME_ENDPOINT", "https://bedrock-runtime.us-test-1.amazonaws.com")
    try:
        adapter = mod.BedrockAdapter()
        adapter.chat(
            {
                "messages": [{"role": "user", "content": "ping"}],
                "model": "meta.llama3-8b-instruct",
                "api_key": "key",
            }
        )
        assert fake.last_url == "https://bedrock-runtime.us-test-1.amazonaws.com/openai/v1/chat/completions"
    finally:
        monkeypatch.delenv("BEDROCK_RUNTIME_ENDPOINT", raising=False)
