import io
import os
from importlib import import_module
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    # In tests, rate limits are disabled by design (PYTEST_CURRENT_TEST is set).
    # This fixture verifies the endpoint works; if headers are present, it checks structure.
    async def override_user():
        return User(id=905, username="tester", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_rate_limits"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_opml_import_rate_limit_headers_optional(client_with_user):
    c = client_with_user
    # Minimal OPML content
    opml = b"""<?xml version='1.0' encoding='UTF-8'?>\n<opml version='1.0'><body><outline text='Feed' title='Feed' type='rss' xmlUrl='https://example.com/feed.xml' /></body></opml>"""
    files = {"file": ("feeds.opml", io.BytesIO(opml), "application/xml")}
    r = c.post("/api/v1/watchlists/sources/import", files=files)
    assert r.status_code == 200, r.text
    # In test mode, optional limiter is disabled; headers may be absent.
    # If present, ensure the values are parseable integers.
    for hdr in ("X-RateLimit-Limit", "X-RateLimit-Remaining"):
        if hdr in r.headers:
            try:
                int(r.headers[hdr])
            except Exception:
                pytest.fail(f"Header {hdr} not an int: {r.headers[hdr]}")
