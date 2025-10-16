"""
Auth tests for /api/v1/audio/transcriptions and /api/v1/audio/translations.
Uses dependency overrides to simulate authenticated user and monkeypatches
transcription functions to avoid heavy model calls.
"""

import io
import math
import struct
import wave

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

pytestmark = [pytest.mark.integration]


def _make_wav_bytes(duration_sec: float = 0.1, sr: int = 16000, freq: float = 440.0) -> bytes:
    """Generate a small mono 16-bit PCM WAV for testing."""
    n_samples = int(duration_sec * sr)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n_samples):
            sample = int(32767 * 0.2 * math.sin(2 * math.pi * freq * (i / sr)))
            frames += struct.pack('<h', sample)
        wf.writeframes(frames)
    return buf.getvalue()


def test_transcriptions_requires_auth_401():
    with TestClient(app) as client:
        wav_bytes = _make_wav_bytes()
        files = {"file": ("test.wav", wav_bytes, "audio/wav")}
        data = {"model": "whisper-1", "response_format": "json"}
        resp = client.post("/api/v1/audio/transcriptions", files=files, data=data)
        assert resp.status_code == 401


def test_transcriptions_ok_with_override(monkeypatch):
    with TestClient(app) as client:
        async def _override_user():
            return User(id=1, username="tester", email="t@example.com", is_active=True)

        app.dependency_overrides[get_request_user] = _override_user

        # Patch the production function used by the endpoint (faster-whisper path)
        def _fake_speech_to_text(*args, **kwargs):
            # Endpoint expects a tuple (segments_list, detected_language) when return_language=True
            segments = [
                {"start_seconds": 0.0, "end_seconds": 0.1, "Text": "stubbed transcript"}
            ]
            return (segments, "en")

        monkeypatch.setattr(
            "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib.speech_to_text",
            _fake_speech_to_text,
            raising=False,
        )

        try:
            wav_bytes = _make_wav_bytes()
            files = {"file": ("test.wav", wav_bytes, "audio/wav")}
            data = {"model": "whisper-1", "response_format": "json"}
            resp = client.post("/api/v1/audio/transcriptions", files=files, data=data)
            assert resp.status_code == 200
            assert resp.json().get("text") == "stubbed transcript"
        finally:
            app.dependency_overrides.pop(get_request_user, None)


def test_translations_requires_auth_401():
    with TestClient(app) as client:
        wav_bytes = _make_wav_bytes()
        files = {"file": ("test.wav", wav_bytes, "audio/wav")}
        data = {"model": "whisper-1", "response_format": "json"}
        resp = client.post("/api/v1/audio/translations", files=files, data=data)
        assert resp.status_code == 401


def test_translations_ok_with_override(monkeypatch):
    with TestClient(app) as client:
        async def _override_user():
            return User(id=1, username="tester", email="t@example.com", is_active=True)

        app.dependency_overrides[get_request_user] = _override_user

        # Patch the production function used by the endpoint (faster-whisper path)
        def _fake_speech_to_text(*args, **kwargs):
            segments = [
                {"start_seconds": 0.0, "end_seconds": 0.1, "Text": "translated transcript"}
            ]
            return (segments, "en")

        monkeypatch.setattr(
            "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib.speech_to_text",
            _fake_speech_to_text,
            raising=False,
        )

        try:
            wav_bytes = _make_wav_bytes()
            files = {"file": ("test.wav", wav_bytes, "audio/wav")}
            data = {"model": "whisper-1", "response_format": "json"}
            resp = client.post("/api/v1/audio/translations", files=files, data=data)
            assert resp.status_code == 200
            assert resp.json().get("text") == "translated transcript"
        finally:
            app.dependency_overrides.pop(get_request_user, None)
