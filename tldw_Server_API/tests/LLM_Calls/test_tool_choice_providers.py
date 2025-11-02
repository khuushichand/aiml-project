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


class _DummySession:
    def __init__(self, captured):
        self.captured = captured
    def post(self, url, headers=None, json=None, timeout=None, stream=False):
        # Capture the outgoing JSON payload for assertions
        self.captured["url"] = url
        self.captured["headers"] = headers
        self.captured["json"] = json
        self.captured["timeout"] = timeout
        self.captured["stream"] = stream
        return _dummy_response(json)
    def close(self):
        return None


def _patch_openai(monkeypatch, captured):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries",
        lambda **kwargs: _DummySession(captured),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {"openai_api": {"api_key": "key", "api_base_url": "https://api.openai.local/v1"}},
    )


def _patch_groq(monkeypatch, captured):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries",
        lambda **kwargs: _DummySession(captured),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {"groq_api": {"api_key": "key", "api_base_url": "https://api.groq.local/openai/v1"}},
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
