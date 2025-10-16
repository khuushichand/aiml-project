"""WebSocket smoke test for MCP Unified (basic initialize/ping flow)."""

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.MCP_unified import get_mcp_server
from tldw_Server_API.app.main import app


@pytest.fixture
def ws_client(monkeypatch):
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
async def test_ws_initialize_and_ping(ws_client):
    with ws_client.websocket_connect("/api/v1/mcp/ws?client_id=smoke") as ws:
        # initialize
        ws.send_json(
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {"clientInfo": {"name": "WS Smoke"}},
                "id": 1,
            }
        )
        msg = ws.receive_json()
        # Ignore any non-RPC frames
        while isinstance(msg, dict) and msg.get("type") == "ping":
            msg = ws.receive_json()
        assert msg.get("jsonrpc") == "2.0"
        assert msg.get("id") == 1
        assert msg.get("error") is None
        result = msg.get("result") or {}
        assert result.get("protocolVersion") == "2024-11-05"

        # ping
        ws.send_json(
            {
                "jsonrpc": "2.0",
                "method": "ping",
                "id": 2,
            }
        )
        msg2 = ws.receive_json()
        while isinstance(msg2, dict) and msg2.get("type") == "ping":
            msg2 = ws.receive_json()
        assert msg2.get("jsonrpc") == "2.0"
        assert msg2.get("id") == 2
        assert msg2.get("error") is None
        result2 = msg2.get("result") or {}
        assert result2.get("pong") is True
