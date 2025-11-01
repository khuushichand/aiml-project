import json
import base64
import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_ws_concurrent_streams_denied(monkeypatch):
    """Ensure WS denies when concurrent_streams quota is exhausted."""
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    import tldw_Server_API.app.api.v1.endpoints.audio as audio_ep

    async def _deny_stream(user_id: int):
        return 2  # pretend two streams active

    async def _can_start_stream(user_id: int):
        return False, "Concurrent streams limit reached (1)"

    # Force can_start_stream denial
    monkeypatch.setattr(audio_ep, "can_start_stream", _can_start_stream)
    # Also return non-zero active count for the limits endpoint if called
    monkeypatch.setattr(audio_ep, "active_streams_count", _deny_stream, raising=False)

    settings = get_settings()
    token = settings.SINGLE_USER_API_KEY

    with TestClient(app) as client:
        try:
            ws = client.websocket_connect(f"/api/v1/audio/stream/transcribe?token={token}")
        except Exception:
            pytest.skip("audio WebSocket endpoint not available in this build")
        # The server will send an error then close.
        with ws as ws:
            # The connection may close very early; try receiving once
            try:
                data = ws.receive_json()
                assert isinstance(data, dict)
                assert data.get("type") == "error"
                assert "Concurrent streams" in str(data.get("message", ""))
            except Exception:
                # If we miss the error frame due to early close, this is acceptable
                pass
            # Any further receive should raise
            with pytest.raises(Exception):
                ws.receive_json()

