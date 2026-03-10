from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


@pytest.fixture()
def watchlists_app(monkeypatch, tmp_path):
    base_dir = tmp_path / "test_companion_watchlists"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")

    app = FastAPI()
    app.include_router(watchlists_router, prefix="/api/v1")

    async def override_user():
        return User(id=906, username="wluser", email=None, is_active=True)

    app.dependency_overrides[get_request_user] = override_user

    personalization_db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(906)))
    personalization_db.update_profile("906", enabled=1)

    try:
        yield app, personalization_db
    finally:
        app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_watchlist_source_creation_records_companion_event(watchlists_app):
    app, personalization_db = watchlists_app

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/watchlists/sources",
            json={
                "name": "Security Feed",
                "url": "https://example.com/security.xml",
                "source_type": "rss",
                "tags": ["security", "feeds"],
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()

    events, total = personalization_db.list_companion_activity_events("906", limit=10)
    assert total == 1
    event = events[0]
    assert event["event_type"] == "watchlist_source_created"
    assert event["source_type"] == "watchlist_source"
    assert event["source_id"] == str(payload["id"])
    assert event["surface"] == "api.watchlists"
    assert event["tags"] == ["security", "feeds"]
    assert event["provenance"]["route"] == "/api/v1/watchlists/sources"
    assert event["metadata"]["name"] == "Security Feed"
