from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = [pytest.mark.integration, pytest.mark.performance]


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=921, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_opml_export_perf_more"
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


def test_opml_export_perf_sanity_beyond_300(client_with_user: TestClient):
    c = client_with_user
    # Create >300 RSS sources
    n = 600
    for i in range(n):
        r = c.post(
            "/api/v1/watchlists/sources",
            json={
                "name": f"PerfMore{i}",
                "url": f"https://example.com/perfmore{i}.xml",
                "source_type": "rss",
            },
        )
        assert r.status_code == 200, r.text

    # Export all RSS
    r = c.get("/api/v1/watchlists/sources/export", params={"type": "rss"})
    assert r.status_code == 200, r.text
    urls = _extract_opml_urls(r.text)
    # Ensure at least N RSS feeds are present
    assert len([u for u in urls if u.startswith("https://example.com/perfmore")]) >= n


@pytest.mark.performance
def test_opml_export_perf_sanity_beyond_800(client_with_user: TestClient):
    c = client_with_user
    # Create >800 RSS sources to stress export path
    n = 800
    for i in range(n):
        r = c.post(
            "/api/v1/watchlists/sources",
            json={
                "name": f"PerfMoreB{i}",
                "url": f"https://example.com/perfmoreB{i}.xml",
                "source_type": "rss",
            },
        )
        assert r.status_code == 200, r.text

    r = c.get("/api/v1/watchlists/sources/export", params={"type": "rss"})
    assert r.status_code == 200, r.text
    urls = _extract_opml_urls(r.text)
    assert len([u for u in urls if u.startswith("https://example.com/perfmoreB")]) >= n
