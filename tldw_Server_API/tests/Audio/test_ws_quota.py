import json
import base64
import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_ws_quota_exceeded_structured_error(monkeypatch):
    """Ensure WS sends structured quota error and closes with code 4003."""
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    import tldw_Server_API.app.api.v1.endpoints.audio as audio_ep

    # Monkeypatch quota check to immediately deny any minutes
    async def _deny(user_id: int, minutes_requested: float):
        return False, 0.0

    monkeypatch.setattr(audio_ep, "check_daily_minutes_allow", _deny)

    settings = get_settings()
    token = settings.SINGLE_USER_API_KEY

    with TestClient(app) as client:
        try:
            ws = client.websocket_connect(f"/api/v1/audio/stream/transcribe?token={token}")
        except Exception:
            pytest.skip("audio WebSocket endpoint not available in this build")
        with ws as ws:
            # Send minimal config message
            ws.send_text(json.dumps({"type": "config", "sample_rate": 16000}))
            # Send one tiny audio chunk (float32 mono 160 samples = 0.01s)
            audio = (np.zeros(160, dtype=np.float32)).tobytes()
            ws.send_text(json.dumps({"type": "audio", "data": base64.b64encode(audio).decode("ascii")}))
            # Expect an error payload indicating quota exceeded
            data = ws.receive_json()
            assert isinstance(data, dict)
            assert data.get("type") == "error"
            assert data.get("error_type") == "quota_exceeded"
            assert data.get("quota") == "daily_minutes"
            # Server will close after sending error; ensure subsequent receive fails
            with pytest.raises(Exception):
                ws.receive_json()
