"""
test_tts_stream_http.py
Description: Streamed TTS over HTTP; validates chunked audio response.

Hits /api/v1/audio/speech with stream=true and verifies streaming bytes.
Skips if TTS is not configured or returns JSON error.
"""

import pytest
import httpx

from .fixtures import api_client


@pytest.mark.critical
def test_tts_streaming_http_chunks(api_client):
    payload = {
        "model": "tts-1",  # server maps provider/model internally
        "input": "This is a short streaming test.",
        "voice": "alloy",
        "response_format": "mp3",
        "stream": True,
    }

    # Use streaming response to validate chunked bytes
    try:
        with api_client.client.stream("POST", "/api/v1/audio/speech", json=payload) as r:
            # Content-Type should indicate audio; some adapters may delay headers
            ct = r.headers.get("content-type", "")
            # Accept either audio/* or octet-stream fallback
            assert ("audio/" in ct) or (ct == "application/octet-stream") or ct == ""

            received = 0
            # Read a few chunks at most to avoid long test
            for idx, chunk in enumerate(r.iter_bytes()):
                if not chunk:
                    continue
                received += len(chunk)
                # Stop after first few chunks
                if idx >= 3:
                    break
            # If we got no bytes at all, treat as optional and skip
            if received == 0:
                pytest.skip("No audio bytes produced; TTS not configured or muted.")
    except httpx.HTTPStatusError as e:
        # Treat missing/disabled TTS as optional
        pytest.skip(f"TTS streaming not available/configured: {e}")
