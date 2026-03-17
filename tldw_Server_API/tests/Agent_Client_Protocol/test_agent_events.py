"""Unit tests for AgentEvent schema."""
from __future__ import annotations

import pytest
import json
from datetime import datetime, timezone

pytestmark = pytest.mark.unit


def test_agent_event_kind_enum_has_all_kinds():
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind

    expected = {
        "thinking", "tool_call", "tool_result", "file_change",
        "terminal_output", "permission_request", "permission_response",
        "completion", "error", "status_change", "token_usage",
        "heartbeat", "lifecycle",
    }
    assert {k.value for k in AgentEventKind} == expected


def test_agent_event_creation_minimal():
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind

    ev = AgentEvent(
        session_id="sess-1",
        kind=AgentEventKind.COMPLETION,
        payload={"text": "Hello", "stop_reason": "end_turn"},
    )
    assert ev.session_id == "sess-1"
    assert ev.kind == AgentEventKind.COMPLETION
    assert ev.sequence == 0
    assert ev.payload["text"] == "Hello"
    assert isinstance(ev.timestamp, datetime)
    assert ev.metadata == {}


def test_agent_event_to_dict_roundtrip():
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind

    ev = AgentEvent(
        session_id="sess-2",
        kind=AgentEventKind.TOOL_CALL,
        payload={"tool_id": "t1", "tool_name": "bash", "arguments": {"cmd": "ls"}, "permission_tier": "individual"},
        metadata={"adapter": "stdio"},
    )
    d = ev.to_dict()
    assert d["kind"] == "tool_call"
    assert d["session_id"] == "sess-2"
    assert d["payload"]["tool_name"] == "bash"
    json.dumps(d)


def test_agent_event_all_payload_shapes():
    """Verify every event kind can be instantiated with its documented payload."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind

    payloads = {
        AgentEventKind.THINKING: {"text": "hmm", "is_partial": False},
        AgentEventKind.TOOL_CALL: {"tool_id": "t1", "tool_name": "read", "arguments": {}, "permission_tier": "auto"},
        AgentEventKind.TOOL_RESULT: {"tool_id": "t1", "tool_name": "read", "output": "data", "is_error": False, "duration_ms": 42},
        AgentEventKind.FILE_CHANGE: {"path": "/a.txt", "action": "create", "diff": None, "content": "hi"},
        AgentEventKind.TERMINAL_OUTPUT: {"command": "ls", "output": "file.txt", "exit_code": 0, "is_partial": False},
        AgentEventKind.PERMISSION_REQUEST: {"request_id": "r1", "tool_name": "bash", "arguments": {}, "tier": "individual", "timeout_sec": 300},
        AgentEventKind.PERMISSION_RESPONSE: {"request_id": "r1", "decision": "approve", "reason": None},
        AgentEventKind.COMPLETION: {"text": "done", "stop_reason": "end_turn"},
        AgentEventKind.ERROR: {"code": "adapter_disconnect", "message": "lost", "recoverable": True},
        AgentEventKind.STATUS_CHANGE: {"from_status": "idle", "to_status": "working"},
        AgentEventKind.TOKEN_USAGE: {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        AgentEventKind.HEARTBEAT: {"elapsed_sec": 15, "state": "thinking"},
        AgentEventKind.LIFECYCLE: {"event": "agent_started", "exit_code": None},
    }
    for kind, payload in payloads.items():
        ev = AgentEvent(session_id="s", kind=kind, payload=payload)
        d = ev.to_dict()
        json.dumps(d)
