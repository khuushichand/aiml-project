import os
import time
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.asyncio
async def test_audio_ws_idle_timeout_increments_metric(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    # Short idle timeout; disable WS pings to avoid noise
    monkeypatch.setenv("AUDIO_WS_IDLE_TIMEOUT_S", "0.1")
    monkeypatch.setenv("STREAM_HEARTBEAT_INTERVAL_S", "0")

    settings = get_settings()
    token = settings.SINGLE_USER_API_KEY

    reg = get_metrics_registry()
    before = reg.get_metric_stats(
        "ws_idle_timeouts_total",
        labels={"component": "audio", "endpoint": "audio_unified_ws", "transport": "ws"},
    ).get("count", 0)

    with TestClient(app) as client:
        try:
            ws = client.websocket_connect(f"/api/v1/audio/stream/transcribe?token={token}")
        except Exception:
            pytest.skip("audio WebSocket endpoint not available in this build")

        # Let idle loop trigger on the server
        with ws:
            time.sleep(0.25)
            # The server should have closed the socket by now due to idle
            # Client context exit will ignore closure exceptions
            pass

    after = reg.get_metric_stats(
        "ws_idle_timeouts_total",
        labels={"component": "audio", "endpoint": "audio_unified_ws", "transport": "ws"},
    ).get("count", 0)

    assert after >= before + 1
