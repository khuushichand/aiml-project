"""
JSON-RPC batch support tests for MCP Unified over WebSocket and protocol-level.
"""

import os
import pytest
import os as _os

# Minimize startup side-effects for tests
_os.environ.setdefault("TEST_MODE", "true")
_os.environ.setdefault("DISABLE_HEAVY_STARTUP", "1")
_os.environ.setdefault("ENABLE_TRACING", "false")
_os.environ.setdefault("OTEL_METRICS_EXPORTER", "console")

from fastapi.testclient import TestClient
from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext


client = TestClient(app)


@pytest.mark.asyncio
async def test_ws_jsonrpc_batch_initialize_and_ping():
    with client.websocket_connect("/api/v1/mcp/ws?client_id=batch") as ws:
        # Send a batch request: initialize + ping
        ws.send_json([
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {"clientInfo": {"name": "Batch WS"}},
                "id": 1,
            },
            {
                "jsonrpc": "2.0",
                "method": "ping",
                "id": 2,
            },
        ])
        msg = ws.receive_json()
        # Ignore ping frames
        while isinstance(msg, dict) and msg.get("type") == "ping":
            msg = ws.receive_json()
        assert isinstance(msg, list)
        ids = sorted(item.get("id") for item in msg)
        assert ids == [1, 2]
        # Ensure success responses
        for item in msg:
            assert item.get("jsonrpc") == "2.0"
            assert item.get("error") is None


@pytest.mark.asyncio
async def test_protocol_notification_returns_none():
    protocol = MCPProtocol()
    # Notification: no id field
    req = {"jsonrpc": "2.0", "method": "ping"}
    ctx = RequestContext(request_id="notif-1", client_id="unit-test")
    resp = await protocol.process_request(req, ctx)
    assert resp is None


_RUN_MCP = os.getenv("RUN_MCP_TESTS", "").lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(not _RUN_MCP, reason="MCP tests disabled by default; set RUN_MCP_TESTS=1 to enable")
