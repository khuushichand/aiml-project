from importlib import import_module
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=907, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_opml_export_group_more"
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


def _extract_opml_urls(xml_text: str) -> list[str]:
    urls = []
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_text)
        for outline in root.findall('.//outline'):
            url = outline.attrib.get('xmlUrl') or outline.attrib.get('xmlurl')
            if url:
                urls.append(url)
    except Exception:
        pass
    return urls


def test_opml_export_multi_group_or_and_tag_and_unknown_group(client_with_user):
    c = client_with_user

    # Create three groups
    g1 = c.post("/api/v1/watchlists/groups", json={"name": "Group1"}).json()
    g2 = c.post("/api/v1/watchlists/groups", json={"name": "Group2"}).json()
    g3 = c.post("/api/v1/watchlists/groups", json={"name": "Group3"}).json()

    # Create RSS sources spread across groups and tags
    s1 = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Feed1", "url": "https://example.com/1.xml", "source_type": "rss", "group_ids": [g1["id"]], "tags": ["keep"]},
    )
    assert s1.status_code == 200
    s2 = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Feed2", "url": "https://example.com/2.xml", "source_type": "rss", "group_ids": [g2["id"]]},
    )
    assert s2.status_code == 200
    s3 = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Feed3", "url": "https://example.com/3.xml", "source_type": "rss", "group_ids": [g3["id"]], "tags": ["keep"]},
    )
    assert s3.status_code == 200

    # Multi-group OR: g1 OR g2 should include Feed1 and Feed2, not Feed3
    r = c.get("/api/v1/watchlists/sources/export", params={"group": [g1["id"], g2["id"]]})
    assert r.status_code == 200, r.text
    urls = _extract_opml_urls(r.text)
    assert "https://example.com/1.xml" in urls
    assert "https://example.com/2.xml" in urls
    assert "https://example.com/3.xml" not in urls

    # Multi-group OR combined with tag AND (keep): should include Feed1 (g1) but not Feed2; exclude Feed3 because g3 not in OR filter
    r = c.get("/api/v1/watchlists/sources/export", params={"group": [g1["id"], g2["id"]], "tag": ["keep"]})
    assert r.status_code == 200, r.text
    urls = _extract_opml_urls(r.text)
    assert "https://example.com/1.xml" in urls
    assert "https://example.com/2.xml" not in urls
    assert "https://example.com/3.xml" not in urls

    # Unknown group id should return empty when used alone
    r = c.get("/api/v1/watchlists/sources/export", params={"group": [999999]})
    assert r.status_code == 200, r.text
    urls = _extract_opml_urls(r.text)
    assert "https://example.com/1.xml" not in urls
    assert "https://example.com/2.xml" not in urls
    assert "https://example.com/3.xml" not in urls


def test_opml_export_tag_case_insensitivity_and_large_set(client_with_user):
    c = client_with_user

    # Create a tag in mixed case via sources
    keep_names = ["Keep", "keep", "KEEP"]
    created_urls = []
    for i, tag in enumerate(keep_names, start=1):
        r = c.post(
            "/api/v1/watchlists/sources",
            json={
                "name": f"FeedK{i}",
                "url": f"https://example.com/k{i}.xml",
                "source_type": "rss",
                "tags": [tag],
            },
        )
        assert r.status_code == 200, r.text
        created_urls.append(f"https://example.com/k{i}.xml")

    # Create a larger set to sanity check performance
    for i in range(1, 61):
        r = c.post(
            "/api/v1/watchlists/sources",
            json={
                "name": f"Feed{i}",
                "url": f"https://example.com/bulk{i}.xml",
                "source_type": "rss",
            },
        )
        assert r.status_code == 200, r.text

    # Export by tag=keep should include all three variants
    r = c.get("/api/v1/watchlists/sources/export", params={"tag": ["keep"]})
    assert r.status_code == 200, r.text
    urls = _extract_opml_urls(r.text)
    for u in created_urls:
        assert u in urls
    # Ensure the large set did not break the response (at least those three exist)
    assert len(urls) >= 3
