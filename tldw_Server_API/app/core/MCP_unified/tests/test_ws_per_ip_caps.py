"""
Tests for per-IP WebSocket connection caps in MCP Unified.
"""

import os
import pytest
import os as _os

from starlette.websockets import WebSocketDisconnect

from tldw_Server_API.app.core.MCP_unified import get_mcp_server

# Minimize startup side-effects for tests
_os.environ.setdefault("TEST_MODE", "true")
_os.environ.setdefault("ENABLE_TRACING", "false")
_os.environ.setdefault("OTEL_METRICS_EXPORTER", "console")
os.environ.setdefault("MCP_WS_AUTH_REQUIRED", "false")
os.environ.setdefault("MCP_ALLOWED_IPS", "")


@pytest.mark.asyncio
async def test_ws_per_ip_cap_enforced(monkeypatch):
    # Configure per-IP cap before app/server initialization
    os.environ["MCP_WS_MAX_CONNECTIONS_PER_IP"] = "2"
    os.environ["MCP_WS_MAX_CONNECTIONS"] = "50"

    # Clear cached config to pick up env vars
    from tldw_Server_API.app.core.MCP_unified.config import get_config
    try:
        get_config.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    from fastapi.testclient import TestClient
    from tldw_Server_API.app.main import app

    client = TestClient(app)
    server = get_mcp_server()
    server.config.ws_auth_required = False
    server.config.allowed_client_ips = []
    server.config.blocked_client_ips = []
    server.config.ws_max_connections_per_ip = 2
    server.config.ws_max_connections = 50

    # Open two connections (at cap)
    ws1 = client.websocket_connect("/api/v1/mcp/ws?client_id=ipcap1")
    ws1.__enter__()
    ws2 = client.websocket_connect("/api/v1/mcp/ws?client_id=ipcap2")
    ws2.__enter__()

    # Third should be rejected
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/mcp/ws?client_id=ipcap3"):
            pass

    assert exc_info.value.code == 1013
    assert exc_info.value.reason == "Too many connections from IP"

    # Cleanup
    ws2.__exit__(None, None, None)
    ws1.__exit__(None, None, None)

    # Assert metrics recorded a rejection
    from tldw_Server_API.app.core.MCP_unified.monitoring.metrics import get_metrics_collector
    collector = get_metrics_collector()
    internal = collector.get_internal_metrics(300)
    if "ws_rejection" not in internal:
        metrics = list(collector._metrics.get("ws_rejection", []))
        assert metrics, "Expected ws_rejection metric to be recorded"
        assert any(m.labels.get("reason") == "per_ip_cap" for m in metrics)
    else:
        assert internal["ws_rejection"]["type"] == "counter"
        assert internal["ws_rejection"]["value"] >= 1
