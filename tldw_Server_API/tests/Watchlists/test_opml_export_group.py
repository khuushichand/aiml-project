import io
from importlib import import_module, reload
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=906, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_opml_export_group"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")

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


def test_opml_export_filters_by_group(client_with_user):
    c = client_with_user

    # Create two groups
    g1 = c.post("/api/v1/watchlists/groups", json={"name": "GroupA"}).json()
    g2 = c.post("/api/v1/watchlists/groups", json={"name": "GroupB"}).json()

    # Create RSS sources in different groups
    s1 = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "FeedA1", "url": "https://example.com/a1.xml", "source_type": "rss", "group_ids": [g1["id"]]},
    )
    assert s1.status_code == 200
    s2 = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "FeedA2", "url": "https://example.com/a2.xml", "source_type": "rss", "group_ids": [g1["id"]]},
    )
    assert s2.status_code == 200
    s3 = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "FeedB1", "url": "https://example.com/b1.xml", "source_type": "rss", "group_ids": [g2["id"]]},
    )
    assert s3.status_code == 200

    # Export for GroupA only
    r = c.get(f"/api/v1/watchlists/sources/export", params={"group": [g1["id"]]})
    assert r.status_code == 200, r.text
    urls = _extract_opml_urls(r.text)
    assert "https://example.com/a1.xml" in urls
    assert "https://example.com/a2.xml" in urls
    assert "https://example.com/b1.xml" not in urls

    # Export for GroupB only
    r = c.get(f"/api/v1/watchlists/sources/export", params={"group": [g2["id"]]})
    assert r.status_code == 200, r.text
    urls = _extract_opml_urls(r.text)
    assert "https://example.com/b1.xml" in urls
    assert "https://example.com/a1.xml" not in urls

    # Export for GroupA + tag filtering (AND)
    # Tag one source and request tag filter
    c.patch(f"/api/v1/watchlists/sources/{s1.json()['id']}", json={"tags": ["keep"]})
    r = c.get(f"/api/v1/watchlists/sources/export", params={"group": [g1["id"]], "tag": ["keep"]})
    assert r.status_code == 200, r.text
    urls = _extract_opml_urls(r.text)
    assert "https://example.com/a1.xml" in urls
    assert "https://example.com/a2.xml" not in urls
