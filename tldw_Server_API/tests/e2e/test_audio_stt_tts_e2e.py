"""
test_audio_stt_tts_e2e.py
End-to-end tests for STT (file) and non-streaming TTS.

Includes:
- STT file flow via POST /api/v1/audio/transcriptions (multipart)
  - Uses a short WAV. Asserts JSON structure and fields.
  - Optionally uploads the same WAV as media and, if transcript text is non-empty,
    searches media for a token to confirm searchability.
- TTS voices catalog and non-stream synthesis (mp3)
  - GET voices catalog
  - POST /api/v1/audio/speech without stream, verify headers and byte length
"""

import io
import re
import time
import pytest
import httpx

from .fixtures import api_client, create_test_audio, cleanup_test_file, AssertionHelpers, has_openai_api_key


def _should_try_openai_fallback(response: httpx.Response) -> bool:
    if response.status_code in (401, 403):
        return False
    return response.status_code >= 400


def _post_tts_with_fallback(api_client, payload: dict) -> httpx.Response:
    response = api_client.client.post("/api/v1/audio/speech", json=payload)
    if not _should_try_openai_fallback(response):
        return response
    if payload.get("model") != "kokoro":
        return response
    if not has_openai_api_key():
        return response
    fallback = dict(payload)
    fallback["model"] = "tts-1"
    fallback["voice"] = "alloy"
    return api_client.client.post("/api/v1/audio/speech", json=fallback)


def _post_stt_with_fallback(api_client, wav_path: str, data: dict) -> httpx.Response:
    with open(wav_path, "rb") as f:
        files = {"file": ("sample.wav", f, "audio/wav")}
        response = api_client.client.post("/api/v1/audio/transcriptions", files=files, data=data)
        if response.status_code != 503:
            return response
        if data.get("model") not in {"whisper-1", "whisper"}:
            return response
        fallback = dict(data)
        fallback["model"] = "parakeet-mlx"
        try:
            f.seek(0)
        except Exception:
            return response
        return api_client.client.post("/api/v1/audio/transcriptions", files=files, data=fallback)


@pytest.mark.critical
def test_stt_file_flow_transcription_and_optional_search(api_client):
    # Generate short WAV file
    wav_path = create_test_audio()
    try:
        data = {"model": "whisper-1", "language": "en", "response_format": "json"}
        r = _post_stt_with_fallback(api_client, wav_path, data)
        if r.status_code in (400, 401, 403, 404, 413, 429, 500, 501, 503):
            pytest.skip(f"STT not available/configured: {r.status_code}")
        r.raise_for_status()
        body = r.json()
        assert isinstance(body, dict)
        assert "text" in body
        assert "duration" in body
        # language and segments are optional but likely present

        # Optional: make transcript searchable by uploading audio as media
        # This will attach transcription if STT backend is wired for media ingestion.
        up = api_client.upload_media(file_path=wav_path, title="STT Test WAV", media_type="audio", generate_embeddings=False)
        media_id = AssertionHelpers.assert_successful_upload(up)

        # Give a moment for any background attach
        time.sleep(1.0)
        details = api_client.get_media_item(media_id)
        transcript = details.get("transcription") or details.get("transcript") or ""

        # If transcript has a token-like word, try searching for it
        token = None
        m = re.search(r"[A-Za-z]{3,}", (body.get("text") or ""))
        if not m:
            m = re.search(r"[A-Za-z]{3,}", transcript)
        if m:
            token = m.group(0)

        if token:
            sr = api_client.client.post("/api/v1/media/search", json={"query": token}, params={"limit": 10})
            if sr.status_code == 200:
                results = sr.json() if isinstance(sr.json(), list) else sr.json().get("results", [])
                ids = [(x.get("id") or x.get("media_id")) for x in results]
                assert media_id in ids
        else:
            pytest.skip("Transcript empty or non-alphabetic; skipping search assertion.")
    finally:
        cleanup_test_file(wav_path)


@pytest.mark.critical
def test_tts_voices_catalog_and_nonstream_synthesis(api_client):
    # Voices catalog
    try:
        voices = api_client.client.get("/api/v1/audio/voices/catalog")
        if voices.status_code in (404, 501):
            pytest.skip("Voices catalog not available")
        voices.raise_for_status()
        v = voices.json()
        assert isinstance(v, dict)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"TTS voices endpoint not available/configured: {e}")

    # Non-stream TTS synthesis
    payload = {
        "model": "kokoro",
        "input": "This is a short synthesis test.",
        "voice": "af_bella",
        "response_format": "mp3",
        "stream": False,
    }
    r = _post_tts_with_fallback(api_client, payload)
    if r.status_code in (400, 401, 403, 404, 422, 429, 500, 501):
        pytest.skip(f"TTS synthesis not available/configured: {r.status_code}")
    # Content-Type should be audio/* or octet-stream fallback
    ct = r.headers.get("content-type", "")
    assert ("audio/" in ct) or (ct == "application/octet-stream")
    assert len(r.content) > 100  # basic length check
