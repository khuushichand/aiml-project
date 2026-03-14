"""Tests for workspace registry and conversation scope columns (Stage 1)."""
import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    ConflictError,
    InputError,
)


pytestmark = pytest.mark.unit


@pytest.fixture()
def db(tmp_path):
    """Create a fresh in-memory-like CharactersRAGDB with a character card."""
    db_path = tmp_path / "chacha_scope.db"
    instance = CharactersRAGDB(db_path=str(db_path), client_id="test-client")
    # Seed a character so conversations have a valid FK target
    instance.add_character_card({"name": "ScopeTestChar"})
    return instance


# ── workspace upsert ───────────────────────────────────────────────────────


class TestWorkspaceUpsert:
    def test_upsert_creates_workspace(self, db):
        ws = db.upsert_workspace("ws-1", "My Workspace")
        assert ws["id"] == "ws-1"
        assert ws["name"] == "My Workspace"
        assert ws["version"] == 1
        assert ws["deleted"] in (0, False)

    def test_upsert_is_idempotent(self, db):
        db.upsert_workspace("ws-1", "My Workspace")
        ws = db.upsert_workspace("ws-1", "My Workspace")
        assert ws["version"] == 1  # unchanged

    def test_get_workspace(self, db):
        db.upsert_workspace("ws-1", "My Workspace")
        ws = db.get_workspace("ws-1")
        assert ws is not None
        assert ws["name"] == "My Workspace"

    def test_get_missing_workspace_returns_none(self, db):
        assert db.get_workspace("nonexistent") is None

    def test_list_excludes_deleted(self, db):
        db.upsert_workspace("ws-1", "WS1")
        db.upsert_workspace("ws-2", "WS2")
        db.delete_workspace("ws-2", expected_version=1)
        workspaces = db.list_workspaces()
        assert len(workspaces) == 1
        assert workspaces[0]["id"] == "ws-1"


# ── conversation scope ─────────────────────────────────────────────────────


class TestConversationScope:
    def test_default_global_scope(self, db):
        conv_id = db.add_conversation(
            {"character_id": 1, "title": "Global chat"}
        )
        conv = db.get_conversation_by_id(conv_id)
        assert conv["scope_type"] == "global"
        assert conv["workspace_id"] is None

    def test_workspace_scope(self, db):
        db.upsert_workspace("ws-1", "WS1")
        conv_id = db.add_conversation(
            {
                "character_id": 1,
                "title": "Scoped chat",
                "scope_type": "workspace",
                "workspace_id": "ws-1",
            }
        )
        conv = db.get_conversation_by_id(conv_id)
        assert conv["scope_type"] == "workspace"
        assert conv["workspace_id"] == "ws-1"

    def test_workspace_scope_without_id_raises(self, db):
        with pytest.raises(InputError):
            db.add_conversation(
                {
                    "character_id": 1,
                    "title": "Bad",
                    "scope_type": "workspace",
                }
            )

    def test_search_respects_scope(self, db):
        db.upsert_workspace("ws-1", "WS1")
        db.add_conversation({"character_id": 1, "title": "Global"})
        db.add_conversation(
            {
                "character_id": 1,
                "title": "Scoped",
                "scope_type": "workspace",
                "workspace_id": "ws-1",
            }
        )
        global_results = db.search_conversations(None, scope_type="global")
        ws_results = db.search_conversations(
            None, scope_type="workspace", workspace_id="ws-1"
        )
        assert len(global_results) == 1
        assert global_results[0]["scope_type"] == "global"
        assert len(ws_results) == 1
        assert ws_results[0]["workspace_id"] == "ws-1"


# ── workspace delete cascade ──────────────────────────────────────────────


class TestWorkspaceDeleteCascade:
    def test_delete_soft_deletes_conversations(self, db):
        db.upsert_workspace("ws-1", "WS1")
        conv_id = db.add_conversation(
            {
                "character_id": 1,
                "title": "Scoped",
                "scope_type": "workspace",
                "workspace_id": "ws-1",
            }
        )
        db.delete_workspace("ws-1", expected_version=1)
        conv = db.get_conversation_by_id(conv_id)
        assert conv is None  # soft-deleted, so invisible

    def test_delete_doesnt_affect_global(self, db):
        db.upsert_workspace("ws-1", "WS1")
        global_id = db.add_conversation(
            {"character_id": 1, "title": "Global"}
        )
        db.delete_workspace("ws-1", expected_version=1)
        conv = db.get_conversation_by_id(global_id)
        assert conv is not None


# ── workspace optimistic locking ───────────────────────────────────────────


class TestWorkspaceOptimisticLocking:
    def test_stale_version_raises(self, db):
        db.upsert_workspace("ws-1", "WS1")
        with pytest.raises(ConflictError):
            db.update_workspace("ws-1", {"name": "Renamed"}, expected_version=99)

    def test_correct_version_succeeds(self, db):
        db.upsert_workspace("ws-1", "WS1")
        ws = db.update_workspace("ws-1", {"name": "Renamed"}, expected_version=1)
        assert ws["name"] == "Renamed"
        assert ws["version"] == 2
