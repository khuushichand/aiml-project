"""Tests for ACP Sessions SQLite persistence."""
import json
import os
import tempfile

import pytest

from tldw_Server_API.app.core.DB_Management.ACP_Sessions_DB import ACPSessionsDB


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "acp_sessions.db")
        instance = ACPSessionsDB(db_path=path)
        yield instance
        instance.close()


class TestSessionCRUD:
    def test_register_and_get_session(self, db):
        row = db.register_session(
            session_id="s1",
            user_id=1,
            agent_type="claude_code",
            name="Test Session",
            cwd="/tmp/work",
        )
        assert row is not None
        assert row["session_id"] == "s1"
        assert row["user_id"] == 1
        assert row["agent_type"] == "claude_code"
        assert row["name"] == "Test Session"
        assert row["status"] == "active"

        fetched = db.get_session("s1")
        assert fetched is not None
        assert fetched["session_id"] == "s1"

    def test_get_session_not_found(self, db):
        assert db.get_session("nonexistent") is None

    def test_close_session(self, db):
        db.register_session(session_id="s1", user_id=1)
        db.close_session("s1")
        rec = db.get_session("s1")
        assert rec["status"] == "closed"

    def test_list_sessions_filters(self, db):
        db.register_session(session_id="s1", user_id=1, agent_type="claude_code")
        db.register_session(session_id="s2", user_id=2, agent_type="codex")
        db.register_session(session_id="s3", user_id=1, agent_type="claude_code")
        db.close_session("s3")

        # Filter by user
        sessions, total = db.list_sessions(user_id=1)
        assert total == 2
        assert len(sessions) == 2

        # Filter by status
        sessions, total = db.list_sessions(user_id=1, status="active")
        assert total == 1
        assert sessions[0]["session_id"] == "s1"

    def test_register_session_with_tags_and_mcp(self, db):
        db.register_session(
            session_id="s1",
            user_id=1,
            tags=["workflow", "test"],
            mcp_servers=[{"name": "fs", "type": "stdio"}],
        )
        rec = db.get_session("s1")
        assert rec["tags"] == ["workflow", "test"]
        assert rec["mcp_servers"] == [{"name": "fs", "type": "stdio"}]

    def test_update_session_activity(self, db):
        db.register_session(session_id="s1", user_id=1)
        original = db.get_session("s1")
        db.update_activity("s1")
        updated = db.get_session("s1")
        # last_activity_at should be updated (or at least not None)
        assert updated["last_activity_at"] is not None

    def test_set_session_error(self, db):
        db.register_session(session_id="s1", user_id=1)
        db.set_session_status("s1", "error")
        rec = db.get_session("s1")
        assert rec["status"] == "error"

    def test_list_sessions_pagination(self, db):
        for i in range(10):
            db.register_session(session_id=f"s{i}", user_id=1)
        sessions, total = db.list_sessions(user_id=1, limit=3, offset=0)
        assert total == 10
        assert len(sessions) == 3
        sessions2, _ = db.list_sessions(user_id=1, limit=3, offset=3)
        assert len(sessions2) == 3
        # No overlap
        ids1 = {s["session_id"] for s in sessions}
        ids2 = {s["session_id"] for s in sessions2}
        assert ids1.isdisjoint(ids2)

    def test_delete_session(self, db):
        db.register_session(session_id="s1", user_id=1)
        assert db.delete_session("s1") is True
        assert db.get_session("s1") is None
        assert db.delete_session("s1") is False  # already deleted

    def test_register_defaults(self, db):
        """Verify default values for optional fields."""
        row = db.register_session(session_id="s1", user_id=1)
        assert row["agent_type"] == "custom"
        assert row["name"] == ""
        assert row["cwd"] == ""
        assert row["tags"] == []
        assert row["mcp_servers"] == []
        assert row["message_count"] == 0
        assert row["prompt_tokens"] == 0
        assert row["completion_tokens"] == 0
        assert row["total_tokens"] == 0
        assert row["bootstrap_ready"] is True
        assert row["needs_bootstrap"] is False
        assert row["forked_from"] is None
        assert row["persona_id"] is None
        assert row["workspace_id"] is None

    def test_boolean_fields_conversion(self, db):
        """Ensure integer booleans in SQLite are returned as Python bools."""
        db.register_session(session_id="s1", user_id=1)
        rec = db.get_session("s1")
        assert isinstance(rec["bootstrap_ready"], bool)
        assert isinstance(rec["needs_bootstrap"], bool)

    def test_list_sessions_filter_by_agent_type(self, db):
        db.register_session(session_id="s1", user_id=1, agent_type="claude_code")
        db.register_session(session_id="s2", user_id=1, agent_type="codex")
        sessions, total = db.list_sessions(agent_type="codex")
        assert total == 1
        assert sessions[0]["session_id"] == "s2"

    def test_created_at_is_populated(self, db):
        row = db.register_session(session_id="s1", user_id=1)
        assert row["created_at"] is not None
        assert len(row["created_at"]) > 0  # ISO timestamp string
