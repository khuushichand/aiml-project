from __future__ import annotations

from typing import Any, Dict

import pytest


class _FakeResponse:
    def __init__(self, json_obj: Dict[str, Any] | None = None):
        self.status_code = 200
        self._json = json_obj or {"object": "chat.completion", "choices": [{"message": {"content": "ok"}}]}

    def raise_for_status(self):
        return None

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, captured: Dict[str, Any]):
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
        self._captured["url"] = url
        self._captured["headers"] = headers
        self._captured["json"] = json
        return _FakeResponse()

    def stream(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("stream() not expected")


@pytest.fixture(autouse=True)
def _enable_adapters(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_HUGGINGFACE", "1")
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_MISTRAL", "1")
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_QWEN", "1")
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_DEEPSEEK", "1")
    yield


def test_huggingface_app_config_timeout(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter import HuggingFaceAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter as mod

    captured: Dict[str, Any] = {}
    # Patch the adapter's exposed factory so the adapter path is used without network
    def _factory(*a, timeout=None, **k):
        captured.setdefault("timeout", timeout)
        return _FakeClient(captured)

    monkeypatch.setattr(mod, "http_client_factory", _factory, raising=True)

    a = HuggingFaceAdapter()
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "mistralai/Mistral-7B-Instruct-v0.1",
        "api_key": "k",
        "app_config": {"huggingface_api": {"api_base_url": "https://api-inference.huggingface.co/v1", "api_timeout": 77}},
    }
    _ = a.chat(req)
    assert captured.get("timeout") == 77
    assert str(captured.get("url", "")).startswith("https://api-inference.huggingface.co/v1")


def test_mistral_app_config_overrides(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter import MistralAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter as mod

    captured: Dict[str, Any] = {}

    def _factory(*args, timeout: float | None = None, **kwargs):
        captured["timeout"] = timeout
        return mod.http_client_factory(*args, **kwargs) if False else _FakeClient(captured)

    monkeypatch.setattr(mod, "http_client_factory", _factory, raising=True)

    a = MistralAdapter()
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "mistral-large-latest",
        "api_key": "k",
        "app_config": {"mistral_api": {"api_base_url": "https://api.mistral.mock/v1", "api_timeout": 66}},
    }
    _ = a.chat(req)
    assert captured.get("timeout") == 66
    assert str(captured.get("url", "")).startswith("https://api.mistral.mock/v1/chat/completions")


def test_qwen_app_config_timeout(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter import QwenAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter as mod

    captured: Dict[str, Any] = {}
    def _factory(*a, timeout=None, **k):
        captured.setdefault("timeout", timeout)
        return _FakeClient(captured)

    monkeypatch.setattr(mod, "http_client_factory", _factory, raising=True)

    a = QwenAdapter()
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "qwen2-7b-instruct",
        "api_key": "k",
        "app_config": {"qwen_api": {"api_base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "api_timeout": 55}},
    }
    _ = a.chat(req)
    assert captured.get("timeout") == 55


def test_deepseek_app_config_timeout(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.deepseek_adapter import DeepSeekAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.deepseek_adapter as mod

    captured: Dict[str, Any] = {}
    def _factory(*a, timeout=None, **k):
        captured.setdefault("timeout", timeout)
        return _FakeClient(captured)

    monkeypatch.setattr(mod, "http_client_factory", _factory, raising=True)

    a = DeepSeekAdapter()
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "deepseek-chat",
        "api_key": "k",
        "app_config": {"deepseek_api": {"api_base_url": "https://api.deepseek.com", "api_timeout": 88}},
    }
    _ = a.chat(req)
    assert captured.get("timeout") == 88
