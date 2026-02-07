import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.audio.audio import router as audio_router
from tldw_Server_API.app.api.v1.endpoints.audio import audio_voices
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-1234567890")
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", "1")
    reset_settings()
    app = FastAPI()
    app.include_router(audio_router, prefix="/api/v1/audio")

    async def _deny_rate_limit():
        raise HTTPException(status_code=429, detail="rate limited in test")

    app.dependency_overrides[audio_voices.check_rate_limit] = _deny_rate_limit
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(audio_voices.check_rate_limit, None)


def test_voice_list_route_enforces_rate_limit_dependency(client):
    response = client.get(
        "/api/v1/audio/voices",
        headers={"X-API-KEY": "test-api-key-1234567890"},
    )
    assert response.status_code == 429
