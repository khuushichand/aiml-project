from __future__ import annotations

from typing import Any, Dict, List

import pytest


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_obj: Dict[str, Any] | None = None, lines: List[str] | None = None):
        self.status_code = status_code
        self._json = json_obj or {"object": "chat.completion", "choices": [{"message": {"content": "ok"}}]}
        self._lines = lines or [
            "data: chunk",
            "data: [DONE]",
        ]

    def raise_for_status(self):
        if 400 <= self.status_code:
            import httpx
            req = httpx.Request("POST", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions")
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

    def post(self, url: str, json: Dict[str, Any], headers: Dict[str, str]):
        assert url.endswith("/chat/completions")
        assert headers.get("authorization") or headers.get("Authorization")
        assert isinstance(json.get("messages"), list)
        return _FakeResponse(200)

    def stream(self, method: str, url: str, json: Dict[str, Any], headers: Dict[str, str]):
        return _FakeStreamCtx(_FakeResponse(200))


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_QWEN", "1")
    monkeypatch.setenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    yield


def test_qwen_adapter_native_http_non_streaming(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter import QwenAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter as qwen_mod
    # Patch both the internal alias and the adapter's exposed factory
    monkeypatch.setattr(qwen_mod, "_hc_create_client", lambda *a, **k: _FakeClient(*a, **k))
    monkeypatch.setattr(qwen_mod, "http_client_factory", lambda *a, **k: _FakeClient(*a, **k))
    a = QwenAdapter()
    r = a.chat({"messages": [{"role": "user", "content": "hi"}], "model": "qwen-plus", "api_key": "k"})
    assert r.get("object") == "chat.completion"


def test_qwen_adapter_native_http_streaming(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter import QwenAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter as qwen_mod
    monkeypatch.setattr(qwen_mod, "_hc_create_client", lambda *a, **k: _FakeClient(*a, **k))
    monkeypatch.setattr(qwen_mod, "http_client_factory", lambda *a, **k: _FakeClient(*a, **k))
    a = QwenAdapter()
    chunks = list(a.stream({"messages": [{"role": "user", "content": "hi"}], "model": "qwen-plus", "api_key": "k", "stream": True}))
    assert any(c.startswith("data: ") for c in chunks)
    assert sum(1 for c in chunks if "[DONE]" in c) == 1


def test_qwen_base_url_uses_region_preset_when_no_override(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter import QwenAdapter

    monkeypatch.delenv("QWEN_BASE_URL", raising=False)
    monkeypatch.delenv("QWEN_REGION", raising=False)
    adapter = QwenAdapter()
    request = {"app_config": {"qwen_api": {"region": "us"}}}
    assert (
        adapter._base_url(request["app_config"], request)
        == "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    )


def test_qwen_base_url_precedence_request_env_config_region(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter import QwenAdapter

    adapter = QwenAdapter()
    cfg = {"qwen_api": {"api_base_url": "https://cfg.example.com/v1", "region": "cn"}}

    monkeypatch.setenv("QWEN_BASE_URL", "https://env.example.com/v1")
    request = {"base_url": "https://req.example.com/v1", "app_config": cfg}
    assert adapter._base_url(cfg, request) == "https://req.example.com/v1"

    request = {"app_config": cfg}
    assert adapter._base_url(cfg, request) == "https://env.example.com/v1"

    monkeypatch.delenv("QWEN_BASE_URL", raising=False)
    assert adapter._base_url(cfg, request) == "https://cfg.example.com/v1"

    cfg_without_base = {"qwen_api": {"region": "cn"}}
    assert adapter._base_url(cfg_without_base, {"app_config": cfg_without_base}) == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
