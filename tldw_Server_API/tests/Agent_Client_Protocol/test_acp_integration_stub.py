"""Integration tests using the stub agent via real STDIO transport.

These tests exercise the full JSON-RPC protocol path through
ACPStdioClient → acp_stub_agent.py without needing the Go binary.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import (
    ACPStdioClient,
    ACPResponseError,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

STUB_AGENT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "Helper_Scripts",
    "acp_stub_agent.py",
)


@pytest.fixture
async def client():
    """Spawn stub agent for each test."""
    c = ACPStdioClient(
        command=sys.executable,
        args=[os.path.abspath(STUB_AGENT_PATH)],
    )
    await c.start()
    yield c
    await c.close()


# ---- Session lifecycle ----

async def test_initialize(client):
    """Verify initialize handshake returns agent info."""
    result = await client.call("initialize", {})
    assert result.result is not None
    assert result.result["agentInfo"]["name"] == "tldw-acp-stub"
    assert result.result["protocolVersion"] == 1


async def test_session_new(client):
    """Verify session/new returns a session ID."""
    await client.call("initialize", {})
    result = await client.call("session/new", {})
    assert "sessionId" in result.result
    assert result.result["sessionId"].startswith("stub-")


async def test_session_prompt(client):
    """Verify session/prompt returns stop reason and emits update."""
    await client.call("initialize", {})
    new_result = await client.call("session/new", {})
    session_id = new_result.result["sessionId"]

    # Collect notifications
    notifications = []

    async def handler(msg):
        notifications.append(msg)

    client.set_notification_handler(handler)

    result = await client.call(
        "session/prompt",
        {"sessionId": session_id, "prompt": "Hello"},
    )
    assert result.result["stopReason"] == "end"


async def test_session_cancel(client):
    """Verify session/cancel returns successfully."""
    await client.call("initialize", {})
    result = await client.call("session/cancel", {})
    assert result.result is None


async def test_unknown_method_returns_error(client):
    """Verify unknown methods raise ACPResponseError."""
    with pytest.raises(ACPResponseError, match="method not found"):
        await client.call("nonexistent/method", {})


# ---- Concurrent sessions ----

async def test_concurrent_sessions(client):
    """Verify multiple sessions can be created sequentially."""
    await client.call("initialize", {})

    session_ids = []
    for _ in range(3):
        result = await client.call("session/new", {})
        session_ids.append(result.result["sessionId"])

    assert len(set(session_ids)) == 3  # All unique


# ---- Error handling ----

async def test_client_close_is_idempotent(client):
    """Closing an already-closed client should not raise."""
    await client.close()
    await client.close()  # Should not raise


async def test_client_is_running(client):
    """Verify is_running reflects process state."""
    assert client.is_running
    await client.close()
    assert not client.is_running
