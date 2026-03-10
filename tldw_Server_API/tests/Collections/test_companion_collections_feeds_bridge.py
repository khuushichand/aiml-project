import importlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit

TEST_USER_ID = 811


@pytest.fixture()
def collections_feeds_app_with_companion(monkeypatch):
    async def override_user():
        return User(id=TEST_USER_ID, username="feeds-companion", email=None, is_active=True)

    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("ROUTES_ENABLE", "collections-feeds")
    monkeypatch.setenv("TEST_MODE", "1")

    base_dir = Path.cwd() / "Databases" / "test_companion_collections_feeds_bridge"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    from tldw_Server_API.app import main as app_main
    from tldw_Server_API.app.api.v1.endpoints import collections_feeds

    importlib.reload(app_main)
    fastapi_app = app_main.app
    fastapi_app.dependency_overrides[get_request_user] = override_user
    monkeypatch.setattr(collections_feeds, "_register_schedule", lambda *args, **kwargs: None)

    personalization_db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(TEST_USER_ID)))
    personalization_db.update_profile(str(TEST_USER_ID), enabled=1)

    try:
        yield fastapi_app, personalization_db
    finally:
        fastapi_app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_active_collections_feed_creation_records_first_run_companion_activity(
    collections_feeds_app_with_companion,
):
    app, personalization_db = collections_feeds_app_with_companion

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/collections/feeds",
            json={
                "url": "https://example.com/feed.xml",
                "name": "Companion Feed",
                "tags": ["research", "feeds"],
                "active": True,
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    job_id = int(payload["job_id"])

    events, total = personalization_db.list_companion_activity_events(str(TEST_USER_ID), limit=20)
    assert total >= 1

    item_events = [
        event
        for event in events
        if event["event_type"] == "watchlist_item_added"
        and event["metadata"]["job_id"] == job_id
    ]
    assert item_events

    event = item_events[0]
    assert event["source_type"] == "watchlist_item"
    assert event["surface"] == "api.watchlists"
    assert event["provenance"]["route"] == "/api/v1/collections/feeds"
    assert event["provenance"]["action"] == "item_ingested"
    assert event["metadata"]["status"] == "ingested"


def test_collections_feed_lifecycle_records_companion_source_events(
    collections_feeds_app_with_companion,
):
    app, personalization_db = collections_feeds_app_with_companion

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/collections/feeds",
            json={
                "url": "https://example.com/lifecycle.xml",
                "name": "Lifecycle Feed",
                "tags": ["research", "feeds"],
                "active": False,
            },
        )
        assert create_response.status_code == 200, create_response.text
        feed = create_response.json()
        feed_id = int(feed["id"])

        update_response = client.patch(
            f"/api/v1/collections/feeds/{feed_id}",
            json={
                "name": "Lifecycle Feed Updated",
                "tags": ["research", "priority"],
                "settings": {"rss": {"use_feed_content_if_available": True}},
            },
        )
        assert update_response.status_code == 200, update_response.text
        updated = update_response.json()

        delete_response = client.delete(f"/api/v1/collections/feeds/{feed_id}")
        assert delete_response.status_code == 200, delete_response.text

    events, total = personalization_db.list_companion_activity_events(str(TEST_USER_ID), limit=20)
    assert total >= 3

    source_events = [
        event
        for event in events
        if event["source_id"] == str(feed_id)
        and event["event_type"] in {
            "watchlist_source_created",
            "watchlist_source_updated",
            "watchlist_source_deleted",
        }
    ]
    assert len(source_events) == 3
    event_types = [event["event_type"] for event in source_events]
    assert event_types == [
        "watchlist_source_deleted",
        "watchlist_source_updated",
        "watchlist_source_created",
    ]

    deleted_event = source_events[0]
    assert deleted_event["surface"] == "api.collections"
    assert deleted_event["provenance"]["route"] == f"/api/v1/collections/feeds/{feed_id}"
    assert deleted_event["metadata"]["deleted"] is True
    assert deleted_event["metadata"]["hard_delete"] is True

    updated_event = source_events[1]
    assert updated_event["surface"] == "api.collections"
    assert updated_event["provenance"]["route"] == f"/api/v1/collections/feeds/{feed_id}"
    assert updated_event["metadata"]["name"] == updated["name"]
    assert updated_event["metadata"]["active"] is False
    assert updated_event["tags"] == ["research", "priority"]
    assert updated_event["metadata"]["changed_fields"] == ["name", "settings", "tags"]

    created_event = source_events[2]
    assert created_event["surface"] == "api.collections"
    assert created_event["provenance"]["route"] == "/api/v1/collections/feeds"
    assert created_event["tags"] == ["research", "feeds"]
    assert created_event["metadata"]["name"] == "Lifecycle Feed"
    assert created_event["metadata"]["active"] is False
