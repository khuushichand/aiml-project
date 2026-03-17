"""Tests for AgentDrivenRunner — calls agent entry tool, translates response to events."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind

pytestmark = pytest.mark.unit

SESSION_ID = "test-session-001"


def _make_runner(
    transport_return=None,
    transport_side_effect=None,
    structured_response: bool = False,
    cancel: bool = False,
    entry_tool: str = "execute",
):
    """Helper to build an AgentDrivenRunner with mocked dependencies."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_runners import (
        AgentDrivenRunner,
    )

    transport = AsyncMock()
    if transport_side_effect:
        transport.call_tool.side_effect = transport_side_effect
    else:
        transport.call_tool.return_value = transport_return or {}

    callback = AsyncMock()
    cancel_event = asyncio.Event()
    if cancel:
        cancel_event.set()

    runner = AgentDrivenRunner(
        transport=transport,
        event_callback=callback,
        session_id=SESSION_ID,
        cancel_event=cancel_event,
        entry_tool=entry_tool,
        structured_response=structured_response,
    )
    return runner, transport, callback


def test_agent_driven_simple_text():
    """Transport returns plain text content; verify single COMPLETION event."""
    runner, transport, callback = _make_runner(
        transport_return={"content": [{"type": "text", "text": "Answer"}]}
    )

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "hello"}])
    )

    transport.call_tool.assert_awaited_once_with(
        "execute", {"messages": [{"role": "user", "content": "hello"}]}
    )
    assert callback.await_count == 1
    event: AgentEvent = callback.call_args_list[0][0][0]
    assert event.kind == AgentEventKind.COMPLETION
    assert event.payload["text"] == "Answer"
    assert event.session_id == SESSION_ID


def test_agent_driven_structured_steps():
    """Transport returns structured JSON steps; verify multiple events in order."""
    steps = {
        "steps": [
            {"type": "thinking", "text": "Let me think..."},
            {"type": "tool_call", "tool_name": "search", "arguments": {"q": "test"}},
            {"type": "tool_result", "tool_name": "search", "output": "found it"},
            {"type": "completion", "text": "Here is the answer"},
        ]
    }
    runner, transport, callback = _make_runner(
        transport_return={"content": [{"type": "text", "text": json.dumps(steps)}]},
        structured_response=True,
    )

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "search for test"}])
    )

    assert callback.await_count == 4
    events = [call[0][0] for call in callback.call_args_list]

    assert events[0].kind == AgentEventKind.THINKING
    assert events[0].payload["text"] == "Let me think..."

    assert events[1].kind == AgentEventKind.TOOL_CALL
    assert events[1].payload["tool_name"] == "search"
    assert events[1].payload["arguments"] == {"q": "test"}

    assert events[2].kind == AgentEventKind.TOOL_RESULT
    assert events[2].payload["tool_name"] == "search"
    assert events[2].payload["output"] == "found it"

    assert events[3].kind == AgentEventKind.COMPLETION
    assert events[3].payload["text"] == "Here is the answer"


def test_agent_driven_structured_no_completion_step():
    """If structured response has no completion step, emit one with raw text."""
    steps = {
        "steps": [
            {"type": "thinking", "text": "hmm"},
        ]
    }
    raw_text = json.dumps(steps)
    runner, transport, callback = _make_runner(
        transport_return={"content": [{"type": "text", "text": raw_text}]},
        structured_response=True,
    )

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "go"}])
    )

    events = [call[0][0] for call in callback.call_args_list]
    assert events[0].kind == AgentEventKind.THINKING
    # Fallback completion
    assert events[-1].kind == AgentEventKind.COMPLETION
    assert events[-1].payload["text"] == raw_text


def test_agent_driven_tool_error():
    """Transport.call_tool raises; verify ERROR event is emitted."""
    runner, transport, callback = _make_runner(
        transport_side_effect=RuntimeError("connection lost")
    )

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "hi"}])
    )

    assert callback.await_count == 1
    event: AgentEvent = callback.call_args_list[0][0][0]
    assert event.kind == AgentEventKind.ERROR
    assert "connection lost" in event.payload["error"]


def test_agent_driven_cancel():
    """Cancel event is set; verify no call_tool and no events."""
    runner, transport, callback = _make_runner(cancel=True)

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "hi"}])
    )

    transport.call_tool.assert_not_awaited()
    callback.assert_not_awaited()


def test_agent_driven_custom_entry_tool():
    """Verify custom entry_tool name is used in call_tool."""
    runner, transport, callback = _make_runner(
        transport_return={"content": [{"type": "text", "text": "ok"}]},
        entry_tool="run_agent",
    )

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "go"}])
    )

    transport.call_tool.assert_awaited_once_with(
        "run_agent", {"messages": [{"role": "user", "content": "go"}]}
    )
