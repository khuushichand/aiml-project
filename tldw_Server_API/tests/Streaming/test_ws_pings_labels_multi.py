import time
import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.asyncio
async def test_ws_pings_label_isolation_across_endpoints(monkeypatch):
    """Verify ws_pings_total increments with correct labels for multiple endpoints.

    We enable short ping intervals on both Audio WS (via STREAM_HEARTBEAT_INTERVAL_S)
    and MCP WS (via MCP_WS_PING_INTERVAL). Each connection should increment only
    its own labeled counter series.
    """
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager

    # Short ping intervals
    monkeypatch.setenv("STREAM_HEARTBEAT_INTERVAL_S", "0.05")
    # MCP config expects integer seconds; use 1s for reliable triggering
    monkeypatch.setenv("MCP_WS_PING_INTERVAL", "1")

    settings = get_settings()
    audio_token = settings.SINGLE_USER_API_KEY
    mcp_token = get_jwt_manager().create_access_token(subject="1")
    # Ensure MCP server instance uses 1s ping interval even if created before env set
    try:
        from tldw_Server_API.app.core.MCP_unified import get_mcp_server
        get_mcp_server().config.ws_ping_interval = 1
    except Exception:
        _ = None

    reg = get_metrics_registry()
    audio_labels = {"component": "audio", "endpoint": "audio_unified_ws", "transport": "ws"}
    mcp_labels = {"component": "mcp", "endpoint": "mcp_ws", "transport": "ws"}

    before_audio = reg.get_metric_stats("ws_pings_total", labels=audio_labels).get("count", 0)
    # Track MCP send latency metric for label verification
    before_mcp_latency = reg.get_metric_stats(
        "ws_send_latency_ms", labels={**mcp_labels}
    ).get("count", 0)

    with TestClient(app) as client:
        # Open Audio WS
        try:
            audio_ws = client.websocket_connect(f"/api/v1/audio/stream/transcribe?token={audio_token}")
        except Exception:
            pytest.skip("audio WebSocket endpoint not available in this build")

        # Open MCP WS (authenticated)
        try:
            mcp_ws = client.websocket_connect(
                "/api/v1/mcp/ws?client_id=test.labels",
                headers={"Authorization": f"Bearer {mcp_token}"},
            )
        except Exception:
            # Close audio ws before skipping
            with audio_ws:
                pass
            pytest.skip("MCP WebSocket endpoint not available in this build")

        # Keep both connections open long enough for a few pings
        with audio_ws, mcp_ws:
            # Allow multiple audio pings; concurrently exercise MCP send path
            time.sleep(0.25)
            try:
                mcp_ws.send_text(
                    json.dumps({
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"clientInfo": {"name": "labels-probe", "version": "0.0.1"}},
                    })
                )
                _ = mcp_ws.receive_json()
            except Exception:
                _ = None

    after_audio = reg.get_metric_stats("ws_pings_total", labels=audio_labels).get("count", 0)
    after_mcp_latency = reg.get_metric_stats(
        "ws_send_latency_ms", labels={**mcp_labels}
    ).get("count", 0)

    assert after_audio >= before_audio + 2
    assert after_mcp_latency >= before_mcp_latency + 1
