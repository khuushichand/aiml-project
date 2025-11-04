import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.asyncio
async def test_audio_ws_emits_ws_latency_metrics_on_commit():
    """Connecting to audio WS and sending a commit should emit ws_send_latency_ms via stream wrapper."""
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    token = settings.SINGLE_USER_API_KEY

    reg = get_metrics_registry()
    before = reg.get_metric_stats("ws_send_latency_ms").get("count", 0)

    with TestClient(app) as client:
        try:
            ws = client.websocket_connect(f"/api/v1/audio/stream/transcribe?token={token}")
        except Exception:
            pytest.skip("audio WebSocket endpoint not available in this build")

        with ws as ws:
            # Minimal config message to satisfy handler; avoid model loading side effects
            ws.send_text(json.dumps({"type": "config", "sample_rate": 16000}))
            # Immediately commit (no audio) to trigger full_transcript frame via stream.send_json
            ws.send_text(json.dumps({"type": "commit"}))

            # Read at least one server message to ensure send path executed
            try:
                _ = ws.receive_json()
            except Exception:
                # If nothing arrives, this still validates that server attempted send_json
                pass

    after = reg.get_metric_stats("ws_send_latency_ms").get("count", 0)
    assert after >= before + 1

