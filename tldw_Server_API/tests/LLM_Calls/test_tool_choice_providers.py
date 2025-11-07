import pytest


def _dummy_response(payload):
    class R:
        status_code = 200
        def json(self):
            # Echo back the payload to simplify assertions
            return payload
        def raise_for_status(self):
            return None
        def close(self):
            return None
    return R()


def _patch_openai(monkeypatch, captured):
    class _Client:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _dummy_response(json)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter.http_client_factory",
        lambda *args, **kwargs: _Client(),
    )


def _patch_groq(monkeypatch, captured):
    class _Client:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _dummy_response(json)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter.http_client_factory",
        lambda *args, **kwargs: _Client(),
    )


def test_openai_tool_choice_gating(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_openai

    captured = {}
    _patch_openai(monkeypatch, captured)

    messages = [{"role": "user", "content": "hi"}]

    # 1) No tools, function tool_choice should not be set
    chat_with_openai(messages, tool_choice={"type": "function", "function": {"name": "f"}})
    payload = captured["json"]
    assert "tool_choice" not in payload

    # 2) No tools, tool_choice == "none" should be set
    chat_with_openai(messages, tool_choice="none")
    payload = captured["json"]
    assert payload.get("tool_choice") == "none"

    # 3) Tools present, function tool_choice should be honored
    tools = [{"type": "function", "function": {"name": "f", "parameters": {}}}]
    tc = {"type": "function", "function": {"name": "f"}}
    chat_with_openai(messages, tools=tools, tool_choice=tc)
    payload = captured["json"]
    assert payload.get("tool_choice") == tc


def test_groq_tool_choice_gating(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_groq

    captured = {}
    _patch_groq(monkeypatch, captured)

    messages = [{"role": "user", "content": "hi"}]

    # 1) No tools, function tool_choice should not be set
    chat_with_groq(messages, tool_choice={"type": "function", "function": {"name": "f"}})
    payload = captured["json"]
    assert "tool_choice" not in payload

    # 2) No tools, tool_choice == "none" should be set
    chat_with_groq(messages, tool_choice="none")
    payload = captured["json"]
    assert payload.get("tool_choice") == "none"

    # 3) Tools present, function tool_choice should be honored
    tools = [{"type": "function", "function": {"name": "f", "parameters": {}}}]
    tc = {"type": "function", "function": {"name": "f"}}
    chat_with_groq(messages, tools=tools, tool_choice=tc)
    payload = captured["json"]
    assert payload.get("tool_choice") == tc
