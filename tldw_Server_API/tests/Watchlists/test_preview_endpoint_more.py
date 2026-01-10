from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=912, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_preview_more"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")

    from fastapi import FastAPI
    from tldw_Server_API.app.core.config import API_V1_PREFIX
    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_preview_empty_filters_has_ingestable_items(client_with_user: TestClient):
    c = client_with_user

    # Create an RSS source
    s = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Feed", "url": "https://example.com/rss.xml", "source_type": "rss"},
    )
    assert s.status_code == 200, s.text
    sid = s.json()["id"]

    # Create a job with empty filters payload
    j = c.post(
        "/api/v1/watchlists/jobs",
        json={"name": "No Filters", "scope": {"sources": [sid]}, "job_filters": {"filters": []}},
    )
    assert j.status_code == 200, j.text
    jid = j.json()["id"]

    r = c.post(f"/api/v1/watchlists/jobs/{jid}/preview", params={"limit": 5, "per_source": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    # With no filters, preview should show ingestable items (TEST_MODE stubs)
    assert data["total"] >= 1
    assert data["ingestable"] >= 1


def test_preview_invalid_regex_filter_is_safe_and_gates_when_required(client_with_user: TestClient):
    c = client_with_user

    # Create a site source
    s = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "Site",
            "url": "https://example.com/",
            "source_type": "site",
            "settings": {"scrape_rules": {"list_url": "https://example.com/list", "skip_article_fetch": True}},
        },
    )
    assert s.status_code == 200, s.text
    sid = s.json()["id"]

    # Job with an invalid regex include rule and require_include=true
    j = c.post(
        "/api/v1/watchlists/jobs",
        json={
            "name": "Invalid Regex Include",
            "scope": {"sources": [sid]},
            "job_filters": {
                "filters": [
                    {"type": "regex", "action": "include", "value": {"pattern": "[unclosed", "flags": "i"}}
                ],
                "require_include": True,
            },
        },
    )
    assert j.status_code == 200, j.text
    jid = j.json()["id"]

    # Preview should not error; with include-only gating, invalid regex won't match → all filtered
    r = c.post(f"/api/v1/watchlists/jobs/{jid}/preview", params={"limit": 5, "per_source": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 1
    assert data["ingestable"] == 0
    assert data["filtered"] >= 1
