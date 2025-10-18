"""
JSON-RPC batch support tests for MCP Unified over WebSocket and protocol-level.
"""

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.MCP_unified import get_mcp_server
from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext
from tldw_Server_API.app.main import app


@pytest.fixture
def ws_client(monkeypatch):
    # Minimize startup side-effects for tests
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("ENABLE_TRACING", "false")
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "console")
    monkeypatch.setenv("MCP_WS_AUTH_REQUIRED", "false")
    monkeypatch.setenv("MCP_ALLOWED_IPS", "")

    client = TestClient(app)
    server = get_mcp_server()
    server.config.ws_auth_required = False
    server.config.allowed_client_ips = []
    server.config.blocked_client_ips = []
    try:
        yield client
    finally:
        client.close()


@pytest.mark.asyncio
async def test_ws_jsonrpc_batch_initialize_and_ping(ws_client):
    with ws_client.websocket_connect("/api/v1/mcp/ws?client_id=batch") as ws:
        # Send a batch request: initialize + ping
        ws.send_json(
            [
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
            ]
        )
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
