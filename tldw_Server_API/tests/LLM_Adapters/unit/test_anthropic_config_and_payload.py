from __future__ import annotations

from typing import Any, Dict, List

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

    # Capture POST call inputs for assertions
    def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
        self._captured["url"] = url
        self._captured["json"] = json
        self._captured["headers"] = headers
        return _FakeResponse()

    # Not exercised in these tests
    def stream(self, *args, **kwargs):  # pragma: no cover - not used here
        raise AssertionError("stream() not expected in these tests")


@pytest.fixture(autouse=True)
def _enable_anthropic_native(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_ANTHROPIC", "1")
    yield


def test_anthropic_app_config_base_url_and_timeout(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as anth_mod

    captured: Dict[str, Any] = {}

    def _factory(*args, timeout: float | None = None, **kwargs):
        captured["timeout"] = timeout
        return _FakeClient(captured)

    monkeypatch.setattr(anth_mod, "http_client_factory", _factory, raising=True)

    a = AnthropicAdapter()
    request = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "claude-sonnet-4.5",
        "api_key": "k",
        "app_config": {"anthropic_api": {"api_base_url": "https://alt.anthropic.local/v1", "api_timeout": 33}},
    }
    _ = a.chat(request)
    assert captured.get("timeout") == 33
    assert str(captured.get("url", "")).startswith("https://alt.anthropic.local/v1/messages")


def test_anthropic_tool_choice_none_omits_tools(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as anth_mod

    captured: Dict[str, Any] = {}
    monkeypatch.setattr(anth_mod, "http_client_factory", lambda *a, **k: _FakeClient(captured), raising=True)

    tools = [
        {"type": "function", "function": {"name": "lookup", "description": "d", "parameters": {"type": "object"}}},
    ]
    a = AnthropicAdapter()
    request = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "claude-haiku-4.5",
        "api_key": "k",
        "tools": tools,
        "tool_choice": "none",
    }
    _ = a.chat(request)
    payload = captured.get("json") or {}
    # When tool_choice == "none" we omit tools entirely
    assert "tools" not in payload


def test_anthropic_tool_choice_specific_maps(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as anth_mod

    captured: Dict[str, Any] = {}
    monkeypatch.setattr(anth_mod, "http_client_factory", lambda *a, **k: _FakeClient(captured), raising=True)

    tools = [
        {"type": "function", "function": {"name": "lookup", "description": "d", "parameters": {"type": "object"}}},
    ]
    a = AnthropicAdapter()
    request = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "claude-opus-4.1",
        "api_key": "k",
        "tools": tools,
        "tool_choice": {"type": "function", "function": {"name": "lookup"}},
    }
    _ = a.chat(request)
    payload = captured.get("json") or {}
    assert isinstance(payload.get("tools"), list) and payload["tools"][0]["name"] == "lookup"
    assert payload["tools"][0].get("input_schema") == {"type": "object"}
    assert payload.get("tool_choice") == {"type": "tool", "name": "lookup"}


def test_anthropic_tool_results_and_calls_mapped(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as anth_mod

    captured: Dict[str, Any] = {}
    monkeypatch.setattr(anth_mod, "http_client_factory", lambda *a, **k: _FakeClient(captured), raising=True)

    request = {
        "messages": [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "Calling tool",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": "{\"query\":\"mars\"}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "tool result"},
        ],
        "model": "claude-opus-4.1",
        "api_key": "k",
    }
    _ = AnthropicAdapter().chat(request)
    payload = captured.get("json") or {}
    msgs: List[Dict[str, Any]] = payload.get("messages", [])

    assistant_msg = next((m for m in msgs if m.get("role") == "assistant"), {})
    tool_use_blocks = [b for b in assistant_msg.get("content", []) if b.get("type") == "tool_use"]
    assert tool_use_blocks
    assert tool_use_blocks[0]["id"] == "call_1"
    assert tool_use_blocks[0]["name"] == "lookup"
    assert tool_use_blocks[0]["input"] == {"query": "mars"}

    tool_result_msgs = [
        m for m in msgs
        if m.get("role") == "user" and any(b.get("type") == "tool_result" for b in m.get("content", []))
    ]
    assert tool_result_msgs
    tool_block = next(b for b in tool_result_msgs[0]["content"] if b.get("type") == "tool_result")
    assert tool_block["tool_use_id"] == "call_1"
    assert tool_block["content"] == "tool result"


def test_anthropic_malformed_tools_rejected(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as anth_mod
    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError

    captured: Dict[str, Any] = {}
    monkeypatch.setattr(anth_mod, "http_client_factory", lambda *a, **k: _FakeClient(captured), raising=True)

    tools = [None, "x", {}, {"type": "function", "function": {"name": None}}, {"type": "other"}]
    a = AnthropicAdapter()
    request = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "claude-haiku-4.5",
        "api_key": "k",
        "tools": tools,
    }
    with pytest.raises(ChatBadRequestError):
        _ = a.chat(request)


def test_anthropic_multimodal_image_data_url(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as anth_mod

    captured: Dict[str, Any] = {}
    monkeypatch.setattr(anth_mod, "http_client_factory", lambda *a, **k: _FakeClient(captured), raising=True)

    msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": "hello"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
        ],
    }
    a = AnthropicAdapter()
    request = {"messages": [msg], "model": "claude-haiku-4.5", "api_key": "k"}
    _ = a.chat(request)
    payload = captured.get("json") or {}
    parts: List[Dict[str, Any]] = payload.get("messages", [{}])[0].get("content", [])
    assert any(p.get("type") == "text" for p in parts)
    img = next((p for p in parts if p.get("type") == "image"), None)
    assert img and img.get("source", {}).get("type") == "base64"
    assert img["source"].get("media_type") == "image/png"
    assert img["source"].get("data") == "QUJD"


def test_anthropic_multimodal_invalid_image_url_ignored(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as anth_mod

    captured: Dict[str, Any] = {}
    monkeypatch.setattr(anth_mod, "http_client_factory", lambda *a, **k: _FakeClient(captured), raising=True)

    msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": "hello"},
            {"type": "image_url", "image_url": {"url": "ftp://invalid.example/image.png"}},
        ],
    }
    a = AnthropicAdapter()
    request = {"messages": [msg], "model": "claude-haiku-4.5", "api_key": "k"}
    _ = a.chat(request)
    payload = captured.get("json") or {}
    parts: List[Dict[str, Any]] = payload.get("messages", [{}])[0].get("content", [])
    assert any(p.get("type") == "text" for p in parts)
    assert not any(p.get("type") == "image" for p in parts)
