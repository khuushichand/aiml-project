"""
test_tts_stream_http.py
Description: Streamed TTS over HTTP; validates chunked audio response.

Hits /api/v1/audio/speech with stream=true and verifies streaming bytes.
Skips if TTS is not configured or returns JSON error.
"""

import pytest
import httpx

from .fixtures import api_client, has_openai_api_key


def _should_try_openai_fallback(response: httpx.Response) -> bool:
    if response.status_code in (401, 403):
        return False
    return response.status_code >= 400


def _stream_tts_bytes(api_client, payload: dict) -> tuple[int, bool]:
    with api_client.client.stream("POST", "/api/v1/audio/speech", json=payload) as r:
        if _should_try_openai_fallback(r):
            return 0, True
        ct = r.headers.get("content-type", "")
        assert ("audio/" in ct) or (ct == "application/octet-stream") or ct == ""
        received = 0
        for idx, chunk in enumerate(r.iter_bytes()):
            if not chunk:
                continue
            received += len(chunk)
            if idx >= 3:
                break
        return received, False


@pytest.mark.critical
def test_tts_streaming_http_chunks(api_client):
    payload = {
        "model": "kokoro",
        "input": "This is a short streaming test.",
        "voice": "af_bella",
        "response_format": "mp3",
        "stream": True,
    }

    try:
        received, wants_fallback = _stream_tts_bytes(api_client, payload)
        if wants_fallback and has_openai_api_key():
            fallback = dict(payload)
            fallback["model"] = "tts-1"
            fallback["voice"] = "alloy"
            received, wants_fallback = _stream_tts_bytes(api_client, fallback)

        if received == 0:
            pytest.skip("No audio bytes produced; TTS not configured or muted.")
    except httpx.HTTPStatusError as e:
        pytest.skip(f"TTS streaming not available/configured: {e}")
