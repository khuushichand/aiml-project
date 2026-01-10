import json
import base64
import numpy as np
import pytest
from fastapi.testclient import TestClient


def test_audio_ws_invalid_json_yields_validation_error(monkeypatch):


     from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    token = get_settings().SINGLE_USER_API_KEY

    with TestClient(app) as client:
        try:
            ws = client.websocket_connect(f"/api/v1/audio/stream/transcribe?token={token}")
        except Exception:
            pytest.skip("audio WebSocket endpoint not available in this build")
        with ws as ws:
            # Send minimal config then an invalid JSON frame (as text that's not JSON)
            ws.send_text(json.dumps({"type": "config", "sample_rate": 16000}))
            ws.send_text("not-json")
            msg = ws.receive_json()
            assert isinstance(msg, dict)
            assert msg.get("type") == "error"
            assert msg.get("code") == "validation_error"
            # compat shim from WebSocketStream
            assert msg.get("error_type") == "validation_error"
