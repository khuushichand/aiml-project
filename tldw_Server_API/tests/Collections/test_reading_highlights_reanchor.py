import importlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Collections.utils import hash_text_sha256
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


@pytest.fixture()
def reading_app(monkeypatch):
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")

    base_dir = Path.cwd() / "Databases" / "test_reading_highlights_reanchor"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    from tldw_Server_API.app import main as app_main

    importlib.reload(app_main)
    fastapi_app = app_main.app

    try:
        yield fastapi_app
    finally:
        fastapi_app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_highlight_reanchoring_on_content_change(reading_app):
    async def override_user():
        return User(id=777, username="anchor", email=None, is_active=True)

    reading_app.dependency_overrides[get_request_user] = override_user

    with TestClient(reading_app) as client:
        content_v1 = "Alpha intro. Important sentence lives here. Omega."
        r = client.post(
            "/api/v1/reading/save",
            json={
                "url": "https://example.org/anchor",
                "title": "Anchor Item",
                "content": content_v1,
            },
        )
        assert r.status_code == 200, r.text
        item_id = r.json()["id"]

        r = client.post(
            f"/api/v1/reading/items/{item_id}/highlight",
            json={
                "item_id": item_id,
                "quote": "Important sentence",
                "anchor_strategy": "fuzzy_quote",
            },
        )
        assert r.status_code == 200, r.text
        highlight = r.json()
        assert highlight["state"] == "active"
        assert highlight["start_offset"] == content_v1.index("Important sentence")
        assert highlight["content_hash_ref"] == hash_text_sha256(content_v1)

        content_v2 = "Intro. Important sentence appears earlier now."
        r = client.post(
            "/api/v1/reading/save",
            json={
                "url": "https://example.org/anchor",
                "title": "Anchor Item",
                "content": content_v2,
            },
        )
        assert r.status_code == 200, r.text

        r = client.get(f"/api/v1/reading/items/{item_id}/highlights")
        assert r.status_code == 200, r.text
        highlight = r.json()[0]
        assert highlight["state"] == "active"
        assert highlight["start_offset"] == content_v2.index("Important sentence")
        assert highlight["content_hash_ref"] == hash_text_sha256(content_v2)

        content_v3 = "No match remains."
        r = client.post(
            "/api/v1/reading/save",
            json={
                "url": "https://example.org/anchor",
                "title": "Anchor Item",
                "content": content_v3,
            },
        )
        assert r.status_code == 200, r.text

        r = client.get(f"/api/v1/reading/items/{item_id}/highlights")
        assert r.status_code == 200, r.text
        highlight = r.json()[0]
        assert highlight["state"] == "stale"
