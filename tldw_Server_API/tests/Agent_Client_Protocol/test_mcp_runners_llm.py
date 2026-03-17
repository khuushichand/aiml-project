"""Tests for LLMDrivenRunner — ReAct loop: LLM decides tools, ToolGate approves, transport executes."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import (
    LLMResponse,
    LLMToolCall,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind
from tldw_Server_API.app.core.Agent_Client_Protocol.tool_gate import ToolGateResult

pytestmark = pytest.mark.unit

SESSION_ID = "test-session-llm"

MCP_TOOLS = [
    {
        "name": "search",
        "description": "Web search",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
    }
]


def _make_runner(
    llm_responses: list[LLMResponse] | None = None,
    gate_results: list[ToolGateResult] | None = None,
    transport_returns: list[dict] | None = None,
    cancel_after: int | None = None,
    max_iterations: int = 20,
):
    """Helper to build an LLMDrivenRunner with mocked dependencies."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_runners import (
        LLMDrivenRunner,
    )

    transport = AsyncMock()
    if transport_returns:
        transport.call_tool.side_effect = transport_returns
    else:
        transport.call_tool.return_value = {"content": [{"type": "text", "text": "result"}]}

    llm_caller = AsyncMock()
    if llm_responses:
        llm_caller.call.side_effect = llm_responses
    else:
        llm_caller.call.return_value = LLMResponse(text="Done")

    tool_gate = AsyncMock()
    if gate_results:
        tool_gate.request_approval.side_effect = gate_results
    else:
        tool_gate.request_approval.return_value = ToolGateResult(approved=True)

    callback = AsyncMock()
    cancel_event = asyncio.Event()

    # If cancel_after is set, wrap callback to set cancel after N calls
    if cancel_after is not None:
        original_callback = callback

        call_count = 0

        async def cancelling_callback(event):
            nonlocal call_count
            call_count += 1
            await original_callback(event)
            if call_count >= cancel_after:
                cancel_event.set()

        callback_fn = cancelling_callback
    else:
        callback_fn = callback

    runner = LLMDrivenRunner(
        transport=transport,
        event_callback=callback_fn,
        session_id=SESSION_ID,
        cancel_event=cancel_event,
        llm_caller=llm_caller,
        tool_gate=tool_gate,
        tools=MCP_TOOLS,
        max_iterations=max_iterations,
    )
    return runner, transport, llm_caller, tool_gate, callback, cancel_event


def test_llm_driven_single_turn():
    """LLM returns text immediately; verify single COMPLETION event."""
    runner, transport, llm_caller, tool_gate, callback, _ = _make_runner(
        llm_responses=[LLMResponse(text="The answer is 42")]
    )

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "what is the answer?"}])
    )

    assert callback.await_count == 1
    event: AgentEvent = callback.call_args_list[0][0][0]
    assert event.kind == AgentEventKind.COMPLETION
    assert event.payload["text"] == "The answer is 42"
    assert event.payload["stop_reason"] == "end_turn"
    transport.call_tool.assert_not_awaited()


def test_llm_driven_multi_turn():
    """LLM returns tool_call first, then text. Verify TOOL_CALL -> TOOL_RESULT -> COMPLETION."""
    tc = LLMToolCall(id="tc1", name="search", arguments={"query": "hello"})
    runner, transport, llm_caller, tool_gate, callback, _ = _make_runner(
        llm_responses=[
            LLMResponse(tool_calls=[tc]),
            LLMResponse(text="Found the answer"),
        ],
        transport_returns=[
            {"content": [{"type": "text", "text": "search result"}]},
        ],
    )

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "search hello"}])
    )

    events = [call[0][0] for call in callback.call_args_list]
    assert len(events) == 3

    assert events[0].kind == AgentEventKind.TOOL_CALL
    assert events[0].payload["tool_name"] == "search"
    assert events[0].payload["arguments"] == {"query": "hello"}

    assert events[1].kind == AgentEventKind.TOOL_RESULT
    assert events[1].payload["tool_name"] == "search"
    assert events[1].payload["output"] == "search result"
    assert events[1].payload["is_error"] is False

    assert events[2].kind == AgentEventKind.COMPLETION
    assert events[2].payload["text"] == "Found the answer"


def test_llm_driven_max_iterations():
    """LLM always returns tool_calls; verify max_iterations COMPLETION."""
    tc = LLMToolCall(id="tc1", name="search", arguments={"query": "loop"})
    # Return tool_calls every time (more than max_iterations)
    responses = [LLMResponse(tool_calls=[tc]) for _ in range(5)]
    runner, transport, llm_caller, tool_gate, callback, _ = _make_runner(
        llm_responses=responses,
        max_iterations=3,
    )

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "loop"}])
    )

    events = [call[0][0] for call in callback.call_args_list]
    # Last event should be COMPLETION with max_iterations
    last = events[-1]
    assert last.kind == AgentEventKind.COMPLETION
    assert last.payload["stop_reason"] == "max_iterations"


def test_llm_driven_cancel():
    """Cancel event set after first iteration; verify loop stops."""
    tc = LLMToolCall(id="tc1", name="search", arguments={"query": "test"})
    responses = [
        LLMResponse(tool_calls=[tc]),
        LLMResponse(tool_calls=[tc]),
        LLMResponse(text="done"),
    ]
    # Cancel after 2 events (TOOL_CALL + TOOL_RESULT from first iteration)
    runner, transport, llm_caller, tool_gate, callback, cancel_event = _make_runner(
        llm_responses=responses,
        max_iterations=10,
        cancel_after=2,
    )

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "test"}])
    )

    # LLM should have been called once (first iteration), then cancel kicks in
    assert llm_caller.call.await_count == 1


def test_llm_driven_governance_denial():
    """ToolGate returns denied; verify TOOL_RESULT with is_error."""
    tc = LLMToolCall(id="tc1", name="search", arguments={"query": "forbidden"})
    runner, transport, llm_caller, tool_gate, callback, _ = _make_runner(
        llm_responses=[
            LLMResponse(tool_calls=[tc]),
            LLMResponse(text="Okay, denied"),
        ],
        gate_results=[ToolGateResult(approved=False, reason="Not allowed")],
    )

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "do forbidden thing"}])
    )

    events = [call[0][0] for call in callback.call_args_list]
    # Should have: denied TOOL_RESULT, then COMPLETION
    denied = events[0]
    assert denied.kind == AgentEventKind.TOOL_RESULT
    assert denied.payload["is_error"] is True
    assert "Not allowed" in denied.payload["output"]

    # Transport should NOT have been called (denied)
    transport.call_tool.assert_not_awaited()

    completion = events[-1]
    assert completion.kind == AgentEventKind.COMPLETION


def test_llm_driven_transport_error():
    """Transport raises during tool execution; verify ERROR event."""
    tc = LLMToolCall(id="tc1", name="search", arguments={"query": "boom"})
    runner, transport, llm_caller, tool_gate, callback, _ = _make_runner(
        llm_responses=[
            LLMResponse(tool_calls=[tc]),
            LLMResponse(text="recovered"),
        ],
        transport_returns=[RuntimeError("transport failed")],
    )
    # Override: side_effect with exception
    transport.call_tool.side_effect = RuntimeError("transport failed")

    asyncio.get_event_loop().run_until_complete(
        runner.run([{"role": "user", "content": "boom"}])
    )

    events = [call[0][0] for call in callback.call_args_list]
    # TOOL_CALL, then TOOL_RESULT with error
    tool_call_ev = events[0]
    assert tool_call_ev.kind == AgentEventKind.TOOL_CALL

    tool_result_ev = events[1]
    assert tool_result_ev.kind == AgentEventKind.TOOL_RESULT
    assert tool_result_ev.payload["is_error"] is True
    assert "transport failed" in tool_result_ev.payload["output"]
