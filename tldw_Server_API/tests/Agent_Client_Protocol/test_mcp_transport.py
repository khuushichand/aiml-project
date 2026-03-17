"""Tests for MCPTransport ABC, create_transport factory, and stub transports."""
from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import (
    MCPTransport,
    create_transport,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.stdio import (
    MCPStdioTransport,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.sse import (
    MCPSSETransport,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.streamable_http import (
    MCPStreamableHTTPTransport,
)

pytestmark = pytest.mark.unit


def test_mcp_transport_is_abstract():
    """Instantiating MCPTransport directly should raise TypeError."""
    with pytest.raises(TypeError):
        MCPTransport()


def test_create_transport_unknown_raises():
    """create_transport should raise ValueError for unknown protocol."""
    with pytest.raises(ValueError, match="Unknown.*protocol"):
        create_transport({"mcp_transport": "grpc"})


def test_create_transport_stdio():
    """create_transport('stdio') should return MCPStdioTransport."""
    transport = create_transport({
        "mcp_transport": "stdio",
        "command": "python",
        "args": ["-m", "my_server"],
        "env": {"FOO": "bar"},
    })
    assert isinstance(transport, MCPStdioTransport)
    assert transport._command == "python"
    assert transport._args == ["-m", "my_server"]
    assert transport._env == {"FOO": "bar"}
    assert transport.is_connected is False


def test_create_transport_sse():
    """create_transport('sse') should return MCPSSETransport."""
    transport = create_transport({
        "mcp_transport": "sse",
        "sse_url": "http://localhost:8080/sse",
        "post_url": "http://localhost:8080/messages",
        "headers": {"Authorization": "Bearer tok"},
        "timeout_sec": 60,
    })
    assert isinstance(transport, MCPSSETransport)
    assert transport._sse_url == "http://localhost:8080/sse"
    assert transport._post_url == "http://localhost:8080/messages"
    assert transport._headers == {"Authorization": "Bearer tok"}
    assert transport._timeout_sec == 60
    assert transport.is_connected is False


def test_create_transport_streamable_http():
    """create_transport('streamable_http') should return MCPStreamableHTTPTransport."""
    transport = create_transport({
        "mcp_transport": "streamable_http",
        "endpoint": "http://localhost:9090/mcp",
        "headers": {"X-Key": "val"},
        "timeout_sec": 45,
    })
    assert isinstance(transport, MCPStreamableHTTPTransport)
    assert transport._endpoint == "http://localhost:9090/mcp"
    assert transport._headers == {"X-Key": "val"}
    assert transport._timeout_sec == 45
    assert transport.is_connected is False


def test_create_transport_stdio_defaults():
    """Stdio transport defaults: args=None, env=None."""
    transport = create_transport({
        "mcp_transport": "stdio",
        "command": "node",
    })
    assert isinstance(transport, MCPStdioTransport)
    assert transport._args == []
    assert transport._env == {}


def test_create_transport_sse_defaults():
    """SSE transport defaults: post_url=None, headers=None, timeout_sec=30."""
    transport = create_transport({
        "mcp_transport": "sse",
        "sse_url": "http://localhost/sse",
    })
    assert isinstance(transport, MCPSSETransport)
    assert transport._post_url is None
    assert transport._headers is None
    assert transport._timeout_sec == 30
