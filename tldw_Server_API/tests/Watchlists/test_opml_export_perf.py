from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=919, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_opml_export_perf"
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


def test_opml_export_performance_sanity_large_set(client_with_user: TestClient):
    c = client_with_user
    # Create a few hundred RSS sources (no tags/groups)
    n = 300
    for i in range(n):
        r = c.post(
            "/api/v1/watchlists/sources",
            json={
                "name": f"Perf{i}",
                "url": f"https://example.com/perf{i}.xml",
                "source_type": "rss",
            },
        )
        assert r.status_code == 200, r.text

    # Export all (rss-only)
    r = c.get("/api/v1/watchlists/sources/export", params={"type": "rss"})
    assert r.status_code == 200, r.text
    urls = _extract_opml_urls(r.text)
    # At least N RSS feeds appear (allow duplicates or pre-existing filters to reduce slightly)
    assert len([u for u in urls if u.startswith("https://example.com/perf")]) >= n
