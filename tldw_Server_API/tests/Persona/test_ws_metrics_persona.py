import json
import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.asyncio
async def test_persona_ws_emits_ws_latency_metrics(monkeypatch):
    """Ensure Persona WS sends frames via WebSocketStream and increments ws_send_latency_ms with labels."""
    # Ensure the route is enabled for this test run
    monkeypatch.setenv("ROUTES_ENABLE", "persona")
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    api_key = settings.SINGLE_USER_API_KEY

    reg = get_metrics_registry()
    before = reg.get_metric_stats(
        "ws_send_latency_ms",
        labels={"component": "persona", "endpoint": "persona_ws", "transport": "ws"},
    ).get("count", 0)

    with TestClient(app) as client:
        try:
            ws = client.websocket_connect(f"/api/v1/persona/stream?api_key={api_key}")
        except Exception:
            pytest.skip("persona WebSocket endpoint not available")

        with ws as ws:
            # Expect a server notice on connect; then send a simple user message
            try:
                _ = ws.receive_json()
            except Exception:
                pass
            ws.send_text(json.dumps({"type": "user_message", "text": "hello"}))
            try:
                _ = ws.receive_json()
            except Exception:
                pass

    after = reg.get_metric_stats(
        "ws_send_latency_ms",
        labels={"component": "persona", "endpoint": "persona_ws", "transport": "ws"},
    ).get("count", 0)

    assert after >= before + 1
