import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.asyncio
async def test_mcp_ws_emits_ws_latency_metrics_on_initialize(monkeypatch):
    from tldw_Server_API.app.main import app

    # Create an MCP JWT directly to avoid endpoint policy constraints
    from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
    token = get_jwt_manager().create_access_token(subject="1")

    with TestClient(app) as client:

        reg = get_metrics_registry()
        before = reg.get_metric_stats(
            "ws_send_latency_ms",
            labels={"component": "mcp", "endpoint": "mcp_ws", "transport": "ws"},
        ).get("count", 0)

        # Open WS and send initialize
        # Authenticate via Authorization header to satisfy ws_auth_required
        ws = client.websocket_connect(
            f"/api/v1/mcp/ws?client_id=test",
            headers={"Authorization": f"Bearer {token}"},
        )
        with ws:
            ws.send_text(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"clientInfo": {"name": "probe", "version": "0.0.1"}},
                    }
                )
            )
            _ = ws.receive_json()

        after = reg.get_metric_stats(
            "ws_send_latency_ms",
            labels={"component": "mcp", "endpoint": "mcp_ws", "transport": "ws"},
        ).get("count", 0)

        assert after >= before + 1
