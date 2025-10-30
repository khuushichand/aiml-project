import json
from importlib import import_module
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=777, username="ytuser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_youtube_url_helpers_import_and_behavior():
    mod = import_module("tldw_Server_API.app.api.v1.endpoints.watchlists")
    is_yt = getattr(mod, "_is_youtube_url")
    is_feed = getattr(mod, "_is_youtube_feed_url")

    assert is_yt("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True
    assert is_feed("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is False

    assert is_yt("https://youtu.be/dQw4w9WgXcQ") is True
    assert is_feed("https://youtu.be/dQw4w9WgXcQ") is False

    ch_feed = "https://www.youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw"
    assert is_yt(ch_feed) is True
    assert is_feed(ch_feed) is True

    pl_feed = "https://www.youtube.com/feeds/videos.xml?playlist_id=PL590L5WQmH8c9k2FYR3LyzAxylDWX2vHX"
    assert is_yt(pl_feed) is True
    assert is_feed(pl_feed) is True

    user_feed = "https://www.youtube.com/feeds/videos.xml?user=GoogleDevelopers"
    assert is_yt(user_feed) is True
    assert is_feed(user_feed) is True

    assert is_yt("https://example.com/feed.xml") is False
    assert is_feed("https://example.com/feed.xml") is False

    # m.youtube.com and no-www hosts
    assert is_yt("https://m.youtube.com/watch?v=dQw4w9WgXcQ") is True
    assert is_feed("https://m.youtube.com/watch?v=dQw4w9WgXcQ") is False
    assert is_yt("https://youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw") is True
    assert is_feed("https://youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw") is True

    # Mixed case canonical feed URL should still be accepted
    mixed = "HTTPS://WWW.YouTube.COM/FEEDS/VIDEOS.XML?CHANNEL_ID=UC_x5XG1OV2P6uZZ5FSM9Ttw"
    assert is_yt(mixed) is True
    assert is_feed(mixed) is True

    # youtu.be link with playlist list param is NOT a feed
    short_with_list = "https://youtu.be/dQw4w9WgXcQ?list=PL590L5WQmH8c9k2FYR3LyzAxylDWX2vHX"
    assert is_yt(short_with_list) is True
    assert is_feed(short_with_list) is False

    # Extra query params on canonical feed remain accepted
    feed_with_extra = "https://www.youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw&foo=bar"
    assert is_yt(feed_with_extra) is True
    assert is_feed(feed_with_extra) is True


def test_create_source_rejects_non_feed_youtube(client_with_user):
    c = client_with_user
    body = {
        "name": "YT Bad",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "source_type": "rss",
    }
    r = c.post("/api/v1/watchlists/sources", json=body)
    assert r.status_code == 400
    assert "invalid_youtube_rss_url" in r.text


def test_update_source_rejects_non_feed_youtube(client_with_user):
    c = client_with_user
    # Start with a valid non-YouTube RSS source
    create = {
        "name": "Valid Feed",
        "url": "https://example.com/feed.xml",
        "source_type": "rss",
    }
    r = c.post("/api/v1/watchlists/sources", json=create)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    # Attempt to change URL to a non-feed YouTube URL
    r = c.patch(
        f"/api/v1/watchlists/sources/{sid}",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert r.status_code == 400
    assert "invalid_youtube_rss_url" in r.text


def test_bulk_mixed_valid_and_invalid_reports_errors(client_with_user):
    c = client_with_user
    payload = {
        "sources": [
            {  # invalid: YouTube non-feed
                "name": "YT Bad",
                "url": "https://youtu.be/dQw4w9WgXcQ",
                "source_type": "rss",
            },
            {  # valid: YouTube channel feed
                "name": "YT Good",
                "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw",
                "source_type": "rss",
            },
            {  # valid: site
                "name": "Site A",
                "url": "https://a.example.com/",
                "source_type": "site",
            },
        ]
    }
    r = c.post("/api/v1/watchlists/sources/bulk", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 3
    assert data["created"] == 2
    assert data["errors"] == 1
    # Ensure one error entry mentions invalid_youtube_rss_url
    errs = [it for it in data["items"] if it["status"] == "error"]
    assert len(errs) == 1
    assert "invalid_youtube_rss_url" in (errs[0].get("error") or "")


def test_bulk_group_validation_errors(client_with_user):
    c = client_with_user
    # Use an obviously invalid group id
    invalid_gid = 987654321
    payload = {
        "sources": [
            {
                "name": "With Invalid Group",
                "url": "https://example.com/feed.xml",
                "source_type": "rss",
                "group_ids": [invalid_gid],
            }
        ]
    }
    r = c.post("/api/v1/watchlists/sources/bulk", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 1
    assert data["created"] == 0
    assert data["errors"] == 1
    assert data["items"][0]["status"] == "error"
    assert "group_not_found" in (data["items"][0].get("error") or "")


def test_bulk_tag_name_validation_errors(client_with_user):
    c = client_with_user
    payload = {
        "sources": [
            {
                "name": "Bad Tags",
                "url": "https://news.example.com/rss",
                "source_type": "rss",
                "tags": ["ok", "  ", ""],
            },
            {
                "name": "Good Tags",
                "url": "https://a.example.com/",
                "source_type": "site",
                "tags": ["alpha", "beta"],
            },
        ]
    }
    r = c.post("/api/v1/watchlists/sources/bulk", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 2
    assert data["created"] == 1
    assert data["errors"] == 1
    errs = [it for it in data["items"] if it["status"] == "error"]
    assert errs and "invalid_tag_names" in (errs[0].get("error") or "")
