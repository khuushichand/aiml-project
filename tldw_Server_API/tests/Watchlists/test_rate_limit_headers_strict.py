from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=913, username="wluser", email=None, is_active=True)

    # Avoid TEST_MODE so limiter can be enabled; we also patch the helper to force enable
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_rate_limits"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    # Ensure TEST_MODE not set
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.delenv("TLDW_TEST_MODE", raising=False)

    from fastapi import FastAPI
    from tldw_Server_API.app.core.config import API_V1_PREFIX
    from tldw_Server_API.app.api.v1.endpoints import watchlists as wl

    # Force-enable limits by patching the helper to False inside the module
    monkeypatch.setattr(wl, "_limits_disabled_now", lambda: False, raising=True)

    app = FastAPI()
    app.include_router(wl.router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _has_any_rate_headers(resp) -> bool:
    hdrs = resp.headers
    return any(
        h in hdrs
        for h in (
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        )
    )


def test_opml_import_emits_rate_limit_headers(client_with_user: TestClient):
    c = client_with_user
    # Build a minimal OPML body
    opml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<opml version=\"1.0\"><body>"
        "<outline text=\"Feed\" title=\"Feed\" type=\"rss\" xmlUrl=\"https://example.com/feed.xml\"/>"
        "</body></opml>"
    )
    files = {
        "file": ("feeds.opml", opml, "application/xml"),
        "active": (None, "1"),
    }
    r = c.post("/api/v1/watchlists/sources/import", files=files)
    assert r.status_code == 200, r.text
    assert _has_any_rate_headers(r)


def test_filters_patch_emits_rate_limit_headers(client_with_user: TestClient):
    c = client_with_user
    # Create a source + job
    s = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Feed", "url": "https://example.com/rss.xml", "source_type": "rss"},
    )
    assert s.status_code == 200, s.text
    j = c.post(
        "/api/v1/watchlists/jobs",
        json={"name": "Job", "scope": {"sources": [s.json()["id"]]}, "active": True},
    )
    assert j.status_code == 200, j.text
    # Patch filters
    r = c.patch(
        f"/api/v1/watchlists/jobs/{j.json()['id']}/filters",
        json={"filters": [{"type": "keyword", "action": "include", "value": {"keywords": ["a"], "match": "any"}}]},
    )
    assert r.status_code == 200, r.text
    assert _has_any_rate_headers(r)


def test_filters_add_emits_rate_limit_headers(client_with_user: TestClient):
    c = client_with_user
    # Create a source + job
    s = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Feed2", "url": "https://example.com/rss2.xml", "source_type": "rss"},
    )
    assert s.status_code == 200, s.text
    j = c.post(
        "/api/v1/watchlists/jobs",
        json={"name": "Job2", "scope": {"sources": [s.json()["id"]]}, "active": True},
    )
    assert j.status_code == 200, j.text
    # Add filter (append)
    r = c.post(
        f"/api/v1/watchlists/jobs/{j.json()['id']}/filters:add",
        json={"filters": [{"type": "regex", "action": "exclude", "value": {"pattern": "spam", "flags": "i"}}]},
    )
    assert r.status_code == 200, r.text
    assert _has_any_rate_headers(r)
