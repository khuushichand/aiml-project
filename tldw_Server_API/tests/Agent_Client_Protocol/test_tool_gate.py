"""Tests for ToolGate ABC and ToolGateResult."""
from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.tool_gate import (
    ToolGate,
    ToolGateResult,
)

pytestmark = pytest.mark.unit


def test_tool_gate_result_defaults():
    """ToolGateResult(approved=True) should have reason=None by default."""
    result = ToolGateResult(approved=True)
    assert result.approved is True
    assert result.reason is None


def test_tool_gate_result_with_reason():
    """ToolGateResult should store a custom reason string."""
    result = ToolGateResult(approved=False, reason="policy violation")
    assert result.approved is False
    assert result.reason == "policy violation"


def test_tool_gate_is_abstract():
    """Instantiating ToolGate directly should raise TypeError."""
    with pytest.raises(TypeError):
        ToolGate()


@pytest.mark.asyncio
async def test_tool_gate_concrete_implementation():
    """A concrete subclass of ToolGate should work as expected."""

    class AlwaysApprove(ToolGate):
        async def request_approval(self, session_id, tool_name, arguments):
            return ToolGateResult(approved=True, reason="auto-approved")

    gate = AlwaysApprove()
    result = await gate.request_approval("sess-1", "read_file", {"path": "/tmp"})
    assert result.approved is True
    assert result.reason == "auto-approved"
