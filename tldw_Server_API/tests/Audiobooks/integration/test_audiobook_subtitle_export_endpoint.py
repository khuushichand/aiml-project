import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.audiobooks import router as audiobooks_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

pytestmark = pytest.mark.integration


def _post_subtitles(client, payload):
    return client.post("/api/v1/audiobooks/subtitles", json=payload)


@pytest.fixture()
def client_user_only(monkeypatch):
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "false")
    existing_enable = (os.getenv("ROUTES_ENABLE") or "").strip()
    enable_parts = [p for p in existing_enable.replace(" ", ",").split(",") if p]
    if "audiobooks" not in [p.lower() for p in enable_parts]:
        enable_parts.append("audiobooks")
    monkeypatch.setenv("ROUTES_ENABLE", ",".join(enable_parts))

    fastapi_app = FastAPI()
    fastapi_app.include_router(audiobooks_router, prefix="/api/v1")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()


def test_export_subtitles_srt_sentence_mode(client_user_only):
    payload = {
        "format": "srt",
        "mode": "sentence",
        "variant": "wide",
        "alignment": {
            "engine": "kokoro",
            "sample_rate": 24000,
            "words": [
                {"word": "Hello", "start_ms": 0, "end_ms": 400},
                {"word": "world.", "start_ms": 450, "end_ms": 900},
            ],
        },
    }
    resp = _post_subtitles(client_user_only, payload)
    assert resp.status_code == 200
    text = resp.text
    assert "Hello world." in text
    assert "00:00:00,000 --> 00:00:00,900" in text
