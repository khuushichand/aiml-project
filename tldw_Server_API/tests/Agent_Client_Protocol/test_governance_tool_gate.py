"""Tests for GovernanceToolGate -- bridges ToolGate ABC to GovernanceFilter."""
from __future__ import annotations

import asyncio

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind
from tldw_Server_API.app.core.Agent_Client_Protocol.governance_filter import (
    GovernanceFilter,
    GovernanceToolGate,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def bus():
    return SessionEventBus(session_id="s1")


@pytest.fixture
def gov(bus):
    return GovernanceFilter(bus=bus)


@pytest.fixture
def gate(gov):
    return GovernanceToolGate(governance_filter=gov, session_id="s1")


@pytest.mark.asyncio
async def test_governance_tool_gate_auto_approved(gate):
    """Auto-tier tool (read_file) should be approved immediately."""
    result = await gate.request_approval(
        session_id="s1",
        tool_name="read_file",
        arguments={"path": "/tmp/foo.txt"},
    )
    assert result.approved is True
    assert result.reason is None


@pytest.mark.asyncio
async def test_governance_tool_gate_held_then_approved(bus, gov, gate):
    """Individual-tier tool (bash) held, then approved via on_permission_response."""
    q = bus.subscribe("test")

    async def _approve_after_hold():
        # Wait for the PERMISSION_REQUEST to appear on the bus
        perm_req = await asyncio.wait_for(q.get(), timeout=2.0)
        assert perm_req.kind == AgentEventKind.PERMISSION_REQUEST
        request_id = perm_req.payload["request_id"]
        await gov.on_permission_response(request_id, decision="approve")

    approve_task = asyncio.create_task(_approve_after_hold())

    result = await asyncio.wait_for(
        gate.request_approval(session_id="s1", tool_name="bash", arguments={"cmd": "ls"}),
        timeout=3.0,
    )
    await approve_task

    assert result.approved is True
    assert result.reason is None


@pytest.mark.asyncio
async def test_governance_tool_gate_held_then_denied(bus, gov, gate):
    """Individual-tier tool (bash) held, then denied via on_permission_response."""
    q = bus.subscribe("test")

    async def _deny_after_hold():
        perm_req = await asyncio.wait_for(q.get(), timeout=2.0)
        assert perm_req.kind == AgentEventKind.PERMISSION_REQUEST
        request_id = perm_req.payload["request_id"]
        await gov.on_permission_response(request_id, decision="deny", reason="too dangerous")

    deny_task = asyncio.create_task(_deny_after_hold())

    result = await asyncio.wait_for(
        gate.request_approval(session_id="s1", tool_name="bash", arguments={"cmd": "rm -rf /"}),
        timeout=3.0,
    )
    await deny_task

    assert result.approved is False
    assert result.reason == "too dangerous"
