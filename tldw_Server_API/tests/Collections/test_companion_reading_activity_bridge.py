import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints import reading as reading_ep
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit

TEST_USER_ID = 222

fastapi_app = FastAPI()
fastapi_app.include_router(reading_ep.router, prefix="/api/v1")


@pytest.fixture()
def client_with_companion_opt_in(monkeypatch):
    async def override_user():
        return User(id=TEST_USER_ID, username="reader", email=None, is_active=True)

    monkeypatch.setenv("TEST_MODE", "1")

    base_dir = Path.cwd() / "Databases" / "test_companion_reading_bridge"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    personalization_db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(TEST_USER_ID)))
    personalization_db.update_profile(str(TEST_USER_ID), enabled=1)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    try:
        with TestClient(fastapi_app) as client:
            yield client, personalization_db
    finally:
        fastapi_app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_reading_actions_record_companion_activity(client_with_companion_opt_in):
    client, personalization_db = client_with_companion_opt_in

    save_resp = client.post(
        "/api/v1/reading/save",
        json={
            "url": "https://example.com/article",
            "title": "Example Article",
            "content": "Example article body.",
            "tags": ["ai", "priority"],
        },
    )
    assert save_resp.status_code == 200, save_resp.text
    item = save_resp.json()
    item_id = item["id"]

    duplicate_save_resp = client.post(
        "/api/v1/reading/save",
        json={
            "url": "https://example.com/article",
            "title": "Example Article",
            "content": "Example article body.",
            "tags": ["ai"],
        },
    )
    assert duplicate_save_resp.status_code == 200, duplicate_save_resp.text

    update_resp = client.patch(
        f"/api/v1/reading/items/{item_id}",
        json={"status": "read", "favorite": True, "notes": "Finished"},
    )
    assert update_resp.status_code == 200, update_resp.text

    archive_resp = client.delete(f"/api/v1/reading/items/{item_id}")
    assert archive_resp.status_code == 200, archive_resp.text
    assert archive_resp.json()["hard"] is False

    events, total = personalization_db.list_companion_activity_events(str(TEST_USER_ID), limit=10)
    assert total == 3

    event_types = [event["event_type"] for event in events]
    assert event_types == [
        "reading_item_archived",
        "reading_item_updated",
        "reading_item_saved",
    ]

    saved_event = events[2]
    assert saved_event["source_type"] == "reading_item"
    assert saved_event["source_id"] == str(item_id)
    assert saved_event["surface"] == "api.reading"
    assert saved_event["tags"] == ["ai", "priority"]
    assert saved_event["provenance"]["capture_mode"] == "explicit"
    assert saved_event["provenance"]["route"] == "/api/v1/reading/save"
    assert saved_event["metadata"]["url"] == "https://example.com/article"
    assert saved_event["metadata"]["title"] == "Example Article"

    archived_event = events[0]
    assert archived_event["metadata"]["hard_delete"] is False
    assert archived_event["provenance"]["route"] == f"/api/v1/reading/items/{item_id}"
