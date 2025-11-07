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
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_OPENAI", "1")
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_GROQ", "1")
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_OPENROUTER", "1")
    yield


def test_openai_app_config_base_url_and_timeout(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter import OpenAIAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter as mod

    captured: Dict[str, Any] = {}

    def _factory(*args, timeout: float | None = None, **kwargs):
        captured["timeout"] = timeout
        return _FakeClient(captured)

    monkeypatch.setattr(mod, "http_client_factory", _factory, raising=True)

    a = OpenAIAdapter()
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "gpt-4o-mini",
        "api_key": "k",
        "app_config": {"openai_api": {"api_base_url": "https://mock.openai.local/v1", "api_timeout": 12}},
    }
    _ = a.chat(req)
    assert captured.get("timeout") == 12
    assert str(captured.get("url", "")).startswith("https://mock.openai.local/v1/chat/completions")


def test_groq_app_config_base_url_and_timeout(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter import GroqAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter as mod

    captured: Dict[str, Any] = {}
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, timeout=None, **k: (captured.setdefault("timeout", timeout) or _FakeClient(captured)) and _FakeClient(captured), raising=True)

    a = GroqAdapter()
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "llama3-8b",
        "api_key": "k",
        "app_config": {"groq_api": {"api_base_url": "https://api.groq.test/openai/v1", "api_timeout": 22}},
    }
    _ = a.chat(req)
    assert captured.get("timeout") == 22
    assert str(captured.get("url", "")).startswith("https://api.groq.test/openai/v1/chat/completions")


def test_openrouter_app_config_base_url_and_timeout(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter import OpenRouterAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter as mod

    captured: Dict[str, Any] = {}

    def _factory(*args, timeout: float | None = None, **kwargs):
        captured["timeout"] = timeout
        return _FakeClient(captured)

    monkeypatch.setattr(mod, "http_client_factory", _factory, raising=True)

    a = OpenRouterAdapter()
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "meta-llama/llama-3-8b",
        "api_key": "k",
        "app_config": {"openrouter_api": {"api_base_url": "https://openrouter.mock/api/v1", "api_timeout": 44}},
    }
    _ = a.chat(req)
    assert captured.get("timeout") == 44
    assert str(captured.get("url", "")).startswith("https://openrouter.mock/api/v1/chat/completions")

