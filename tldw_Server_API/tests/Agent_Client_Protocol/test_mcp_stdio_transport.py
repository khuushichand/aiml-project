"""Tests for MCPStdioTransport — stdio-based MCP transport."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage
from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.stdio import (
    MCPStdioTransport,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.is_running = True
    return client


@pytest.fixture
def transport():
    return MCPStdioTransport(command="node", args=["server.js"], env={"FOO": "bar"})


# ---- Tests ----


def test_stdio_transport_not_connected_initially(transport):
    """A freshly created transport should not be connected."""
    assert transport.is_connected is False


@pytest.mark.asyncio
async def test_stdio_transport_connect_performs_handshake(transport, mock_client):
    """connect() should start the client, send initialize call, then initialized notification."""
    mock_client.call.return_value = ACPMessage(
        jsonrpc="2.0",
        result={
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "test"},
            "capabilities": {},
        },
    )

    with patch.object(transport, "_create_client", return_value=mock_client):
        await transport.connect()

    mock_client.start.assert_awaited_once()
    mock_client.call.assert_awaited_once()
    call_args = mock_client.call.call_args
    assert call_args[0][0] == "initialize"
    init_params = call_args[0][1]
    assert init_params["protocolVersion"] == "2024-11-05"
    assert init_params["clientInfo"]["name"] == "tldw_acp_harness"

    mock_client.notify.assert_awaited_once_with("initialized", {})
    assert transport.is_connected is True


@pytest.mark.asyncio
async def test_stdio_transport_list_tools(transport, mock_client):
    """list_tools() should parse the tools from the call response."""
    tools = [
        {"name": "echo", "description": "echoes input"},
        {"name": "add", "description": "adds numbers"},
    ]
    mock_client.call.return_value = ACPMessage(
        jsonrpc="2.0",
        result={"tools": tools},
    )
    transport._client = mock_client
    transport._connected = True

    result = await transport.list_tools()

    assert result == tools
    mock_client.call.assert_awaited_once_with("tools/list", {})


@pytest.mark.asyncio
async def test_stdio_transport_call_tool(transport, mock_client):
    """call_tool() should forward name and arguments correctly."""
    mock_client.call.return_value = ACPMessage(
        jsonrpc="2.0",
        result={"content": [{"type": "text", "text": "hello"}]},
    )
    transport._client = mock_client
    transport._connected = True

    result = await transport.call_tool("echo", {"message": "hello"})

    assert result == {"content": [{"type": "text", "text": "hello"}]}
    mock_client.call.assert_awaited_once_with(
        "tools/call", {"name": "echo", "arguments": {"message": "hello"}}
    )


@pytest.mark.asyncio
async def test_stdio_transport_close(transport, mock_client):
    """close() should call client.close() and mark transport as disconnected."""
    transport._client = mock_client
    transport._connected = True

    await transport.close()

    mock_client.close.assert_awaited_once()
    assert transport.is_connected is False


@pytest.mark.asyncio
async def test_stdio_transport_health_check(transport, mock_client):
    """health_check() returns True when client is running, False otherwise."""
    transport._client = mock_client
    transport._connected = True

    assert await transport.health_check() is True

    mock_client.is_running = False
    assert await transport.health_check() is False


@pytest.mark.asyncio
async def test_stdio_transport_list_tools_not_connected(transport):
    """list_tools() raises RuntimeError when not connected."""
    with pytest.raises(RuntimeError, match="Not connected"):
        await transport.list_tools()


@pytest.mark.asyncio
async def test_stdio_transport_call_tool_not_connected(transport):
    """call_tool() raises RuntimeError when not connected."""
    with pytest.raises(RuntimeError, match="Not connected"):
        await transport.call_tool("echo", {})
