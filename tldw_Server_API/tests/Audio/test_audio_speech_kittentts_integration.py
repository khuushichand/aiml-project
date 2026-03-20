import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints import audio as audio_endpoints
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.main import app


pytestmark = pytest.mark.integration


class _RecordingKittenTTSService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_speech(
        self,
        request_data,
        provider=None,
        fallback=True,
        provider_overrides=None,
        voice_to_voice_start=None,
        voice_to_voice_route="audio.speech",
        user_id=None,
        request_id=None,
        metadata_only=False,
    ):
        self.calls.append(
            {
                "request_data": request_data,
                "provider": provider,
                "fallback": fallback,
                "provider_overrides": provider_overrides,
                "voice_to_voice_start": voice_to_voice_start,
                "voice_to_voice_route": voice_to_voice_route,
                "user_id": user_id,
                "request_id": request_id,
                "metadata_only": metadata_only,
            }
        )

        async def _gen():
            yield b"kitten-audio"

        return _gen()


@pytest.fixture()
def _client_with_kitten_overrides(bypass_api_limits):
    async def _override_user():
        return User(id=1, username="tester", email="tester@example.com", is_active=True)

    service = _RecordingKittenTTSService()

    async def _override_tts_service():
        return service

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_request_user] = _override_user
    app.dependency_overrides[audio_endpoints.get_tts_service] = _override_tts_service

    try:
        with bypass_api_limits(app), TestClient(app) as client:
            yield client, service
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def test_audio_speech_routes_kitten_tts_through_current_backend_path(_client_with_kitten_overrides):
    client, service = _client_with_kitten_overrides
    settings = get_settings()

    response = client.post(
        "/api/v1/audio/speech",
        json={
            "model": "kitten_tts",
            "input": "Hello from kitten TTS",
            "voice": "kitten_voice",
            "response_format": "mp3",
            "stream": False,
        },
        headers={"X-API-KEY": settings.SINGLE_USER_API_KEY},
    )

    assert response.status_code == 200, response.text
    assert response.content == b"kitten-audio"
    assert response.headers.get("content-type", "").startswith("audio/mpeg")
    assert len(service.calls) == 1
    call = service.calls[0]
    assert call["provider"] == "kitten_tts"
    assert getattr(call["request_data"], "model", None) == "kitten_tts"
    assert getattr(call["request_data"], "input", None) == "Hello from kitten TTS"
