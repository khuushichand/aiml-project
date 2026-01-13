import importlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


@pytest.fixture()
def reading_app(monkeypatch):
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("ROUTES_ENABLE", "reading")

    base_dir = Path.cwd() / "Databases" / "test_reading_api"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    from tldw_Server_API.app import main as app_main

    importlib.reload(app_main)
    fastapi_app = app_main.app

    try:
        yield fastapi_app
    finally:
        fastapi_app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_reading_save_get_search_delete(reading_app):
    async def override_user():
        return User(id=333, username="reader", email=None, is_active=True)

    reading_app.dependency_overrides[get_request_user] = override_user

    with TestClient(reading_app) as client:
        payload = {
            "url": "https://example.org/read",
            "title": "Reading Item",
            "tags": ["alpha"],
            "status": "saved",
            "content": "Example content body for reading list.",
            "notes": "Example notes.",
        }
        r = client.post("/api/v1/reading/save", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        item_id = body["id"]
        assert body["processing_status"] == "ready"

        r = client.get(f"/api/v1/reading/items/{item_id}")
        assert r.status_code == 200, r.text
        detail = r.json()
        assert "Example content body" in (detail.get("text") or "")
        assert detail["processing_status"] == "ready"

        r = client.get("/api/v1/reading/items", params={"q": "Example"})
        assert r.status_code == 200, r.text
        listed_ids = [item["id"] for item in r.json()["items"]]
        assert item_id in listed_ids

        r = client.delete(f"/api/v1/reading/items/{item_id}")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "archived"

        r = client.delete(f"/api/v1/reading/items/{item_id}", params={"hard": "true"})
        assert r.status_code == 200, r.text
        assert r.json()["hard"] is True

        r = client.get(f"/api/v1/reading/items/{item_id}")
        assert r.status_code == 404


def test_reading_user_isolation(reading_app):
    async def user_one():
        return User(id=444, username="alpha", email=None, is_active=True)

    async def user_two():
        return User(id=445, username="beta", email=None, is_active=True)

    reading_app.dependency_overrides[get_request_user] = user_one
    with TestClient(reading_app) as client:
        payload = {
            "url": "https://example.org/isolation",
            "title": "Isolation Item",
            "content": "Isolation content",
        }
        r = client.post("/api/v1/reading/save", json=payload)
        assert r.status_code == 200, r.text
        item_id = r.json()["id"]

        reading_app.dependency_overrides[get_request_user] = user_two
        r = client.get("/api/v1/reading/items", params={"q": "Isolation"})
        assert r.status_code == 200, r.text
        assert not r.json()["items"]

        r = client.get(f"/api/v1/reading/items/{item_id}")
        assert r.status_code == 404, r.text


def test_reading_summarize_and_tts(reading_app, monkeypatch):
    async def override_user():
        return User(id=555, username="voice", email=None, is_active=True)

    def fake_analyze(*_args, **_kwargs):
        return "Mock summary output"

    class FakeTTSService:
        async def generate_speech(self, *_args, **_kwargs):
            yield b"audio"
            yield b"data"

    async def fake_get_tts_service():
        return FakeTTSService()

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.reading.summarize_analyze",
        fake_analyze,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.reading.get_tts_service_v2",
        fake_get_tts_service,
    )

    reading_app.dependency_overrides[get_request_user] = override_user

    with TestClient(reading_app) as client:
        payload = {
            "url": "https://example.org/tts",
            "title": "TTS Item",
            "content": "This is content for summary and TTS.",
        }
        r = client.post("/api/v1/reading/save", json=payload)
        assert r.status_code == 200, r.text
        item_id = r.json()["id"]

        r = client.post(
            f"/api/v1/reading/items/{item_id}/summarize",
            json={"provider": "openai"},
        )
        assert r.status_code == 200, r.text
        summary_body = r.json()
        assert summary_body["summary"] == "Mock summary output"
        assert summary_body["provider"] == "openai"
        assert summary_body["citations"][0]["item_id"] == item_id

        r = client.post(
            f"/api/v1/reading/items/{item_id}/tts",
            json={"stream": False},
        )
        assert r.status_code == 200, r.text
        assert r.content == b"audiodata"
