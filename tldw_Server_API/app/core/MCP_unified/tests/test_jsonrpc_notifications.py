"""
JSON-RPC notification behavior tests for MCP Unified.
"""

import os
import pytest
import os as _os

# Minimize startup side-effects for tests (protocol-level only, but keep consistent)
_os.environ.setdefault("TEST_MODE", "true")
_os.environ.setdefault("DISABLE_HEAVY_STARTUP", "1")
_os.environ.setdefault("ENABLE_TRACING", "false")
_os.environ.setdefault("OTEL_METRICS_EXPORTER", "console")
from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext


@pytest.mark.asyncio
async def test_notification_no_response():
    protocol = MCPProtocol()
    # Send a ping notification (no id) and ensure None response
    req = {"jsonrpc": "2.0", "method": "ping"}
    resp = await protocol.process_request(req, RequestContext(request_id="n-1", client_id="notif"))
    assert resp is None


@pytest.mark.asyncio
async def test_batch_of_notifications_returns_none():
    protocol = MCPProtocol()
    # Two notifications (no ids) should yield None overall
    batch = [
        {"jsonrpc": "2.0", "method": "ping"},
        {"jsonrpc": "2.0", "method": "initialize", "params": {"clientInfo": {"name": "N Batch"}}},
    ]
    # initialize without id is also a notification
    resp = await protocol.process_request(batch, RequestContext(request_id="n-2", client_id="notif"))
    assert resp is None


_RUN_MCP = os.getenv("RUN_MCP_TESTS", "").lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(not _RUN_MCP, reason="MCP tests disabled by default; set RUN_MCP_TESTS=1 to enable")
