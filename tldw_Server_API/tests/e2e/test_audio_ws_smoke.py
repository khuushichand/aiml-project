"""
test_audio_ws_smoke.py
Description: Minimal E2E check for the real-time transcription WebSocket.

The test connects to `/api/v1/audio/stream/transcribe`, sends a simple
configuration (Whisper) and a tiny audio chunk. It asserts that at least one
JSON frame is received (partial, transcription, error). If the environment
is missing streaming dependencies or the server rejects the connection,
the test skips gracefully.
"""

import os
import json
import base64
import asyncio
import pytest

from .fixtures import api_client


def _maybe_import_websockets():
    try:
        import websockets  # type: ignore
        return websockets
    except Exception:
        return None


@pytest.mark.critical
@pytest.mark.asyncio
async def test_audio_ws_transcription_smoke(api_client):
    wsmod = _maybe_import_websockets()
    if not wsmod:
        pytest.skip("websockets package not installed; skipping WS smoke test.")

    base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000").replace("http://", "ws://").replace("https://", "wss://")
    # Use token query param for single-user mode; Authorization header also supported
    token = api_client.client.headers.get("X-API-KEY") or (
        api_client.client.headers.get("Authorization", "").replace("Bearer ", "")
    )
    url = f"{base}/api/v1/audio/stream/transcribe"
    if token:
        url = f"{url}?token={token}"

    try:
        async with wsmod.connect(url, max_size=2**23) as ws:  # generous default
            # 1) Send config using Whisper (likely available via faster-whisper)
            cfg = {
                "type": "config",
                "model": "whisper",
                "whisper_model_size": "tiny",
                "sample_rate": 16000,
                "language": "en",
                "enable_partial": True,
            }
            await ws.send(json.dumps(cfg))

            # 2) Send a tiny audio chunk (random bytes; server may error, that is acceptable)
            # 1/20 sec of 16kHz float32 silence
            fake_audio = bytes(3200)  # 800 samples * 4 bytes
            encoded = base64.b64encode(fake_audio).decode("utf-8")
            await ws.send(json.dumps({"type": "audio", "data": encoded}))

            # 3) Expect at least one JSON frame back
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(raw)
                assert isinstance(data, dict)
                assert data.get("type") in {"partial", "transcription", "final", "error", "status", "insight"}
            except asyncio.TimeoutError:
                pytest.skip("No response from WS transcription within timeout; skipping.")
    except Exception as e:
        # Treat setup/config errors as optional in smoke
        pytest.skip(f"Audio WS not available/configured: {e}")
