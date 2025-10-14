"""
WebSocket smoke test for MCP Unified

Validates basic JSON-RPC initialize and ping over WS.
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


client = TestClient(app)


@pytest.mark.asyncio
async def test_ws_initialize_and_ping():
    with client.websocket_connect("/api/v1/mcp/ws?client_id=smoke") as ws:
        # initialize
        ws.send_json({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {"clientInfo": {"name": "WS Smoke"}},
            "id": 1,
        })
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
        ws.send_json({
            "jsonrpc": "2.0",
            "method": "ping",
            "id": 2,
        })
        msg2 = ws.receive_json()
        while isinstance(msg2, dict) and msg2.get("type") == "ping":
            msg2 = ws.receive_json()
        assert msg2.get("jsonrpc") == "2.0"
        assert msg2.get("id") == 2
        assert msg2.get("error") is None
        result2 = msg2.get("result") or {}
        assert result2.get("pong") is True


_RUN_MCP = os.getenv("RUN_MCP_TESTS", "").lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(not _RUN_MCP, reason="MCP tests disabled by default; set RUN_MCP_TESTS=1 to enable")

