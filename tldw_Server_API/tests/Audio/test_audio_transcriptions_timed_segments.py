import io

import numpy as np
import pytest
import soundfile as sf
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.audio.audio import router as audio_router

TEST_API_KEY = "test-api-key-1234567890"


def _make_wav_bytes(duration_sec: float = 0.1, sr: int = 16000) -> bytes:
    buf = io.BytesIO()
    data = np.zeros(int(sr * duration_sec), dtype=np.float32)
    sf.write(buf, data, sr, format="WAV")
    return buf.getvalue()


def _setup_stubbed_audio_app(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", "1")

    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
    import tldw_Server_API.app.api.v1.endpoints.audio.audio as audio_ep
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as atlib
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter as stt_adapter

    async def _fake_get_request_user() -> User:
        return User(id=1, username="single_user")

    async def _allow_job(*_args, **_kwargs):
        return True, None

    async def _noop_async(*_args, **_kwargs):
        return None

    class _StubAdapter:
        def transcribe_batch(
            self,
            _audio_path,
            *,
            model=None,
            language=None,
            task="transcribe",
            word_timestamps=False,
            prompt=None,
            hotwords=None,
            base_dir=None,
        ):
            _ = (task, word_timestamps, prompt, hotwords, base_dir)
            return {
                "text": "first line second line",
                "language": language or "en",
                "segments": [
                    {
                        "start_seconds": 1.0,
                        "end_seconds": 2.5,
                        "Text": "first line",
                        "words": [
                            {"start": 1.0, "end": 1.4, "word": "first"},
                            {"start": 1.4, "end": 2.5, "word": "line"},
                        ],
                    },
                    {
                        "start_seconds": 2.5,
                        "end_seconds": 4.0,
                        "Text": "second line",
                        "words": [
                            {"start": 2.5, "end": 3.2, "word": "second"},
                            {"start": 3.2, "end": 4.0, "word": "line"},
                        ],
                    },
                ],
                "diarization": {"enabled": False, "speakers": None},
                "usage": {"duration_ms": None, "tokens": None},
                "metadata": {"provider": "parakeet", "model": model or "parakeet-mlx"},
            }

    class _StubRegistry:
        def resolve_provider_for_model(self, _model):
            return "parakeet", "parakeet-mlx", "mlx"

        def get_adapter(self, _provider):
            return _StubAdapter()

    monkeypatch.setattr(audio_ep, "can_start_job", _allow_job)
    monkeypatch.setattr(audio_ep, "increment_jobs_started", _noop_async)
    monkeypatch.setattr(audio_ep, "finish_job", _noop_async)
    monkeypatch.setattr(audio_ep, "check_daily_minutes_allow", _allow_job)
    monkeypatch.setattr(audio_ep, "add_daily_minutes", _noop_async)
    monkeypatch.setattr(stt_adapter, "get_stt_provider_registry", lambda: _StubRegistry())
    monkeypatch.setattr(atlib, "convert_to_wav", lambda path, *args, **kwargs: path)

    app = FastAPI()
    app.dependency_overrides[get_request_user] = _fake_get_request_user
    app.include_router(audio_router, prefix="/api/v1/audio")
    return app


@pytest.mark.unit
def test_audio_transcriptions_uses_provider_timed_segments_for_srt(monkeypatch, bypass_api_limits):
    app = _setup_stubbed_audio_app(monkeypatch)

    with bypass_api_limits(app), TestClient(app) as client:
        wav_bytes = _make_wav_bytes()
        headers = {"X-API-KEY": TEST_API_KEY}
        files = {"file": ("sample.wav", io.BytesIO(wav_bytes), "audio/wav")}
        data = {
            "model": "parakeet-mlx",
            "response_format": "srt",
        }
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers=headers,
            files=files,
            data=data,
        )
        if resp.status_code == 404:
            pytest.skip("audio/transcriptions endpoint not mounted in this build")
        assert resp.status_code == 200, resp.text
        assert "00:00:01,000 --> 00:00:02,500" in resp.text
        assert "00:00:02,500 --> 00:00:04,000" in resp.text
        assert "00:00:00,000 --> 00:00:10,000" not in resp.text


@pytest.mark.unit
def test_audio_transcriptions_uses_provider_timed_segments_for_vtt(monkeypatch, bypass_api_limits):
    app = _setup_stubbed_audio_app(monkeypatch)

    with bypass_api_limits(app), TestClient(app) as client:
        wav_bytes = _make_wav_bytes()
        headers = {"X-API-KEY": TEST_API_KEY}
        files = {"file": ("sample.wav", io.BytesIO(wav_bytes), "audio/wav")}
        data = {
            "model": "parakeet-mlx",
            "response_format": "vtt",
        }
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers=headers,
            files=files,
            data=data,
        )
        if resp.status_code == 404:
            pytest.skip("audio/transcriptions endpoint not mounted in this build")
        assert resp.status_code == 200, resp.text
        assert resp.text.startswith("WEBVTT")
        assert "00:00:01.000 --> 00:00:02.500" in resp.text
        assert "00:00:02.500 --> 00:00:04.000" in resp.text


@pytest.mark.unit
def test_audio_transcriptions_verbose_json_exposes_timed_segments_for_parakeet(monkeypatch, bypass_api_limits):
    app = _setup_stubbed_audio_app(monkeypatch)

    with bypass_api_limits(app), TestClient(app) as client:
        wav_bytes = _make_wav_bytes()
        headers = {"X-API-KEY": TEST_API_KEY}
        files = {"file": ("sample.wav", io.BytesIO(wav_bytes), "audio/wav")}
        data = {
            "model": "parakeet-mlx",
            "response_format": "verbose_json",
            "timestamp_granularities": "segment,word",
        }
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers=headers,
            files=files,
            data=data,
        )
        if resp.status_code == 404:
            pytest.skip("audio/transcriptions endpoint not mounted in this build")
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["segments"][0]["start"] == pytest.approx(1.0)
        assert payload["segments"][0]["end"] == pytest.approx(2.5)
        assert payload["segments"][0]["text"] == "first line"
        assert payload["segments"][0]["words"][0]["word"] == "first"
        assert payload["segments"][1]["start"] == pytest.approx(2.5)

