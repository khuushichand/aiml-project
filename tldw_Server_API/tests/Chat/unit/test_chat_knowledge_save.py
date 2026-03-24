import os
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


def test_knowledge_save_creates_note_with_backlinks(tmp_path):


    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    app = _build_app(db)

    conv_id = db.add_conversation(
        {"id": "conv-1", "root_id": "conv-1", "character_id": 1, "title": "Test Conv", "client_id": "user-1"}
    )
    msg_id = db.add_message({"conversation_id": conv_id, "sender": "user", "content": "hello"})

    payload = {
        "conversation_id": conv_id,
        "message_id": msg_id,
        "snippet": "important snippet",
        "tags": ["alpha", "beta"],
        "make_flashcard": False,
        "export_to": "none",
    }

    resp = app.post("/api/v1/chat/knowledge/save", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    note_id = data["note_id"]
    note = db.get_note_by_id(note_id)
    assert note is not None
    assert note.get("conversation_id") == conv_id
    assert note.get("message_id") == msg_id
    keywords = db.get_keywords_for_note(note_id)
    keyword_texts = sorted([k.get("keyword") for k in keywords])
    assert keyword_texts == ["alpha", "beta"]


def test_knowledge_save_export_guard(tmp_path, monkeypatch):


    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    app = _build_app(db)

    conv_id = db.add_conversation(
        {"id": "conv-2", "root_id": "conv-2", "character_id": 1, "title": "Test Conv", "client_id": "user-1"}
    )

    payload = {
        "conversation_id": conv_id,
        "snippet": "another snippet",
        "tags": None,
        "make_flashcard": False,
        "export_to": "notion",
    }

    # Ensure flag is off
    monkeypatch.delenv("CHAT_CONNECTORS_V2_ENABLED", raising=False)
    resp = app.post("/api/v1/chat/knowledge/save", json=payload)
    assert resp.status_code == 201
    assert resp.json().get("export_status") == "skipped_disabled"

    # Enable and ensure it passes
    monkeypatch.setenv("CHAT_CONNECTORS_V2_ENABLED", "true")
    resp_ok = app.post("/api/v1/chat/knowledge/save", json=payload)
    assert resp_ok.status_code == 201


def test_knowledge_save_requires_exact_scope_match_for_workspace_conversations(tmp_path):
    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    app = _build_app(db)

    db.upsert_workspace("ws-1", "Workspace One")
    conv_id = db.add_conversation(
        {
            "id": "workspace-conv-1",
            "root_id": "workspace-conv-1",
            "character_id": 1,
            "title": "Workspace Conv",
            "client_id": "user-1",
            "scope_type": "workspace",
            "workspace_id": "ws-1",
        }
    )
    msg_id = db.add_message({"conversation_id": conv_id, "sender": "assistant", "content": "scoped"})

    base_payload = {
        "conversation_id": conv_id,
        "message_id": msg_id,
        "snippet": "workspace snippet",
        "make_flashcard": False,
        "export_to": "none",
    }

    missing_scope = app.post("/api/v1/chat/knowledge/save", json=base_payload)
    assert missing_scope.status_code == 404, missing_scope.text

    wrong_scope = app.post(
        "/api/v1/chat/knowledge/save",
        json={**base_payload, "scope_type": "workspace", "workspace_id": "ws-2"},
    )
    assert wrong_scope.status_code == 404, wrong_scope.text

    correct_scope = app.post(
        "/api/v1/chat/knowledge/save",
        json={**base_payload, "scope_type": "workspace", "workspace_id": "ws-1"},
    )
    assert correct_scope.status_code == 201, correct_scope.text
