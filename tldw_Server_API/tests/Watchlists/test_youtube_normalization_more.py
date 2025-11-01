import os
from importlib import import_module, reload
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=777, username="ytuser", email=None, is_active=True)

    # Route user DB base dir into project Databases to avoid permission issues
    base_dir = Path.cwd() / "Databases" / "test_user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")
    # Ensure full app loads watchlists endpoints (avoid minimal gating)
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")

    # Ensure a clean per-user DB for user 777 (default path used by settings)
    try:
        default_user_db = Path.cwd() / "Databases" / "user_databases" / "777" / "Media_DB_v2.db"
        if default_user_db.exists():
            default_user_db.unlink()
    except Exception:
        pass

    # Build a minimal app including only the Watchlists router to avoid heavy imports
    from fastapi import FastAPI
    from tldw_Server_API.app.core.config import API_V1_PREFIX
    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_create_source_normalizes_channel_and_sets_headers(client_with_user: TestClient):
    c = client_with_user
    body = {
        "name": "YT Channel",
        "url": "https://www.youtube.com/channel/UC1234567890abcdef",
        "source_type": "rss",
    }
    r = c.post("/api/v1/watchlists/sources", json=body)
    assert r.status_code == 200, r.text
    # Server should set normalization headers when it transforms the URL
    assert r.headers.get("X-YouTube-Normalized") == "1"
    canonical = r.headers.get("X-YouTube-Canonical-URL")
    assert canonical and canonical.startswith("https://www.youtube.com/feeds/videos.xml?channel_id=")
    data = r.json()
    assert data["url"] == canonical


def test_update_source_normalizes_playlist(client_with_user: TestClient):
    c = client_with_user
    # Create baseline site source
    src = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Temp", "url": "https://example.com/", "source_type": "site"},
    ).json()
    # Update to RSS with playlist URL (non-canonical input)
    r = c.patch(
        f"/api/v1/watchlists/sources/{src['id']}",
        json={"source_type": "rss", "url": "https://www.youtube.com/playlist?list=PL123XYZ"},
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("X-YouTube-Normalized") == "1"
    canonical = r.headers.get("X-YouTube-Canonical-URL")
    assert canonical and canonical.startswith("https://www.youtube.com/feeds/videos.xml?playlist_id=")
    assert r.json()["url"] == canonical


def test_bulk_normalizes_per_entry_and_returns_canonical_url(client_with_user: TestClient):
    c = client_with_user
    payload = {
        "sources": [
            {"name": "YT Play", "url": "https://www.youtube.com/playlist?list=PL999", "source_type": "rss"},
            {"name": "YT Chan", "url": "https://www.youtube.com/channel/UCzzzz", "source_type": "rss"},
        ]
    }
    r = c.post("/api/v1/watchlists/sources/bulk", json=payload)
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    assert len(items) == 2
    urls = {it["name"]: it.get("url") for it in items}
    assert urls["YT Play"].startswith("https://www.youtube.com/feeds/videos.xml?playlist_id=")
    assert urls["YT Chan"].startswith("https://www.youtube.com/feeds/videos.xml?channel_id=")


def test_bulk_normalizes_uppercase_and_extra_params(client_with_user: TestClient):
    c = client_with_user
    payload = {
        "sources": [
            {
                "name": "Play Extra",
                "url": "HTTPS://WWW.YOUTUBE.COM/PLAYLIST?LIST=PL999&feature=youtu.be",
                "source_type": "rss",
            },
            {
                "name": "Chan Upper",
                "url": "HTTPS://WWW.YOUTUBE.COM/CHANNEL/UCzzzz",
                "source_type": "rss",
            },
        ]
    }
    r = c.post("/api/v1/watchlists/sources/bulk", json=payload)
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    # Bulk response should include normalized URLs; per-entry headers are not present in bulk
    urls = {it.get("name"): it.get("url") for it in items}
    assert urls["Play Extra"] == "https://www.youtube.com/feeds/videos.xml?playlist_id=PL999"
    assert urls["Chan Upper"] == "https://www.youtube.com/feeds/videos.xml?channel_id=UCzzzz"


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://www.youtube.com/@somehandle",
        "https://www.youtube.com/c/SomeVanity",
        "https://youtu.be/abc123",
        "https://www.youtube.com/watch?v=abc123",
        "https://www.youtube.com/shorts/abc123",
    ],
)
def test_unsupported_youtube_inputs_return_400(client_with_user: TestClient, bad_url: str):
    c = client_with_user
    r = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "BadYT", "url": bad_url, "source_type": "rss"},
    )
    assert r.status_code == 400
    assert "invalid_youtube_rss_url" in r.text


def test_create_normalizes_uppercase_host_and_extra_params(client_with_user: TestClient):
    c = client_with_user
    # Uppercase host and playlist path with extra unrelated params should still normalize
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "YT Upper",
            "url": "HTTPS://WWW.YOUTUBE.COM/PLAYLIST?LIST=PLABCDEF&feature=youtu.be",
            "source_type": "rss",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("X-YouTube-Normalized") == "1"
    canonical = r.headers.get("X-YouTube-Canonical-URL")
    assert canonical == "https://www.youtube.com/feeds/videos.xml?playlist_id=PLABCDEF"
    assert r.json()["url"] == canonical

    # Channel path with uppercase should normalize too
    r2 = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "YT Upper Ch",
            "url": "HTTPS://WWW.YOUTUBE.COM/CHANNEL/UCZZZZ",
            "source_type": "rss",
        },
    )
    assert r2.status_code == 200, r2.text
    assert r2.headers.get("X-YouTube-Normalized") == "1"
    canonical2 = r2.headers.get("X-YouTube-Canonical-URL")
    assert canonical2 == "https://www.youtube.com/feeds/videos.xml?channel_id=UCZZZZ"
    assert r2.json()["url"] == canonical2


def test_channel_with_trailing_and_videos_path_normalizes(client_with_user: TestClient):
    c = client_with_user
    # Trailing slash
    r1 = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "YT Ch Slash",
            "url": "https://www.youtube.com/channel/UCZZZZ/",
            "source_type": "rss",
        },
    )
    assert r1.status_code == 200, r1.text
    assert r1.headers.get("X-YouTube-Normalized") == "1"
    assert r1.headers.get("X-YouTube-Canonical-URL") == "https://www.youtube.com/feeds/videos.xml?channel_id=UCZZZZ"

    # Extra path /videos should still normalize to channel feed
    r2 = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "YT Ch Videos",
            "url": "https://www.youtube.com/channel/UCABCD/videos",
            "source_type": "rss",
        },
    )
    assert r2.status_code == 200, r2.text
    assert r2.headers.get("X-YouTube-Normalized") == "1"
    assert r2.headers.get("X-YouTube-Canonical-URL") == "https://www.youtube.com/feeds/videos.xml?channel_id=UCABCD"


def test_channel_with_playlist_query_wins_over_channel(client_with_user: TestClient):
    c = client_with_user
    # Channel path plus LIST query should produce playlist canonical
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "YT Ch+List",
            "url": "https://www.youtube.com/channel/UC12345?LIST=PLHELLO",
            "source_type": "rss",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("X-YouTube-Normalized") == "1"
    assert r.headers.get("X-YouTube-Canonical-URL") == "https://www.youtube.com/feeds/videos.xml?playlist_id=PLHELLO"


def test_user_url_normalization_sets_user_feed_and_headers(client_with_user: TestClient):
    c = client_with_user
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "YT User",
            "url": "https://www.youtube.com/user/SomeUser",
            "source_type": "rss",
        },
    )
    assert r.status_code == 200, r.text
    # Normalization headers present
    assert r.headers.get("X-YouTube-Normalized") == "1"
    canonical = r.headers.get("X-YouTube-Canonical-URL")
    assert canonical == "https://www.youtube.com/feeds/videos.xml?user=SomeUser"
    assert r.json()["url"] == canonical


def test_playlist_param_takes_precedence_over_user_path(client_with_user: TestClient):
    c = client_with_user
    # Even with a /user path, a playlist query param should prefer playlist canonicalization
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "YT User+List",
            "url": "https://www.youtube.com/user/SomeUser?list=PLXYZ123",
            "source_type": "rss",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("X-YouTube-Normalized") == "1"
    canonical = r.headers.get("X-YouTube-Canonical-URL")
    assert canonical == "https://www.youtube.com/feeds/videos.xml?playlist_id=PLXYZ123"
    assert r.json()["url"] == canonical


def test_user_uppercase_path_and_extra_params_normalizes(client_with_user: TestClient):
    c = client_with_user
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "YT User Upper",
            "url": "https://WWW.YOUTUBE.COM/USER/SomeUser?view=all",
            "source_type": "rss",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("X-YouTube-Normalized") == "1"
    assert r.headers.get("X-YouTube-Canonical-URL") == "https://www.youtube.com/feeds/videos.xml?user=SomeUser"


def test_channel_uppercase_videos_with_query_normalizes(client_with_user: TestClient):
    c = client_with_user
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "YT Ch Upper Videos",
            "url": "HTTPS://WWW.YOUTUBE.COM/CHANNEL/UCXYZZ/videos/?foo=bar",
            "source_type": "rss",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("X-YouTube-Normalized") == "1"
    assert r.headers.get("X-YouTube-Canonical-URL") == "https://www.youtube.com/feeds/videos.xml?channel_id=UCXYZZ"


def test_channel_http_no_www_normalizes_to_https(client_with_user: TestClient):
    c = client_with_user
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "YT No WWW",
            "url": "http://youtube.com/channel/UC123NO",
            "source_type": "rss",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("X-YouTube-Normalized") == "1"
    assert r.headers.get("X-YouTube-Canonical-URL") == "https://www.youtube.com/feeds/videos.xml?channel_id=UC123NO"
