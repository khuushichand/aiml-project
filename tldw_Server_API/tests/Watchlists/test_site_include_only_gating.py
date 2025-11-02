from pathlib import Path
from importlib import import_module

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=908, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_site_include_only"
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


def test_site_include_only_gating(client_with_user):
    c = client_with_user

    # Create a site source with basic scrape_rules; TEST_MODE produces synthetic items
    s = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "Site Under Test",
            "url": "https://example.com/",
            "source_type": "site",
            "settings": {
                "scrape_rules": {"list_url": "https://example.com/list", "limit": 3, "skip_article_fetch": True}
            },
        },
    )
    assert s.status_code == 200, s.text
    src_id = s.json()["id"]

    # Job scoped to this source with an include rule that matches 'Test' in title
    j = c.post(
        "/api/v1/watchlists/jobs",
        json={
            "name": "Site Include Only",
            "scope": {"sources": [src_id]},
            "active": True,
            "job_filters": {
                "filters": [
                    {"type": "keyword", "action": "include", "value": {"keywords": ["Test"], "match": "any"}}
                ],
                "require_include": True,
            },
        },
    )
    assert j.status_code == 200, j.text
    job_id = j.json()["id"]

    # Trigger run and verify that include-only gating ingests the matching synthetic items
    r = c.post(f"/api/v1/watchlists/jobs/{job_id}/run")
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    detail = c.get(f"/api/v1/watchlists/runs/{rid}/details").json()
    stats = detail.get("stats", {})
    assert stats.get("items_found", 0) >= 1
    assert stats.get("filters_include", 0) >= 1
    assert stats.get("items_ingested", 0) >= 1

    # Now set an include rule that does NOT match and assert gating filters all
    r2 = c.patch(
        f"/api/v1/watchlists/jobs/{job_id}/filters",
        json={
            "filters": [
                {"type": "keyword", "action": "include", "value": {"keywords": ["NoMatch"], "match": "any"}}
            ],
            "require_include": True,
        },
    )
    assert r2.status_code == 200, r2.text

    r3 = c.post(f"/api/v1/watchlists/jobs/{job_id}/run")
    assert r3.status_code == 200, r3.text
    rid2 = r3.json()["id"]
    detail2 = c.get(f"/api/v1/watchlists/runs/{rid2}/details").json()
    stats2 = detail2.get("stats", {})
    assert stats2.get("items_found", 0) >= 1
    # With include-only gating and no include match, nothing ingested
    assert stats2.get("items_ingested", 0) == 0
    assert stats2.get("filters_include", 0) == 0
    # Filtered count should be >= found
    assert stats2.get("filters_exclude", 0) >= 0
