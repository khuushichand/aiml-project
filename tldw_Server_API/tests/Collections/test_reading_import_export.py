import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Collections.reading_importers import (
    parse_instapaper_export,
    parse_pocket_export,
)
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


def test_parse_pocket_export():
    payload = {
        "list": {
            "1": {
                "resolved_url": "https://example.com/story",
                "resolved_title": "Example Story",
                "tags": {"research": {}, "ai": {}},
                "status": "0",
                "favorite": "1",
                "time_added": "1700000000",
                "excerpt": "Pocket note",
            }
        }
    }
    items = parse_pocket_export(json.dumps(payload).encode("utf-8"))
    assert len(items) == 1
    item = items[0]
    assert item.url == "https://example.com/story"
    assert item.title == "Example Story"
    assert set(item.tags) == {"ai", "research"}
    assert item.status == "saved"
    assert item.favorite is True
    assert item.notes == "Pocket note"


def test_parse_instapaper_export():
    csv_payload = "URL,Title,Tags,Folder,Notes\nhttps://example.com/a,Example A,tag1;tag2,Archive,Note A\n"
    items = parse_instapaper_export(csv_payload.encode("utf-8"))
    assert len(items) == 1
    item = items[0]
    assert item.url == "https://example.com/a"
    assert item.title == "Example A"
    assert set(item.tags) == {"tag1", "tag2"}
    assert item.status == "archived"
    assert item.notes == "Note A"


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=222, username="reader", email=None, is_active=True)

    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ROUTES_ENABLE", "reading")

    base_dir = Path.cwd() / "Databases" / "test_reading_import"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    from tldw_Server_API.app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_request_user] = override_user
    try:
        with TestClient(fastapi_app) as client:
            yield client
    finally:
        fastapi_app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_reading_import_and_export(client_with_user):
    client = client_with_user
    payload = {
        "list": {
            "1": {
                "resolved_url": "https://example.com/story",
                "resolved_title": "Example Story",
                "tags": {"research": {}, "ai": {}},
                "status": "0",
                "favorite": "1",
                "excerpt": "Pocket note",
            }
        }
    }
    files = {
        "file": ("pocket.json", json.dumps(payload).encode("utf-8"), "application/json"),
    }
    data = {"source": "pocket", "merge_tags": "true"}
    r = client.post("/api/v1/reading/import", files=files, data=data)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 1

    r = client.get("/api/v1/reading/items")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    assert items[0]["title"] == "Example Story"

    r = client.get("/api/v1/reading/export", params={"format": "jsonl"})
    assert r.status_code == 200
    lines = [line for line in r.text.splitlines() if line]
    assert lines
    exported = json.loads(lines[0])
    assert exported["title"] == "Example Story"
    assert "notes" in exported
