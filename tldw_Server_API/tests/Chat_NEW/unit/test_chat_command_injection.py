import os
from typing import Any, Dict, List, Optional

import pytest

from tldw_Server_API.app.core.Chat import chat_orchestrator, command_router
from tldw_Server_API.app.core.Chat import command_router as command_router_module


def test_system_injection_for_time(monkeypatch):


     # Enable commands and system injection
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMAND_INJECTION_MODE", "system")

    captured_payload: List[Dict[str, Any]] = []

    def fake_call(api_endpoint: str, messages_payload: List[Dict[str, Any]], **kwargs):
        nonlocal captured_payload
        captured_payload = messages_payload
        return "ok"

    async def fake_call_async(api_endpoint: str, messages_payload: List[Dict[str, Any]], **kwargs):
        nonlocal captured_payload
        captured_payload = messages_payload
        return "ok"

    # Patch both sync and async dispatcher variants so the orchestrator wrapper
    # (which now routes through achat) uses the stubbed implementation.
    monkeypatch.setattr(chat_orchestrator, "chat_api_call", fake_call)
    monkeypatch.setattr(chat_orchestrator, "chat_api_call_async", fake_call_async)

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


def test_streaming_path_uses_async_dispatcher(monkeypatch):


    """Streaming chat with a slash command should call async_dispatch_command, not dispatch_command."""

    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMAND_INJECTION_MODE", "system")

    called: Dict[str, Any] = {"async_calls": 0, "sync_calls": 0}

    async def fake_async_dispatch(ctx, name, args):
        called["async_calls"] += 1

        class R:
            ok = True
            content = "ok"
            metadata = {}

        return R()

    def fake_sync_dispatch(ctx, name, args):

        called["sync_calls"] += 1

        class R:
            ok = True
            content = "ok-sync"
            metadata = {}

        return R()

    # Patch dispatcher functions on the command_router module used by the orchestrator.
    monkeypatch.setattr(command_router_module, "async_dispatch_command", fake_async_dispatch)
    monkeypatch.setattr(command_router_module, "dispatch_command", fake_sync_dispatch)

    # Also stub out the provider call so we don't depend on external services.
    def fake_call(api_endpoint: str, messages_payload: List[Dict[str, Any]], **kwargs):
        return "stream-ok"

    monkeypatch.setattr(chat_orchestrator, "chat_api_call", fake_call)

    gen = chat_orchestrator.chat(
        message="/time",
        history=[],
        media_content=None,
        selected_parts=[],
        api_endpoint="openai",
        api_key=None,
        custom_prompt=None,
        temperature=0.2,
        system_message=None,
        streaming=True,
        chatdict_entries=None,
    )

    # Exhaust the generator to ensure the path is fully executed.
    list(gen)

    assert called["async_calls"] == 1
    assert called["sync_calls"] == 0


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

    async def fake_call_async(api_endpoint: str, messages_payload: List[Dict[str, Any]], **kwargs):
        nonlocal captured_payload
        captured_payload = messages_payload
        return "ok"

    monkeypatch.setattr(chat_orchestrator, "chat_api_call", fake_call)
    monkeypatch.setattr(chat_orchestrator, "chat_api_call_async", fake_call_async)

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
