import importlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


@pytest.fixture()
def feeds_app(monkeypatch):
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("ROUTES_ENABLE", "collections-feeds")

    base_dir = Path.cwd() / "Databases" / "test_collections_feeds_api"
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


def test_collections_feeds_create_list_delete(feeds_app):
    async def override_user():
        return User(id=808, username="feeds", email=None, is_active=True)

    feeds_app.dependency_overrides[get_request_user] = override_user

    with TestClient(feeds_app) as client:
        payload = {
            "url": "https://example.com/feed.xml",
            "name": "Example Feed",
            "tags": ["news"],
        }
        r = client.post("/api/v1/collections/feeds", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        feed_id = body["id"]
        job_id = body.get("job_id")
        assert body["origin"] == "feed"
        assert body["schedule_expr"] == "0 * * * *"
        assert job_id is not None

        r = client.get("/api/v1/collections/feeds")
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert any(item["id"] == feed_id for item in items)

        r = client.get(f"/api/v1/collections/feeds/{feed_id}")
        assert r.status_code == 200, r.text

        db = WatchlistsDatabase.for_user(user_id=808)
        source = db.get_source(feed_id)
        settings_json = json.loads(source.settings_json or "{}")
        assert settings_json.get("collections_origin") == "feed"
        assert int(settings_json.get("collections_feed_job_id")) == int(job_id)
        job = db.get_job(int(job_id))
        output_prefs = json.loads(job.output_prefs_json or "{}")
        schedule_cfg = output_prefs.get("collections_schedule")
        assert isinstance(schedule_cfg, dict)
        assert schedule_cfg.get("mode") == "hourly_then_daily"

        r = client.delete(f"/api/v1/collections/feeds/{feed_id}")
        assert r.status_code == 200, r.text

        r = client.get("/api/v1/collections/feeds")
        assert r.status_code == 200, r.text
        assert r.json()["items"] == []


def test_collections_feeds_update(feeds_app):
    async def override_user():
        return User(id=809, username="feeds", email=None, is_active=True)

    feeds_app.dependency_overrides[get_request_user] = override_user

    with TestClient(feeds_app) as client:
        payload = {
            "url": "https://example.com/feed.xml",
            "name": "Example Feed",
            "tags": ["news"],
        }
        r = client.post("/api/v1/collections/feeds", json=payload)
        assert r.status_code == 200, r.text
        feed_id = r.json()["id"]

        patch = {
            "name": "Renamed Feed",
            "tags": ["alpha", "beta"],
            "schedule_expr": "0 0 * * *",
            "timezone": "UTC",
            "active": False,
            "settings": {"rss": {"use_feed_content_if_available": True}},
        }
        r = client.patch(f"/api/v1/collections/feeds/{feed_id}", json=patch)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == "Renamed Feed"
        assert sorted(body["tags"]) == ["alpha", "beta"]
        assert body["schedule_expr"] == "0 0 * * *"
        assert body["timezone"] == "UTC"
        assert body["job_active"] is False
        assert body.get("settings", {}).get("rss", {}).get("use_feed_content_if_available") is True
