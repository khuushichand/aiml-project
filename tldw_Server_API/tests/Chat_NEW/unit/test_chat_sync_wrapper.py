import asyncio
import importlib
from typing import Any, Dict, List, Optional

import pytest

from tldw_Server_API.app.core.Chat import chat_orchestrator


@pytest.mark.asyncio
async def test_run_coro_sync_inside_running_loop():
    """_run_coro_sync should execute the given coroutine even when a loop is running."""

    called: Dict[str, Any] = {"count": 0}

    async def fake_coro() -> str:
        called["count"] += 1
        return "coro-result"

    # Call the sync helper from a background thread while this test's loop is running.
    result = await asyncio.to_thread(chat_orchestrator._run_coro_sync, fake_coro())

    assert result == "coro-result"
    assert called["count"] == 1


def test_chat_wrapper_invokes_achat_in_sync_context(monkeypatch):


    """chat() should delegate to achat() when called from a plain sync context."""

    called: Dict[str, Any] = {"count": 0, "last_args": None}

    async def fake_achat(message: str, history: List[Dict[str, Any]], *args: Any, **kwargs: Any) -> str:
        called["count"] += 1
        called["last_args"] = {"message": message, "history": history, "kwargs": kwargs}
        return "from-achat"

    monkeypatch.setattr(chat_orchestrator, "achat", fake_achat)

    resp = chat_orchestrator.chat(
        message="hello",
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

    assert resp == "from-achat"
    assert called["count"] == 1
    assert called["last_args"]["message"] == "hello"


def test_chat_wrapper_async_only_flag_blocks_sync(monkeypatch):
    """CHAT_COMMANDS_ASYNC_ONLY should prevent sync chat() usage."""

    monkeypatch.setenv("CHAT_COMMANDS_ASYNC_ONLY", "1")

    with pytest.raises(RuntimeError, match="CHAT_COMMANDS_ASYNC_ONLY"):
        chat_orchestrator.chat(
            message="blocked",
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


@pytest.mark.asyncio
async def test_chat_wrapper_returns_future_in_running_loop(monkeypatch):
    """chat() should return an awaitable when invoked inside a running loop."""

    called: Dict[str, Any] = {"count": 0}

    async def fake_achat(message: str, history: List[Dict[str, Any]], *args: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok-async"

    monkeypatch.setattr(chat_orchestrator, "achat", fake_achat)

    resp = await chat_orchestrator.chat(
        message="inside-loop-direct",
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

    assert resp == "ok-async"
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_chat_wrapper_strict_mode_raises_in_running_loop(monkeypatch):
    """CHAT_SYNC_IN_EVENT_LOOP_STRICT should raise when chat() is invoked inside a running loop."""

    monkeypatch.setenv("CHAT_SYNC_IN_EVENT_LOOP_STRICT", "1")

    with pytest.raises(RuntimeError, match="CHAT_SYNC_IN_EVENT_LOOP_STRICT"):
        chat_orchestrator.chat(
            message="inside-loop",
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


@pytest.mark.asyncio
async def test_chat_wrapper_safe_under_running_loop(monkeypatch):
    """chat() should be callable without raising when an event loop is already running.

    The recommended pattern from async code is to offload via asyncio.to_thread.
    """

    called: Dict[str, Any] = {"count": 0}

    async def fake_achat(message: str, history: List[Dict[str, Any]], *args: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok-async"

    monkeypatch.setattr(chat_orchestrator, "achat", fake_achat)

    resp = await asyncio.to_thread(
        chat_orchestrator.chat,
        "inside-loop",
        [],
        None,
        [],
        "openai",
        None,
        None,
        0.2,
    )

    assert resp == "ok-async"
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_chat_orchestrator_reload_safe_in_running_loop():
    """Reloading chat_orchestrator should not raise when an event loop is running."""

    importlib.reload(chat_orchestrator)
