import os
import pytest


@pytest.mark.integration
def test_chat_command_replace_mode(monkeypatch, test_client, auth_headers):
    # Enable commands and set injection to replace
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMAND_INJECTION_MODE", "replace")

    # Capture messages payload passed to provider call
    from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint
    captured = {"messages": None}

    def fake_call(**kwargs):
        captured["messages"] = kwargs.get("messages_payload")
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    monkeypatch.setattr(chat_endpoint, "perform_chat_api_call", fake_call)

    # Submit a slash command
    payload = {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "/time"}], "stream": False}
    _ = test_client.post("/api/v1/chat/completions", json=payload, headers=auth_headers)

    # Assert the last user message content is replaced with the command result prefix
    msgs = captured["messages"] or []
    last_user = None
    for m in reversed(msgs):
        if m.get("role") == "user":
            last_user = m
            break
    assert last_user is not None
    parts = last_user.get("content")
    if isinstance(parts, list):
        text_part = next((p for p in parts if p.get("type") == "text"), None)
        assert text_part is not None
        assert text_part.get("text", "").startswith("[/time]")
    elif isinstance(parts, str):
        assert parts.startswith("[/time]")
