"""Unit tests for GovernanceFilter pipeline stage."""
from __future__ import annotations

import asyncio

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind

pytestmark = pytest.mark.unit


def _make_event(
    kind: AgentEventKind = AgentEventKind.THINKING,
    payload: dict | None = None,
    session_id: str = "s1",
) -> AgentEvent:
    return AgentEvent(
        session_id=session_id,
        kind=kind,
        payload=payload or {"text": "hi"},
    )


@pytest.fixture
def bus():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    return SessionEventBus(session_id="s1")


@pytest.fixture
def gov(bus):
    from tldw_Server_API.app.core.Agent_Client_Protocol.governance_filter import GovernanceFilter
    return GovernanceFilter(bus=bus)


@pytest.mark.asyncio
async def test_governance_passes_non_tool_events_immediately(bus, gov):
    q = bus.subscribe("test")
    ev = _make_event(kind=AgentEventKind.THINKING, payload={"text": "hmm"})
    await gov.process(ev)

    got = await asyncio.wait_for(q.get(), timeout=1.0)
    assert got is ev
    assert got.kind == AgentEventKind.THINKING


@pytest.mark.asyncio
async def test_governance_auto_tier_passes_through(bus, gov):
    """Tool with auto tier (e.g. read_file) goes straight to bus."""
    q = bus.subscribe("test")
    ev = _make_event(
        kind=AgentEventKind.TOOL_CALL,
        payload={"tool_id": "t1", "tool_name": "read_file", "arguments": {}},
    )
    await gov.process(ev)

    got = await asyncio.wait_for(q.get(), timeout=1.0)
    assert got is ev
    assert got.kind == AgentEventKind.TOOL_CALL


@pytest.mark.asyncio
async def test_governance_individual_tier_holds_and_emits_permission_request(bus, gov):
    """Tool with individual tier (e.g. bash) is held; a PERMISSION_REQUEST is emitted."""
    q = bus.subscribe("test")
    ev = _make_event(
        kind=AgentEventKind.TOOL_CALL,
        payload={"tool_id": "t1", "tool_name": "bash", "arguments": {"cmd": "rm -rf /"}},
    )
    await gov.process(ev)

    # The bus should have received a PERMISSION_REQUEST, not the original tool_call
    perm_req = await asyncio.wait_for(q.get(), timeout=1.0)
    assert perm_req.kind == AgentEventKind.PERMISSION_REQUEST
    assert "request_id" in perm_req.payload
    assert perm_req.payload["tool_name"] == "bash"
    assert perm_req.payload["tier"] == "individual"

    # Original event should NOT be on bus yet
    assert q.empty()
    assert gov.pending_count == 1


@pytest.mark.asyncio
async def test_governance_approve_releases_held_tool_call(bus, gov):
    """Approving a held tool_call publishes it to the bus."""
    q = bus.subscribe("test")
    ev = _make_event(
        kind=AgentEventKind.TOOL_CALL,
        payload={"tool_id": "t1", "tool_name": "bash", "arguments": {"cmd": "ls"}},
    )
    await gov.process(ev)

    perm_req = await asyncio.wait_for(q.get(), timeout=1.0)
    request_id = perm_req.payload["request_id"]

    await gov.on_permission_response(request_id, decision="approve")

    released = await asyncio.wait_for(q.get(), timeout=1.0)
    assert released is ev
    assert released.kind == AgentEventKind.TOOL_CALL
    assert gov.pending_count == 0


@pytest.mark.asyncio
async def test_governance_deny_emits_error_tool_result(bus, gov):
    """Denying a held tool_call publishes a TOOL_RESULT with is_error=True."""
    q = bus.subscribe("test")
    ev = _make_event(
        kind=AgentEventKind.TOOL_CALL,
        payload={"tool_id": "t1", "tool_name": "bash", "arguments": {"cmd": "rm -rf /"}},
    )
    await gov.process(ev)

    perm_req = await asyncio.wait_for(q.get(), timeout=1.0)
    request_id = perm_req.payload["request_id"]

    await gov.on_permission_response(request_id, decision="deny", reason="too dangerous")

    error_result = await asyncio.wait_for(q.get(), timeout=1.0)
    assert error_result.kind == AgentEventKind.TOOL_RESULT
    assert error_result.payload["is_error"] is True
    assert "too dangerous" in error_result.payload["output"]
    assert error_result.payload["tool_name"] == "bash"
    assert gov.pending_count == 0


@pytest.mark.asyncio
async def test_governance_timeout_auto_denies(bus):
    """Unanswered permission requests are auto-denied after timeout_sec."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.governance_filter import GovernanceFilter

    gov = GovernanceFilter(bus=bus, default_timeout_sec=0.1)  # 100ms timeout
    q = bus.subscribe("test")

    ev = _make_event(
        kind=AgentEventKind.TOOL_CALL,
        payload={"tool_id": "t1", "tool_name": "bash", "arguments": {}},
    )
    await gov.process(ev)

    # Consume the permission_request
    perm_req = await asyncio.wait_for(q.get(), timeout=1.0)
    assert perm_req.kind == AgentEventKind.PERMISSION_REQUEST

    # Wait for the timeout to fire (100ms + margin)
    error_result = await asyncio.wait_for(q.get(), timeout=2.0)
    assert error_result.kind == AgentEventKind.TOOL_RESULT
    assert error_result.payload["is_error"] is True
    assert "timeout" in error_result.payload["output"].lower()
    assert gov.pending_count == 0
