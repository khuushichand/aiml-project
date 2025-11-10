from __future__ import annotations

from typing import Any, Dict, List

import pytest


class _CaptureClient:
    def __init__(self):
        self.last_json: Dict[str, Any] | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
        self.last_json = json
        class R:
            status_code = 200
            def raise_for_status(self):
                return None
            def json(self):
                return {"object": "chat.completion", "choices": [{"message": {"content": "ok"}}]}
        return R()

    def stream(self, *a, **k):  # pragma: no cover - not used here
        raise RuntimeError("not used")


@pytest.mark.parametrize("provider,modname,cls_name", [
    ("mistral", "tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter", "MistralAdapter"),
    ("openrouter", "tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter", "OpenRouterAdapter"),
])
def test_tool_choice_and_json_mode_in_payload(monkeypatch, provider: str, modname: str, cls_name: str):
    # Enable native path for these adapters
    flag = "LLM_ADAPTERS_NATIVE_HTTP_MISTRAL" if provider == "mistral" else "LLM_ADAPTERS_NATIVE_HTTP_OPENROUTER"
    monkeypatch.setenv(flag, "1")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    cap = _CaptureClient()
    mod = __import__(modname, fromlist=[cls_name])
    # Adapters call http_client_factory in these modules
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: cap)
    Adapter = getattr(mod, cls_name)
    a = Adapter()
    req = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "dummy",
        "api_key": "k",
        "tools": [{"type": "function", "function": {"name": "do", "parameters": {}}}],
        "tool_choice": "none",
        "response_format": {"type": "json_object"},
    }
    out = a.chat(req)
    assert out["object"] == "chat.completion"
    assert cap.last_json is not None
    assert cap.last_json.get("tool_choice") == "none"
    # JSON mode parity
    rf = cap.last_json.get("response_format")
    assert isinstance(rf, dict) and rf.get("type") == "json_object"
