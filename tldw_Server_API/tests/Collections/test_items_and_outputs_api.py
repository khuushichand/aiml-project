import json
import os
import shutil
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from importlib import import_module, reload
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=123, username="tester", email=None, is_active=True)

    # Force per-user DB dir into project Databases/ for sandbox write allowance
    base_dir = Path.cwd() / "Databases" / "test_user_dbs"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    app = None
    try:
        # Import app after env vars to honor minimal test mode
        mod = import_module("tldw_Server_API.app.main")
        app = getattr(mod, "app")
        app.dependency_overrides[get_request_user] = override_user
        with TestClient(app) as client:
            yield client
    finally:
        if app is not None:
            app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_items_endpoint_minimal(client_with_user):
    client = client_with_user
    r = client.get("/api/v1/items", params={"ids": [1, 2]})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and isinstance(data["items"], list)


def test_items_endpoint_uses_collections_layer(client_with_user):
    client = client_with_user
    collections_db = CollectionsDatabase.for_user(user_id=123)
    collections_db.upsert_content_item(
        origin="watchlist",
        origin_type="rss",
        origin_id=1,
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        domain="example.com",
        title="Story Headline",
        summary="Summary text for story",
        content_hash=hashlib.sha256(b"Story Headline").hexdigest(),
        word_count=3,
        published_at="2024-01-01T00:00:00Z",
        tags=["news"],
        metadata={"test": True},
        media_id=456,
        job_id=99,
        run_id=100,
        source_id=200,
    )

    r = client.get("/api/v1/items", params={"page": 1, "size": 5, "origin": "watchlist", "q": "Story"})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["total"] >= 1
    assert any(item["title"] == "Story Headline" for item in payload["items"])
    assert all(item["type"] == "watchlist" for item in payload["items"])

    r = client.get("/api/v1/items", params={"origin": "reading"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_outputs_preview_with_inline_data_and_generate(client_with_user, tmp_path):
    client = client_with_user

    # Create a template
    payload = {
        "name": "inline-demo",
        "type": "newsletter_markdown",
        "format": "md",
        "body": "# Daily Brief\nTop: {{ items[0].title if items else 'none' }}\n",
        "description": "Inline demo",
        "is_default": False,
    }
    r = client.post("/api/v1/outputs/templates", json=payload)
    assert r.status_code == 200, r.text
    tpl = r.json()
    tid = tpl["id"]

    # Preview with inline data
    inline_ctx = {
        "items": [
            {
                "title": "Example Story",
                "url": "https://example.com/x",
                "domain": "example.com",
                "summary": "S",
                "published_at": "2024-01-01",
                "tags": ["a"],
            }
        ]
    }
    r = client.post(f"/api/v1/outputs/templates/{tid}/preview", json={"template_id": tid, "data": inline_ctx})
    assert r.status_code == 200, r.text
    prev = r.json()
    assert "Example Story" in prev["rendered"]

    # Generate output with the same inline data
    r = client.post("/api/v1/outputs", json={"template_id": tid, "data": inline_ctx, "title": "demo"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["format"] == "md"
    path = Path(out["storage_path"])  # type: ignore[arg-type]
    assert path.exists(), f"Output file missing at {path}"
    text = path.read_text(encoding="utf-8")
    assert "Example Story" in text

    # Get by id
    oid = out["id"]
    r = client.get(f"/api/v1/outputs/{oid}")
    assert r.status_code == 200
    meta = r.json()
    assert meta["id"] == oid

    # Download
    r = client.get(f"/api/v1/outputs/{oid}/download")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/markdown")
    r = client.head(f"/api/v1/outputs/{oid}/download")
    assert r.status_code == 200
    assert int(r.headers.get("content-length", "0")) > 0

    # List outputs
    r = client.get("/api/v1/outputs", params={"page": 1, "size": 10})
    assert r.status_code == 200
    lst = r.json()
    assert lst["total"] >= 1
    assert any(it["id"] == oid for it in lst.get("items", []))
