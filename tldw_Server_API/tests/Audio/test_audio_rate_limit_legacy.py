import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger
from tldw_Server_API.app.api.v1.endpoints.audio.audio import get_tts_service, router as audio_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool


pytestmark = pytest.mark.unit


class _StubRateLimiter:
    def __init__(self) -> None:
        self.enabled = True
        self.calls = []

    async def check_user_rate_limit(self, user_id, endpoint, limit, window_minutes):
        self.calls.append(("user", user_id, endpoint, limit, window_minutes))
        return False, {"error": "Rate limit exceeded."}

    async def check_rate_limit(self, identifier, endpoint, limit, window_minutes):
        self.calls.append(("ip", identifier, endpoint, limit, window_minutes))
        return False, {"error": "Rate limit exceeded."}


class _StubSettings:
    RATE_LIMIT_ENABLED = True


class _StubUsageLogger:
    def log_event(self, *args, **kwargs):
        return None


class _StubTTSService:
    async def generate_speech(self, *args, **kwargs):
        yield b"stub-audio"


async def _fake_get_request_user(request: Request) -> User:
    request.state.user_id = 123
    return User(id=123, username="tester")


async def _fake_get_tts_service() -> _StubTTSService:
    return _StubTTSService()


def _fake_get_usage_event_logger() -> _StubUsageLogger:


    return _StubUsageLogger()


async def _fake_get_db_pool():
    class _StubPool:
        pass

    return _StubPool()


async def _fake_get_jwt_service():
    class _StubJWT:
        def decode_access_token(self, token):  # pragma: no cover - defensive only
            return {}

    return _StubJWT()


def test_audio_speech_does_not_use_legacy_rate_limit_when_rg_disabled(monkeypatch):


    monkeypatch.setenv("RG_ENABLED", "0")
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")

    limiter = _StubRateLimiter()
    monkeypatch.setattr(auth_deps, "get_rate_limiter", lambda: limiter)
    monkeypatch.setattr(auth_deps, "get_settings", lambda: _StubSettings())

    app = FastAPI()

    @app.middleware("http")
    async def _attach_user_id(request: Request, call_next):
        request.state.user_id = 123
        return await call_next(request)

    app.dependency_overrides[get_request_user] = _fake_get_request_user
    app.dependency_overrides[get_tts_service] = _fake_get_tts_service
    app.dependency_overrides[get_usage_event_logger] = _fake_get_usage_event_logger
    app.dependency_overrides[get_db_pool] = _fake_get_db_pool
    app.dependency_overrides[auth_deps.get_jwt_service_dep] = _fake_get_jwt_service
    app.include_router(audio_router, prefix="/api/v1/audio")

    payload = {
        "model": "tts-1",
        "input": "hello",
        "voice": "alloy",
        "response_format": "mp3",
        "stream": False,
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/audio/speech", json=payload, headers={"X-API-KEY": "test-key"})

    # Stage 5: Auth dependency shim is diagnostics-only; no legacy limiter 429 path.
    assert response.status_code == 401
    assert limiter.calls == []
