import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.audio import router as audio_router


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-1234567890")
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", "1")
    app = FastAPI()
    app.include_router(audio_router, prefix="/api/v1/audio")
    with TestClient(app) as c:
        yield c


@pytest.mark.unit
def test_transcriptions_health_basic_status(client: TestClient):
    """
    The STT health endpoint should respond with a basic status payload
    even when models are not yet downloaded.
    """
    r = client.get("/api/v1/audio/transcriptions/health")
    assert r.status_code == 200
    data = r.json()
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import (
        Audio_Transcription_Lib as stt_lib,
    )
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
        resolve_default_transcription_model,
    )

    default_model = resolve_default_transcription_model("whisper-1")
    provider_raw, _, _ = stt_lib.parse_transcription_model(default_model)
    assert data.get("provider") == provider_raw
    assert "model" in data
    assert "available" in data


@pytest.mark.unit
def test_transcriptions_health_warm_uses_whisper_model(monkeypatch, client: TestClient):
    """
    When warm=true and the provider is Whisper, the endpoint should attempt
    to initialize the underlying faster-whisper model via get_whisper_model,
    and report a warm.ok flag without raising even if initialization fails.
    """
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as atlib

    calls = {}

    def fake_get_whisper_model(model_name, device, check_download_status=False):

        calls["model_name"] = model_name
        calls["device"] = device
        calls["check_download_status"] = check_download_status
        # Return a lightweight sentinel object; STT health does not inspect it.
        return object()

    monkeypatch.setattr(atlib, "get_whisper_model", fake_get_whisper_model)

    r = client.get("/api/v1/audio/transcriptions/health", params={"model": "whisper-1", "warm": "true"})
    assert r.status_code == 200
    data = r.json()

    assert data.get("provider") == "whisper"
    warm = data.get("warm") or {}
    assert warm.get("ok") is True
    assert calls.get("model_name") is not None
