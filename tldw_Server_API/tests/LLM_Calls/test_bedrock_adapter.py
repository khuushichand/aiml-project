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
        self.last_headers = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *, headers=None, json=None):
        self.last_url = url
        self.last_headers = dict(headers or {})
        self.last_json = json
        return self._post_resp or _FakeResp(status_code=200, json_obj={"ok": True})

    def stream(self, method, url, *, headers=None, json=None):
        self.last_url = url
        self.last_headers = dict(headers or {})
        self.last_json = json
        return _FakeResp(status_code=200, lines=self._stream_lines)


def test_bedrock_adapter_non_stream_uses_factory_and_sets_stream(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=400, json_obj={}, text="bad"))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE123")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-example-key")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)

    adapter = mod.BedrockAdapter()
    with pytest.raises(Exception):  # normalized to ChatBadRequestError by adapter
        adapter.chat(
            {
                "messages": [{"role": "user", "content": "hi"}],
                "model": "meta.llama3-8b-instruct",
                "api_key": "key",
                "base_url": "https://bedrock-runtime.us-test-1.amazonaws.com/openai",
            }
        )

    assert isinstance(fake.last_json, dict)
    assert fake.last_json.get("stream") is False
    assert str((fake.last_headers or {}).get("Authorization", "")).startswith("AWS4-HMAC-SHA256 ")


def test_bedrock_adapter_base_url_from_runtime_endpoint(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE123")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-example-key")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)

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
        assert str((fake.last_headers or {}).get("Authorization", "")).startswith("AWS4-HMAC-SHA256 ")
    finally:
        monkeypatch.delenv("BEDROCK_RUNTIME_ENDPOINT", raising=False)


def test_bedrock_adapter_runtime_endpoint_openai_suffix_is_normalized(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE123")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-example-key")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("BEDROCK_RUNTIME_ENDPOINT", "https://bedrock-runtime.us-test-1.amazonaws.com/openai")

    try:
        adapter = mod.BedrockAdapter()
        adapter.chat(
            {
                "messages": [{"role": "user", "content": "ping"}],
                "model": "meta.llama3-8b-instruct",
            }
        )
        assert fake.last_url == "https://bedrock-runtime.us-test-1.amazonaws.com/openai/v1/chat/completions"
    finally:
        monkeypatch.delenv("BEDROCK_RUNTIME_ENDPOINT", raising=False)


def test_bedrock_adapter_infers_region_from_host_before_env(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE123")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-example-key")
    monkeypatch.setenv("BEDROCK_REGION", "us-east-1")

    adapter = mod.BedrockAdapter()
    adapter.chat(
        {
            "messages": [{"role": "user", "content": "ping"}],
            "model": "meta.llama3-8b-instruct",
            "base_url": "https://bedrock-runtime.us-test-2.amazonaws.com/openai/v1",
        }
    )
    auth = str((fake.last_headers or {}).get("Authorization", ""))
    assert "/us-test-2/bedrock/aws4_request" in auth


def test_bedrock_adapter_local_proxy_keeps_bearer_compat(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)

    adapter = mod.BedrockAdapter()
    adapter.chat(
        {
            "messages": [{"role": "user", "content": "ping"}],
            "model": "meta.llama3-8b-instruct",
            "api_key": "proxy-token",
            "base_url": "http://127.0.0.1:9000/openai",
        }
    )
    assert fake.last_url == "http://127.0.0.1:9000/openai/v1/chat/completions"
    assert (fake.last_headers or {}).get("Authorization") == "Bearer proxy-token"


def test_bedrock_adapter_runtime_host_allows_bearer_api_key(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)

    adapter = mod.BedrockAdapter()
    adapter.chat(
        {
            "messages": [{"role": "user", "content": "ping"}],
            "model": "meta.llama3-8b-instruct",
            "api_key": "runtime-bearer-key",
            "base_url": "https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1",
        }
    )
    assert (fake.last_headers or {}).get("Authorization") == "Bearer runtime-bearer-key"


def test_bedrock_adapter_infers_region_from_runtime_fips_host(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE123")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-example-key")
    monkeypatch.setenv("BEDROCK_REGION", "us-east-1")

    adapter = mod.BedrockAdapter()
    adapter.chat(
        {
            "messages": [{"role": "user", "content": "ping"}],
            "model": "meta.llama3-8b-instruct",
            "base_url": "https://bedrock-runtime-fips.us-west-2.amazonaws.com/openai/v1",
        }
    )
    auth = str((fake.last_headers or {}).get("Authorization", ""))
    assert "/us-west-2/bedrock/aws4_request" in auth


def test_bedrock_adapter_runtime_api_aws_host_uses_sigv4(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE123")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-example-key")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)

    adapter = mod.BedrockAdapter()
    adapter.chat(
        {
            "messages": [{"role": "user", "content": "ping"}],
            "model": "meta.llama3-8b-instruct",
            "base_url": "https://bedrock-runtime.us-west-2.api.aws/openai/v1",
        }
    )
    auth = str((fake.last_headers or {}).get("Authorization", ""))
    assert auth.startswith("AWS4-HMAC-SHA256 ")
    assert "/us-west-2/bedrock/aws4_request" in auth


def test_bedrock_adapter_mantle_host_uses_bearer_api_key(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("BEDROCK_API_KEY", raising=False)
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)

    adapter = mod.BedrockAdapter()
    adapter.chat(
        {
            "messages": [{"role": "user", "content": "ping"}],
            "model": "openai.gpt-oss-20b-1:0",
            "api_key": "mantle-api-key",
            "base_url": "https://bedrock-mantle.us-west-2.api.aws/v1",
        }
    )
    assert (fake.last_headers or {}).get("Authorization") == "Bearer mantle-api-key"


def test_bedrock_adapter_mantle_host_uses_sigv4_without_api_key(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE123")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-example-key")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("BEDROCK_API_KEY", raising=False)
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)

    adapter = mod.BedrockAdapter()
    adapter.chat(
        {
            "messages": [{"role": "user", "content": "ping"}],
            "model": "openai.gpt-oss-20b-1:0",
            "base_url": "https://bedrock-mantle.us-west-2.api.aws/v1",
        }
    )
    auth = str((fake.last_headers or {}).get("Authorization", ""))
    assert auth.startswith("AWS4-HMAC-SHA256 ")
    assert "/us-west-2/bedrock/aws4_request" in auth


def test_bedrock_adapter_mantle_host_missing_auth_fails_fast(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers import bedrock_adapter as mod

    fake = _FakeClient(post_resp=_FakeResp(status_code=200, json_obj={"ok": True}))
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: fake)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("BEDROCK_API_KEY", raising=False)
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)

    adapter = mod.BedrockAdapter()
    with pytest.raises(Exception) as exc:
        adapter.chat(
            {
                "messages": [{"role": "user", "content": "ping"}],
                "model": "openai.gpt-oss-20b-1:0",
                "base_url": "https://bedrock-mantle.us-west-2.api.aws/v1",
            }
        )

    text = str(exc.value).lower()
    assert "mantle" in text
    assert "authentication" in text
