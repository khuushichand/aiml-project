from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints import chat as chat_router
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit


def _build_app(db: CharactersRAGDB) -> TestClient:
    app = FastAPI()
    app.include_router(chat_router.router, prefix="/api/v1/chat")
    app.dependency_overrides[get_chacha_db_for_user] = lambda: db
    app.dependency_overrides[get_request_user] = lambda: SimpleNamespace(id="user-1")
    return TestClient(app)


def test_conversation_list_bm25_and_keywords(tmp_path):
    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    app = _build_app(db)

    char_id = db.add_character_card(
        {
            "name": "Test Character",
            "description": "desc",
            "personality": "helpful",
            "system_prompt": "You are helpful.",
            "client_id": "user-1",
        }
    )
    conv1 = db.add_conversation(
        {
            "character_id": char_id,
            "title": "alpha alpha alpha",
            "client_id": "user-1",
        }
    )
    conv2 = db.add_conversation(
        {
            "character_id": char_id,
            "title": "alpha beta",
            "client_id": "user-1",
        }
    )
    kw_id = db.add_keyword("triage")
    db.link_conversation_to_keyword(conv1, kw_id)

    resp = app.get("/api/v1/chat/conversations", params={"query": "alpha", "order_by": "bm25"})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["pagination"]["total"] >= 2
    items = payload["items"]
    assert items[0]["id"] == conv1
    assert items[0]["bm25_norm"] == pytest.approx(1.0, rel=1e-6)
    assert "triage" in items[0]["keywords"]


def test_chat_analytics_buckets(tmp_path):
    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    app = _build_app(db)

    char_id = db.add_character_card(
        {
            "name": "Test Character",
            "description": "desc",
            "personality": "helpful",
            "system_prompt": "You are helpful.",
            "client_id": "user-1",
        }
    )
    db.add_conversation(
        {
            "character_id": char_id,
            "title": "Analytics A",
            "state": "in-progress",
            "client_id": "user-1",
        }
    )
    db.add_conversation(
        {
            "character_id": char_id,
            "title": "Analytics B",
            "state": "resolved",
            "client_id": "user-1",
        }
    )

    today = datetime.now(timezone.utc).date()
    start_date = (today - timedelta(days=1)).isoformat()
    end_date = (today + timedelta(days=1)).isoformat()

    resp = app.get(
        "/api/v1/chat/analytics",
        params={"start_date": start_date, "end_date": end_date, "bucket_granularity": "day"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["pagination"]["total"] >= 1
    assert data["bucket_granularity"] == "day"


def test_conversation_endpoints_expose_normalized_assistant_identity(tmp_path):
    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    app = _build_app(db)

    conversation_id = db.add_conversation(
        {
            "assistant_kind": "persona",
            "assistant_id": "garden-helper",
            "persona_memory_mode": "read_only",
            "title": "Persona conversation",
            "client_id": "user-1",
        }
    )
    assert conversation_id is not None

    list_resp = app.get("/api/v1/chat/conversations")
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()["items"]
    item = next(entry for entry in items if entry["id"] == conversation_id)
    assert item["assistant_kind"] == "persona"
    assert item["assistant_id"] == "garden-helper"
    assert item["character_id"] is None
    assert item["persona_memory_mode"] == "read_only"

    conversation = db.get_conversation_by_id(conversation_id)
    assert conversation is not None

    patch_resp = app.patch(
        f"/api/v1/chat/conversations/{conversation_id}",
        json={
            "version": conversation["version"],
            "source": "api",
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    patched = patch_resp.json()
    assert patched["assistant_kind"] == "persona"
    assert patched["assistant_id"] == "garden-helper"
    assert patched["character_id"] is None
    assert patched["persona_memory_mode"] == "read_only"

    tree_resp = app.get(f"/api/v1/chat/conversations/{conversation_id}/tree")
    assert tree_resp.status_code == 200, tree_resp.text
    metadata = tree_resp.json()["conversation"]
    assert metadata["assistant_kind"] == "persona"
    assert metadata["assistant_id"] == "garden-helper"
    assert metadata["character_id"] is None
