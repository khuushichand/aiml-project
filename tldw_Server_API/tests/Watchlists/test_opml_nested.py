import io
from importlib import import_module
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=779, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_opml_nested"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _nested_opml() -> str:
    # Mixed-case attributes and nested outlines
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<opml version=\"2.0\">\n"
        "  <head><title>Nested</title></head>\n"
        "  <body>\n"
        "    <outline text=\"Tech\">\n"
        "      <outline TEXT=\"Inner One\" TITLE=\"Inner One\" xmlurl=\"https://one.example.com/rss\" htmlUrl=\"https://one.example.com\" />\n"
        "      <outline text=\"Inner Two\" title=\"Inner Two\" xmlUrl=\"https://two.example.com/rss\" />\n"
        "    </outline>\n"
        "    <outline text=\"Top Level\" xmlUrl=\"https://top.example.com/rss\" />\n"
        "  </body>\n"
        "</opml>\n"
    )


def test_opml_nested_and_case_variations(client_with_user):
    c = client_with_user
    xml = _nested_opml()
    files = {"file": ("nested.opml", io.BytesIO(xml.encode("utf-8")), "application/xml")}
    r = c.post("/api/v1/watchlists/sources/import", files=files, data={"active": "1"})
    assert r.status_code == 200, r.text
    data = r.json()
    # Expect 3 unique feeds created
    assert data["created"] >= 3
