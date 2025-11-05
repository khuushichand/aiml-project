from __future__ import annotations

from typing import Any, Dict

import pytest


class _CaptureClient:
    def __init__(self):
        self.last_headers: Dict[str, str] | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
        self.last_headers = dict(headers)
        class R:
            status_code = 200
            def raise_for_status(self):
                return None
            def json(self):
                return {"object": "chat.completion", "choices": [{"message": {"content": "ok"}}]}
        return R()

    def stream(self, *a, **k):  # pragma: no cover - not used here
        raise RuntimeError("not used")


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_OPENROUTER", "1")
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    yield


def test_openrouter_headers_include_site_meta(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter import OpenRouterAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter as or_mod

    cap = _CaptureClient()
    monkeypatch.setattr(or_mod, "http_client_factory", lambda *a, **k: cap)

    a = OpenRouterAdapter()
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "meta-llama/llama-3-8b",
        "api_key": "k",
        "app_config": {
            "openrouter_api": {
                "site_url": "https://example.com",
                "site_name": "TLDW-Test",
            }
        },
    }
    out = a.chat(req)
    assert out["object"] == "chat.completion"
    assert cap.last_headers is not None
    # Verify OpenRouter-specific header quirks
    assert cap.last_headers.get("HTTP-Referer") == "https://example.com"
    assert cap.last_headers.get("X-Title") == "TLDW-Test"
    # Authorization preserved
    assert cap.last_headers.get("Authorization", "").startswith("Bearer ")

