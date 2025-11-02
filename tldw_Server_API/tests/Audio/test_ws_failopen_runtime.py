import base64
import json
import sqlite3

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_ws_failopen_cap_exhausted_sends_error_and_closes(monkeypatch):
    """
    Exercise the bounded fail-open path in the WS streaming handler:

    - Force DB exceptions from both `check_daily_minutes_allow` and `add_daily_minutes`.
    - Set a tiny per-connection fail-open cap via AUDIO_FAILOPEN_CAP_MINUTES.
    - Send small audio chunks until the cap should be exceeded.
    - Assert the server emits a structured quota error and closes the socket.
    """
    from tldw_Server_API.app.main import app
    import tldw_Server_API.app.api.v1.endpoints.audio as audio_ep
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    # Tiny cap: 0.0003 minutes (~18ms). Two 10ms chunks should exceed it.
    monkeypatch.setenv("AUDIO_FAILOPEN_CAP_MINUTES", "0.0003")

    # Monkeypatch quota helpers to raise DB-like errors that are caught by EXPECTED_DB_EXC
    async def _check_raises(user_id: int, minutes_requested: float):
        raise sqlite3.OperationalError("simulated db unavailable (check)")

    async def _add_raises(user_id: int, minutes: float):
        raise sqlite3.OperationalError("simulated db unavailable (add)")

    monkeypatch.setattr(audio_ep, "check_daily_minutes_allow", _check_raises, raising=True)
    monkeypatch.setattr(audio_ep, "add_daily_minutes", _add_raises, raising=True)

    settings = get_settings()
    token = settings.SINGLE_USER_API_KEY

    with TestClient(app) as client:
        try:
            ws = client.websocket_connect(
                f"/api/v1/audio/stream/transcribe?token={token}"
            )
        except Exception:
            pytest.skip("audio WebSocket endpoint not available in this build")

        with ws as ws:
            # Minimal config; server-side defaults apply
            ws.send_text(json.dumps({"type": "config", "sample_rate": 16000}))

            # Prepare a 10ms chunk: 160 samples at 16kHz, float32 mono
            chunk = (np.zeros(160, dtype=np.float32)).tobytes()
            b64 = base64.b64encode(chunk).decode("ascii")

            # First chunk: should be allowed under bounded fail-open
            ws.send_text(json.dumps({"type": "audio", "data": b64}))

            # Second chunk: should exhaust the tiny fail-open cap and trigger error/close
            ws.send_text(json.dumps({"type": "audio", "data": b64}))

            data = ws.receive_json()
            assert isinstance(data, dict)
            assert data.get("type") == "error"
            assert data.get("error_type") == "quota_exceeded"
            assert data.get("quota") == "daily_minutes"

            # Socket should close after error; subsequent receive should fail
            with pytest.raises(Exception):
                ws.receive_json()
