import os
import pytest
from unittest.mock import AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.audio.audio import router as audio_router
from tldw_Server_API.app.api.v1.endpoints import audio as audio_endpoints
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.TTS.adapters.base import TTSResponse
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2
from tldw_Server_API.app.core.TTS.voice_manager import VoiceReferenceMetadata


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-1234567890")
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", "1")
    reset_settings()
    app = FastAPI()
    app.include_router(audio_router, prefix="/api/v1/audio")
    with TestClient(app) as c:
        yield c


def test_custom_voice_resolution_populates_reference(client, monkeypatch):
    class _FakeVoiceManager:
        async def load_voice_reference_audio(self, user_id, voice_id):
            assert str(user_id) == "1"
            assert voice_id == "voice-1"
            return b"RIFF" + b"\x00" * 1000

        async def load_reference_metadata(self, user_id, voice_id):
            return VoiceReferenceMetadata(
                voice_id=voice_id,
                reference_text="stored text",
                provider_artifacts={
                    "neutts": {
                        "ref_codes": [1, 2, 3],
                        "reference_text": "stored text",
                    }
                },
            )

    class _FakeAdapter:
        provider_name = "neutts"
        provider_key = "neutts"

        async def generate(self, request):
            assert request.voice_reference is not None
            assert request.extra_params.get("ref_codes") == [1, 2, 3]
            assert request.extra_params.get("reference_text") == "stored text"
            return TTSResponse(audio_data=b"ok", format=request.format, sample_rate=24000)

    def _fake_get_voice_manager():
        return _FakeVoiceManager()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.voice_manager.get_voice_manager",
        _fake_get_voice_manager,
        raising=True,
    )

    class _FakeFactory:
        def get_provider_for_model(self, _model):
            return "neutts"

    service = TTSServiceV2()
    service._ensure_factory = AsyncMock(return_value=_FakeFactory())
    service._get_adapter = AsyncMock(return_value=_FakeAdapter())

    async def _fake_get_tts_service_v2():
        return service

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_service_v2.get_tts_service_v2",
        _fake_get_tts_service_v2,
        raising=True,
    )

    client.app.dependency_overrides[audio_endpoints.get_tts_service] = _fake_get_tts_service_v2

    payload = {
        "model": "neutts-air",
        "input": "Hello world",
        "voice": "custom:voice-1",
        "response_format": "pcm",
        "stream": False,
    }
    try:
        r = client.post(
            "/api/v1/audio/speech",
            json=payload,
            headers={"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]},
        )
        assert r.status_code == 200, r.text
        assert r.content == b"ok"
    finally:
        client.app.dependency_overrides.pop(audio_endpoints.get_tts_service, None)
