"""Tests for workspace CRUD endpoints and scoped chat session isolation."""
import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    ConflictError,
)


@pytest.fixture
def db(tmp_path):
    d = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    d.add_character_card({"name": "Test Char"})
    return d


class TestWorkspaceLifecycle:
    def test_upsert_then_get(self, db):
        ws = db.upsert_workspace("ws-1", "My Workspace")
        assert ws["id"] == "ws-1"
        fetched = db.get_workspace("ws-1")
        assert fetched["name"] == "My Workspace"

    def test_patch_workspace_name(self, db):
        db.upsert_workspace("ws-1", "Old")
        ws = db.update_workspace("ws-1", {"name": "New"}, expected_version=1)
        assert ws["name"] == "New"
        assert ws["version"] == 2

    def test_archive_workspace(self, db):
        db.upsert_workspace("ws-1", "WS")
        ws = db.update_workspace("ws-1", {"archived": True}, expected_version=1)
        assert ws["archived"] in (True, 1)

    def test_delete_workspace_cascade(self, db):
        db.upsert_workspace("ws-1", "WS")
        conv_id = db.add_conversation({
            "title": "WS chat", "character_id": 1,
            "scope_type": "workspace", "workspace_id": "ws-1",
        })
        db.delete_workspace("ws-1", expected_version=1)

        # Workspace is soft-deleted
        ws = db.get_workspace("ws-1")
        assert ws is None  # get_workspace excludes deleted

        # Conversation is also soft-deleted
        conv = db.get_conversation_by_id(conv_id)
        assert conv is None

    def test_list_workspaces(self, db):
        for i in range(5):
            db.upsert_workspace(f"ws-{i}", f"WS {i}")
        result = db.list_workspaces()
        assert len(result) == 5

    def test_version_conflict_returns_error(self, db):
        db.upsert_workspace("ws-1", "WS")
        db.update_workspace("ws-1", {"name": "V2"}, expected_version=1)
        with pytest.raises((ConflictError, Exception)):
            db.update_workspace("ws-1", {"name": "V3"}, expected_version=1)


class TestScopedChatSessions:
    def test_workspace_chat_not_visible_in_global_list(self, db):
        db.upsert_workspace("ws-1", "WS")
        db.add_conversation({"title": "Global", "character_id": 1})
        db.add_conversation({
            "title": "WS Chat", "character_id": 1,
            "scope_type": "workspace", "workspace_id": "ws-1",
        })
        global_results = db.search_conversations(None, scope_type="global")
        assert all(r["scope_type"] == "global" for r in global_results)

    def test_global_chat_not_visible_in_workspace_list(self, db):
        db.upsert_workspace("ws-1", "WS")
        db.add_conversation({"title": "Global", "character_id": 1})
        ws_results = db.search_conversations(None, scope_type="workspace", workspace_id="ws-1")
        assert len(ws_results) == 0
