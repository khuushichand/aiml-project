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
    app.include_router(chat_router.conversations_alias_router, prefix="/api/v1/chats")
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


def test_conversation_alias_filters_character_scope(tmp_path):
    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    app = _build_app(db)

    char_id = db.add_character_card(
        {
            "name": "Character Scope",
            "description": "desc",
            "personality": "helpful",
            "system_prompt": "You are helpful.",
            "client_id": "user-1",
        }
    )
    db.add_conversation(
        {
            "id": "character-conv",
            "character_id": char_id,
            "title": "Quota review",
            "client_id": "user-1",
        }
    )
    db.add_conversation(
        {
            "id": "plain-conv",
            "character_id": None,
            "assistant_kind": "persona",
            "assistant_id": "plain-helper",
            "persona_memory_mode": "read_only",
            "title": "Quota review",
            "client_id": "user-1",
        }
    )

    resp = app.get(
        "/api/v1/chats/conversations",
        params={"query": "Quota", "character_scope": "non_character"},
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert [item["id"] for item in payload["items"]] == ["plain-conv"]
    assert payload["pagination"]["total"] == 1


def test_conversation_alias_rejects_incompatible_character_scope_and_character_id(tmp_path):
    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    app = _build_app(db)

    resp = app.get(
        "/api/v1/chats/conversations",
        params={"character_scope": "non_character", "character_id": 12},
    )

    assert resp.status_code == 400
    assert "character_scope" in resp.json()["detail"]


def test_conversation_alias_uses_paged_db_search(tmp_path, monkeypatch):
    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    app = _build_app(db)

    observed: dict[str, object] = {}
    now = datetime.now(timezone.utc)

    def fail_full_search(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("full search helper should not be used by the conversations endpoint")

    def fake_page_search(
        query: str | None,
        *,
        client_id: str | None = None,
        character_id: int | None = None,
        character_scope: str | None = None,
        state: str | None = None,
        topic_label: str | None = None,
        topic_prefix: bool = False,
        cluster_id: str | None = None,
        keywords: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        date_field: str = "last_modified",
        order_by: str = "recency",
        limit: int = 50,
        offset: int = 0,
        as_of: datetime | None = None,
        **kwargs,
    ):
        observed.update(
            {
                "query": query,
                "client_id": client_id,
                "character_id": character_id,
                "character_scope": character_scope,
                "order_by": order_by,
                "limit": limit,
                "offset": offset,
                "as_of": as_of,
                "date_field": date_field,
            }
        )
        return (
            [
                {
                    "id": "plain-conv",
                    "assistant_kind": "persona",
                    "assistant_id": "plain-helper",
                    "persona_memory_mode": "read_only",
                    "character_id": None,
                    "title": "Quota review",
                    "state": "in-progress",
                    "topic_label": None,
                    "bm25_norm": 0.42,
                    "last_modified": now.isoformat(),
                    "created_at": now.isoformat(),
                    "version": 3,
                    "cluster_id": None,
                    "source": None,
                    "external_ref": None,
                }
            ],
            7,
            0.91,
        )

    monkeypatch.setattr(db, "search_conversations", fail_full_search)
    monkeypatch.setattr(db, "search_conversations_page", fake_page_search, raising=False)

    resp = app.get(
        "/api/v1/chats/conversations",
        params={
            "query": "Quota",
            "character_scope": "non_character",
            "order_by": "hybrid",
            "limit": 1,
            "offset": 1,
        },
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["pagination"]["total"] == 7
    assert payload["pagination"]["limit"] == 1
    assert payload["pagination"]["offset"] == 1
    assert [item["id"] for item in payload["items"]] == ["plain-conv"]
    assert payload["items"][0]["bm25_norm"] == pytest.approx(0.42, rel=1e-6)
    assert observed["query"] == "Quota"
    assert observed["client_id"] == "user-1"
    assert observed["character_scope"] == "non_character"
    assert observed["order_by"] == "hybrid"
    assert observed["limit"] == 1
    assert observed["offset"] == 1
    assert observed["date_field"] == "last_modified"
    assert isinstance(observed["as_of"], datetime)


def test_conversation_alias_related_lookups_only_use_page_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    app = _build_app(db)

    now = datetime.now(timezone.utc)
    requested_ids: dict[str, list[str]] = {}

    def fail_full_search(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("full search helper should not be used by the conversations endpoint")

    def fake_page_search(*args, **kwargs):  # noqa: ANN002, ANN003
        return (
            [
                {
                    "id": "page-only",
                    "assistant_kind": "persona",
                    "assistant_id": "page-helper",
                    "persona_memory_mode": "read_only",
                    "character_id": None,
                    "title": "Quota review",
                    "state": "in-progress",
                    "topic_label": "quota",
                    "bm25_norm": 1.0,
                    "last_modified": now.isoformat(),
                    "created_at": now.isoformat(),
                    "version": 1,
                    "cluster_id": None,
                    "source": None,
                    "external_ref": None,
                }
            ],
            12,
            1.0,
        )

    def capture_keywords(conversation_ids: list[str]):
        requested_ids["keywords"] = list(conversation_ids)
        return {"page-only": [{"keyword": "quota"}]}

    def capture_message_counts(conversation_ids: list[str], include_deleted: bool = False):
        requested_ids["message_counts"] = list(conversation_ids)
        return {"page-only": 4}

    monkeypatch.setattr(db, "search_conversations", fail_full_search)
    monkeypatch.setattr(db, "search_conversations_page", fake_page_search, raising=False)
    monkeypatch.setattr(db, "get_keywords_for_conversations", capture_keywords)
    monkeypatch.setattr(db, "count_messages_for_conversations", capture_message_counts)

    resp = app.get(
        "/api/v1/chats/conversations",
        params={"query": "Quota", "limit": 1, "offset": 0},
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["items"][0]["keywords"] == ["quota"]
    assert payload["items"][0]["message_count"] == 4
    assert requested_ids["keywords"] == ["page-only"]
    assert requested_ids["message_counts"] == ["page-only"]
