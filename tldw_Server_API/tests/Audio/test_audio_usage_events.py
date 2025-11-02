import asyncio
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.endpoints.audio import get_tts_service
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger


pytestmark = pytest.mark.unit


class _DummyLogger:
    def __init__(self):
        self.events = []
    def log_event(self, name, resource_id=None, tags=None, metadata=None):
        self.events.append((name, resource_id, tags, metadata))


class _FakeTTSService:
    async def generate_speech(self, request_data, provider=None, fallback=True):
        yield b"audio-bytes"


@pytest.fixture()
def client_with_overrides():
    dummy = _DummyLogger()

    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    def override_logger():
        return dummy

    async def override_tts():
        return _FakeTTSService()

    # Apply overrides
    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_usage_event_logger] = override_logger
    fastapi_app.dependency_overrides[get_tts_service] = override_tts

    with TestClient(fastapi_app) as client:
        yield client, dummy

    fastapi_app.dependency_overrides.clear()


def test_tts_usage_event_logged(client_with_overrides):
    client, dummy = client_with_overrides
    payload = {
        "model": "tts-1",
        "input": "hello",
        "voice": "alloy",
        "response_format": "mp3",
        "stream": False
    }
    r = client.post("/api/v1/audio/speech", json=payload)
    assert r.status_code == 200, r.text
    # Ensure a usage event was logged
    assert any(e[0] == "audio.tts" for e in dummy.events)
