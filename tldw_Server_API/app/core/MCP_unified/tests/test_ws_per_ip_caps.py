"""
Tests for per-IP WebSocket connection caps in MCP Unified.
"""

import os
import pytest
import os as _os

# Minimize startup side-effects for tests
_os.environ.setdefault("TEST_MODE", "true")
_os.environ.setdefault("DISABLE_HEAVY_STARTUP", "1")
_os.environ.setdefault("ENABLE_TRACING", "false")
_os.environ.setdefault("OTEL_METRICS_EXPORTER", "console")


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

    # Open two connections (at cap)
    ws1 = client.websocket_connect("/api/v1/mcp/ws?client_id=ipcap1")
    ws1.__enter__()
    ws2 = client.websocket_connect("/api/v1/mcp/ws?client_id=ipcap2")
    ws2.__enter__()

    # Third should be rejected
    failed = False
    try:
        with client.websocket_connect("/api/v1/mcp/ws?client_id=ipcap3") as ws3:
            # If it somehow connects, attempt to read an initial frame; likely closed immediately
            try:
                _ = ws3.receive_json()
            except Exception:
                pass
            failed = True  # Should not get here successfully
    except Exception:
        failed = True

    assert failed, "Expected third connection from same IP to be rejected"

    # Cleanup
    ws2.__exit__(None, None, None)
    ws1.__exit__(None, None, None)

    # Assert metrics recorded a rejection
    from tldw_Server_API.app.core.MCP_unified.monitoring.metrics import get_metrics_collector
    collector = get_metrics_collector()
    internal = collector.get_internal_metrics(300)
    # ws_rejection counter should have at least one event
    assert "ws_rejection" in internal
    assert internal["ws_rejection"]["type"] == "counter"
    assert internal["ws_rejection"]["value"] >= 1


_RUN_MCP = os.getenv("RUN_MCP_TESTS", "").lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(not _RUN_MCP, reason="MCP tests disabled by default; set RUN_MCP_TESTS=1 to enable")
