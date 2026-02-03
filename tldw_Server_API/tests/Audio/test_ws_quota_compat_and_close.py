import json
import base64
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_audio_ws_quota_error_includes_error_type_and_closes_1008(monkeypatch):


    """Quota errors should include error_type and close with code 1008.

    Compatibility: also accepts legacy top-level 'quota' while data.quota remains the canonical field.
    """
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    import tldw_Server_API.app.api.v1.endpoints.audio.audio as audio_ep

    # Force daily minutes denial
    async def _deny(user_id: int, minutes_requested: float):
        return False, 0.0

    monkeypatch.setattr(audio_ep, "check_daily_minutes_allow", _deny)

    token = get_settings().SINGLE_USER_API_KEY

    with TestClient(app) as client:
        try:
            ws = client.websocket_connect(f"/api/v1/audio/stream/transcribe?token={token}")
        except Exception:
            pytest.skip("audio WebSocket endpoint not available in this build")
        with ws as ws:
            # Minimal config and tiny audio to trigger quota path
            ws.send_text(json.dumps({"type": "config", "sample_rate": 16000}))
            audio = (np.zeros(160, dtype=np.float32)).tobytes()
            ws.send_text(json.dumps({"type": "audio", "data": base64.b64encode(audio).decode("ascii")}))

            # Expect standardized error frame with compatibility fields
            msg = ws.receive_json()
            assert isinstance(msg, dict)
            assert msg.get("type") == "error"
            # New fields
            assert msg.get("code") == "quota_exceeded"
            assert msg.get("message")
            # Compat field for rollout
            assert msg.get("error_type") == "quota_exceeded"
            # Quota is present in data and (compat) at top-level
            dq = (msg.get("data") or {}).get("quota")
            tq = msg.get("quota")
            assert (dq == "daily_minutes") or (tq == "daily_minutes")

            # Socket should then close with 1008
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_text()
            assert getattr(exc.value, "code", None) == 1008
