import json
import os
import shutil
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from importlib import import_module, reload
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.exceptions import InvalidStoragePathError
from tldw_Server_API.app.api.v1.endpoints.outputs import _resolve_output_path_for_user


pytestmark = pytest.mark.unit


def _insert_output_row_raw(
    cdb: CollectionsDatabase,
    *,
    title: str,
    format_: str,
    storage_path: str,
    retention_until: str | None = None,
) -> int:
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    res = cdb.backend.execute(
        "INSERT INTO outputs (user_id, job_id, run_id, type, title, format, storage_path, metadata_json, created_at, media_item_id, chatbook_path, deleted, deleted_at, retention_until) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)",
        (
            cdb.user_id,
            None,
            None,
            "newsletter_markdown",
            title,
            format_,
            storage_path,
            None,
            now,
            None,
            None,
            retention_until,
        ),
    )
    return int(res.lastrowid or 0)


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=123, username="tester", email=None, is_active=True)

    # Use full app profile for Collections/outputs endpoints
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")

    # Force per-user DB dir into project Databases/ for sandbox write allowance
    base_dir = Path.cwd() / "Databases" / "test_user_dbs"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    app = None
    try:
        # Reload app after env vars to honor minimal test mode changes
        mod = import_module("tldw_Server_API.app.main")
        mod = reload(mod)
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


def test_items_get_by_id(client_with_user):

    client = client_with_user
    r = client.post(
        "/api/v1/reading/save",
        json={
            "url": "https://example.com/article",
            "title": "Example Article",
            "content": "Inline article content used for tests.",
            "tags": ["demo"],
        },
    )
    assert r.status_code == 200, r.text
    item_id = r.json()["id"]

    r = client.get(f"/api/v1/items/{item_id}")
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["id"] == item_id
    assert item["title"] == "Example Article"


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
    path = _resolve_output_path_for_user(123, out["storage_path"])
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
    r = client.get("/api/v1/outputs/download/by-name", params={"title": "demo", "format": "md"})
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/markdown")

    # List outputs
    r = client.get("/api/v1/outputs", params={"page": 1, "size": 10})
    assert r.status_code == 200
    lst = r.json()
    assert lst["total"] >= 1
    assert any(it["id"] == oid for it in lst.get("items", []))


def test_outputs_generate_variants_and_ingest(client_with_user, monkeypatch):
    client = client_with_user

    class DummyTTS:
        async def generate_speech(self, req):  # noqa: ARG002 - signature used by TTS service
            yield b"FAKEAUDIO"

    async def _fake_get_tts_service_v2(*args, **kwargs):  # noqa: ARG002
        return DummyTTS()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_service_v2.get_tts_service_v2",
        _fake_get_tts_service_v2,
    )

    base_payload = {
        "name": "base-briefing",
        "type": "briefing_markdown",
        "format": "md",
        "body": "# Briefing\n{{ items|length }} items",
        "description": "Base output",
        "is_default": False,
    }
    r = client.post("/api/v1/outputs/templates", json=base_payload)
    assert r.status_code == 200, r.text
    base_id = r.json()["id"]

    mece_payload = {
        "name": "mece-default",
        "type": "mece_markdown",
        "format": "md",
        "body": "# MECE\n{% for item in items %}- {{ item.title }}\n{% endfor %}",
        "description": "MECE output",
        "is_default": True,
    }
    r = client.post("/api/v1/outputs/templates", json=mece_payload)
    assert r.status_code == 200, r.text

    tts_payload = {
        "name": "tts-default",
        "type": "tts_audio",
        "format": "mp3",
        "body": "Audio briefing for {{ items|length }} items.",
        "description": "TTS output",
        "is_default": True,
    }
    r = client.post("/api/v1/outputs/templates", json=tts_payload)
    assert r.status_code == 200, r.text

    inline_ctx = {
        "items": [
            {
                "title": "Story A",
                "url": "https://example.com/a",
                "domain": "example.com",
                "summary": "A",
                "published_at": "2024-01-01",
                "tags": ["tag-a"],
            }
        ]
    }

    r = client.post(
        "/api/v1/outputs",
        json={
            "template_id": base_id,
            "data": inline_ctx,
            "title": "Daily",
            "generate_mece": True,
            "generate_tts": True,
            "ingest_to_media_db": True,
        },
    )
    assert r.status_code == 200, r.text
    base = r.json()
    assert base["media_item_id"] is not None

    r = client.get("/api/v1/outputs", params={"type": "mece_markdown"})
    assert r.status_code == 200
    mece_outputs = r.json()["items"]
    assert any(item.get("media_item_id") for item in mece_outputs)

    r = client.get("/api/v1/outputs", params={"type": "tts_audio"})
    assert r.status_code == 200
    tts_outputs = r.json()["items"]
    assert any(item.get("media_item_id") for item in tts_outputs)


def test_outputs_create_sanitizes_title_and_enforces_base_dir(client_with_user):

    client = client_with_user

    payload = {
        "name": "path-safety",
        "type": "newsletter_markdown",
        "format": "md",
        "body": "Hello {{ items|length }}",
        "description": "Path safety",
        "is_default": False,
    }
    r = client.post("/api/v1/outputs/templates", json=payload)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    r = client.post("/api/v1/outputs", json={"template_id": tid, "data": {"items": []}, "title": "../outside"})
    assert r.status_code == 200, r.text
    out = r.json()
    out_path = _resolve_output_path_for_user(123, out["storage_path"])
    base_dir = DatabasePaths.get_user_base_directory(123) / "outputs"
    assert out_path.exists()
    assert out_path.resolve().is_relative_to(base_dir.resolve())


def test_outputs_download_rejects_storage_path_outside_base(client_with_user, tmp_path):

    client = client_with_user

    external = tmp_path / "outside.md"
    external.write_text("nope", encoding="utf-8")
    cdb = CollectionsDatabase.for_user(user_id=123)
    with pytest.raises(InvalidStoragePathError):
        cdb.create_output_artifact(
            type_="newsletter_markdown",
            title="outside",
            format_="md",
            storage_path=str(external),
            metadata_json=None,
        )
    row_id = _insert_output_row_raw(
        cdb,
        title="outside",
        format_="md",
        storage_path=str(external),
    )

    r = client.get(f"/api/v1/outputs/{row_id}/download")
    assert r.status_code == 400, r.text
    assert r.json().get("detail") == "invalid_path"


def test_outputs_download_normalizes_legacy_absolute_path(client_with_user):

    client = client_with_user

    base_dir = DatabasePaths.get_user_base_directory(123) / "outputs"
    base_dir.mkdir(parents=True, exist_ok=True)
    legacy_path = base_dir / "legacy.md"
    legacy_path.write_text("legacy", encoding="utf-8")
    cdb = CollectionsDatabase.for_user(user_id=123)
    row_id = _insert_output_row_raw(
        cdb,
        title="legacy",
        format_="md",
        storage_path=str(legacy_path),
    )

    r = client.get(f"/api/v1/outputs/{row_id}/download")
    assert r.status_code == 200, r.text
    row = cdb.get_output_artifact(row_id)
    assert row.storage_path == "legacy.md"


def test_outputs_delete_skips_invalid_path_file_removal(client_with_user, tmp_path):

    client = client_with_user

    external = tmp_path / "external.txt"
    external.write_text("keep", encoding="utf-8")
    cdb = CollectionsDatabase.for_user(user_id=123)
    with pytest.raises(InvalidStoragePathError):
        cdb.create_output_artifact(
            type_="newsletter_markdown",
            title="outside-delete",
            format_="md",
            storage_path=str(external),
            metadata_json=None,
        )
    row_id = _insert_output_row_raw(
        cdb,
        title="outside-delete",
        format_="md",
        storage_path=str(external),
    )

    r = client.delete(
        f"/api/v1/outputs/{row_id}",
        params={"hard": "true", "delete_file": "true"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["success"] is True
    assert payload["file_deleted"] is False
    assert external.exists()
    with pytest.raises(KeyError):
        cdb.get_output_artifact(row_id, include_deleted=True)


def test_outputs_purge_skips_invalid_path_delete_files(client_with_user, tmp_path):

    client = client_with_user

    external = tmp_path / "purge.txt"
    external.write_text("keep", encoding="utf-8")
    cdb = CollectionsDatabase.for_user(user_id=123)
    past = (datetime.utcnow() - timedelta(days=1)).replace(microsecond=0).isoformat()
    with pytest.raises(InvalidStoragePathError):
        cdb.create_output_artifact(
            type_="newsletter_markdown",
            title="outside-purge",
            format_="md",
            storage_path=str(external),
            metadata_json=None,
            retention_until=past,
        )
    row_id = _insert_output_row_raw(
        cdb,
        title="outside-purge",
        format_="md",
        storage_path=str(external),
        retention_until=past,
    )

    r = client.post("/api/v1/outputs/purge", json={"delete_files": True})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["removed"] == 1
    assert external.exists()
    with pytest.raises(KeyError):
        cdb.get_output_artifact(row_id, include_deleted=True)


def test_outputs_resolve_path_rejects_traversal(client_with_user):  # noqa: ARG001 - fixture sets up USER_DB_BASE_DIR
    user_id = 123
    with pytest.raises(HTTPException) as excinfo:
        _resolve_output_path_for_user(user_id, "../outside.txt")
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "invalid_path"
