import os
from typing import Any, Dict, List, Optional

import pytest

from tldw_Server_API.app.core.Chat import chat_orchestrator


def test_system_injection_for_time(monkeypatch):
    # Enable commands and system injection
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMAND_INJECTION_MODE", "system")

    captured_payload: List[Dict[str, Any]] = []

    def fake_call(api_endpoint: str, messages_payload: List[Dict[str, Any]], **kwargs):
        nonlocal captured_payload
        captured_payload = messages_payload
        return "ok"

    monkeypatch.setattr(chat_orchestrator, "chat_api_call", fake_call)

    # Minimal chat invocation with a slash command
    resp = chat_orchestrator.chat(
        message="/time",
        history=[],
        media_content=None,
        selected_parts=[],
        api_endpoint="openai",
        api_key=None,
        custom_prompt=None,
        temperature=0.2,
        system_message=None,
        streaming=False,
        chatdict_entries=None,
    )

    assert resp == "ok"
    # Expect a system message injected with command context
    assert any(m.get("role") == "system" and any(
        (p.get("type") == "text" and "/time" in p.get("text", "")) for p in (m.get("content") or [])
    ) for m in captured_payload)
    # If message was purely a command, there may be no user message
    assert not any(m.get("role") == "user" and any(
        (p.get("type") == "text" and p.get("text", "").strip() == "/time") for p in (m.get("content") or [])
    ) for m in captured_payload)


def test_weather_injection_with_args(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMAND_INJECTION_MODE", "system")

    # Stub weather client to return a deterministic summary
    from tldw_Server_API.app.core.Integrations import weather_providers

    class OkClient:
        def get_current(self, location=None, lat=None, lon=None):
            class R:
                ok = True
                summary = f"Sunny at {location}"
                metadata = {"provider": "test"}
            return R()

    monkeypatch.setattr(weather_providers, "get_weather_client", lambda: OkClient())

    captured_payload: List[Dict[str, Any]] = []

    def fake_call(api_endpoint: str, messages_payload: List[Dict[str, Any]], **kwargs):
        nonlocal captured_payload
        captured_payload = messages_payload
        return "ok"

    monkeypatch.setattr(chat_orchestrator, "chat_api_call", fake_call)

    resp = chat_orchestrator.chat(
        message="/weather Boston bring an umbrella?",
        history=[],
        media_content=None,
        selected_parts=[],
        api_endpoint="openai",
        api_key=None,
        custom_prompt=None,
        temperature=0.1,
        system_message=None,
        streaming=False,
        chatdict_entries=None,
    )

    assert resp == "ok"
    # There should be an injected system message mentioning /weather and Boston
    assert any(m.get("role") == "system" and any(
        (p.get("type") == "text" and "/weather" in p.get("text", "") and "Boston" in p.get("text", "")) for p in (m.get("content") or [])
    ) for m in captured_payload)

