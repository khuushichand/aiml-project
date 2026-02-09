import pytest

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError


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
    from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call

    captured = {}
    _patch_openai(monkeypatch, captured)

    messages = [{"role": "user", "content": "hi"}]

    # 1) No tools, tool_choice should raise a deterministic 400
    with pytest.raises(ChatBadRequestError):
        perform_chat_api_call(
            api_provider="openai",
            messages=messages,
            model="gpt-4o-mini",
            tool_choice={"type": "function", "function": {"name": "f"}},
        )

    # 2) No tools, tool_choice == "none" should be allowed
    perform_chat_api_call(api_provider="openai", messages=messages, model="gpt-4o-mini", tool_choice="none")
    payload = captured["json"]
    assert payload.get("tool_choice") == "none"

    # 3) Tools present, function tool_choice should be honored
    tools = [{"type": "function", "function": {"name": "f", "parameters": {}}}]
    tc = {"type": "function", "function": {"name": "f"}}
    perform_chat_api_call(api_provider="openai", messages=messages, model="gpt-4o-mini", tools=tools, tool_choice=tc)
    payload = captured["json"]
    assert payload.get("tool_choice") == tc


def test_groq_tool_choice_gating(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call

    captured = {}
    _patch_groq(monkeypatch, captured)

    messages = [{"role": "user", "content": "hi"}]

    # 1) No tools, tool_choice should raise a deterministic 400
    with pytest.raises(ChatBadRequestError):
        perform_chat_api_call(
            api_provider="groq",
            messages=messages,
            model="llama-3.1-8b-instant",
            tool_choice={"type": "function", "function": {"name": "f"}},
        )

    # 2) No tools, tool_choice == "none" should be allowed
    perform_chat_api_call(api_provider="groq", messages=messages, model="llama-3.1-8b-instant", tool_choice="none")
    payload = captured["json"]
    assert payload.get("tool_choice") == "none"

    # 3) Tools present, function tool_choice should be honored
    tools = [{"type": "function", "function": {"name": "f", "parameters": {}}}]
    tc = {"type": "function", "function": {"name": "f"}}
    perform_chat_api_call(api_provider="groq", messages=messages, model="llama-3.1-8b-instant", tools=tools, tool_choice=tc)
    payload = captured["json"]
    assert payload.get("tool_choice") == tc
