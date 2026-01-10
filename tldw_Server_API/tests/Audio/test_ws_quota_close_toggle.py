import json
import base64
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_ws_quota_close_code_toggle_to_1008(monkeypatch):


     """When AUDIO_WS_QUOTA_CLOSE_1008=1, quota closes should use code 1008 instead of legacy 4003."""
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    import tldw_Server_API.app.api.v1.endpoints.audio as audio_ep

    # Enable new close code policy
    monkeypatch.setenv("AUDIO_WS_QUOTA_CLOSE_1008", "1")

    # Force daily-minutes check to immediately deny
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
            # Minimal config and tiny audio chunk
            ws.send_text(json.dumps({"type": "config", "sample_rate": 16000}))
            audio = (np.zeros(160, dtype=np.float32)).tobytes()
            ws.send_text(json.dumps({"type": "audio", "data": base64.b64encode(audio).decode("ascii")}))

            # Expect an error payload indicating quota exceeded
            data = ws.receive_json()
            assert isinstance(data, dict)
            assert data.get("type") == "error"
            assert data.get("error_type") == "quota_exceeded"

            # Next receive should raise disconnect with code 1008 under the toggle
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_text()
            # Starlette's WebSocketDisconnect carries the close code
            assert getattr(exc.value, "code", None) == 1008
