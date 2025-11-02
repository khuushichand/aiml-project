import io
from pathlib import Path
from importlib import import_module

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=778, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_opml"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _opml_sample() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<opml version=\"2.0\">\n"
        "  <head><title>Test</title></head>\n"
        "  <body>\n"
        "    <outline text=\"Feed One\" title=\"Feed One\" xmlUrl=\"https://feed1.example.com/rss\" />\n"
        "    <outline text=\"Feed Two\" title=\"Feed Two\" xmlUrl=\"https://feed2.example.com/rss\" />\n"
        "  </body>\n"
        "</opml>\n"
    )


def test_opml_import_export_endpoints(client_with_user):
    c = client_with_user

    # Import OPML
    xml = _opml_sample()
    files = {"file": ("feeds.opml", io.BytesIO(xml.encode("utf-8")), "application/xml")}
    r = c.post("/api/v1/watchlists/sources/import", files=files, data={"active": "1"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] >= 2

    # Export OPML
    r = c.get("/api/v1/watchlists/sources/export")
    assert r.status_code == 200, r.text
    assert "<opml" in r.text
    assert "https://feed1.example.com/rss" in r.text
    assert "https://feed2.example.com/rss" in r.text
