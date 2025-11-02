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
        return User(id=780, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_opml_edges"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_opml_edge_cases(client_with_user):
    c = client_with_user

    # Duplicate URLs and htmlUrl-only outlines should be handled
    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<opml version=\"2.0\">\n"
        "  <head><title>Edges</title></head>\n"
        "  <body>\n"
        "    <outline text=\"A\" xmlUrl=\"https://dup.example.com/rss\" htmlUrl=\"https://dup.example.com\" />\n"
        "    <outline text=\"B\" xmlurl=\"https://dup.example.com/rss\" />\n"  # duplicate, case variation
        "    <outline text=\"C\" htmlUrl=\"https://htmlonly.example.com\" />\n"  # no xmlUrl → ignored by parser
        "    <outline text=\"D\" xmlUrl=\"https://uniq.example.com/rss\" />\n"
        "  </body>\n"
        "</opml>\n"
    )
    files = {"file": ("edges.opml", io.BytesIO(xml.encode("utf-8")), "application/xml")}
    r = c.post("/api/v1/watchlists/sources/import", files=files, data={"active": "1"})
    assert r.status_code == 200, r.text
    data = r.json()
    # dup.example.com/rss counted once; uniq.example.com/rss once; html-only skipped entirely
    assert data["created"] >= 2

    # Invalid OPML should skip gracefully
    bad = b"<notopml>garbage"
    files = {"file": ("bad.opml", io.BytesIO(bad), "application/xml")}
    r = c.post("/api/v1/watchlists/sources/import", files=files, data={"active": "1"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 0 and data["errors"] == 0  # parser yields no entries
