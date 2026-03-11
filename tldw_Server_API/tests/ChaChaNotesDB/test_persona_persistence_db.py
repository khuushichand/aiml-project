import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return a temporary SQLite path for persona persistence database tests."""
    return tmp_path / "persona_persistence_test.sqlite"


@pytest.fixture
def db_instance(db_path: Path) -> Iterator[CharactersRAGDB]:
    """Provide a CharactersRAGDB instance and close it after each test."""
    db = CharactersRAGDB(db_path, "persona-persistence-test-client")
    yield db
    db.close_connection()


def test_migration_v25_to_latest_creates_persona_tables(db_path: Path):
    db = CharactersRAGDB(db_path, "seed-client")
    db.close_connection()

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "UPDATE db_schema_version SET version = ? WHERE schema_name = ?",
            (25, CharactersRAGDB._SCHEMA_NAME),
        )
        conn.execute("DROP TABLE IF EXISTS persona_memory_entries")
        conn.execute("DROP TABLE IF EXISTS persona_sessions")
        conn.execute("DROP TABLE IF EXISTS persona_policy_rules")
        conn.execute("DROP TABLE IF EXISTS persona_scope_rules")
        conn.execute("DROP TABLE IF EXISTS persona_profiles")
        conn.commit()

    migrated = CharactersRAGDB(db_path, "migration-check-client")
    conn = migrated.get_connection()

    version = conn.execute(
        "SELECT version FROM db_schema_version WHERE schema_name = ?",
        (CharactersRAGDB._SCHEMA_NAME,),
    ).fetchone()["version"]
    assert version == CharactersRAGDB._CURRENT_SCHEMA_VERSION

    for table_name in (
        "persona_profiles",
        "persona_scope_rules",
        "persona_policy_rules",
        "persona_sessions",
        "persona_memory_entries",
    ):
        found = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        assert found is not None

    profile_indexes = {row["name"] for row in conn.execute("PRAGMA index_list('persona_profiles')").fetchall()}
    assert "idx_persona_profiles_user_active" in profile_indexes
    profile_columns = {row["name"] for row in conn.execute("PRAGMA table_info('persona_profiles')").fetchall()}
    assert "use_persona_state_context_default" in profile_columns
    memory_columns = {row["name"] for row in conn.execute("PRAGMA table_info('persona_memory_entries')").fetchall()}
    assert "scope_snapshot_id" in memory_columns
    assert "session_id" in memory_columns
    session_columns = {row["name"] for row in conn.execute("PRAGMA table_info('persona_sessions')").fetchall()}
    assert "activity_surface" in session_columns
    assert "preferences_json" in session_columns
    memory_indexes = {row["name"] for row in conn.execute("PRAGMA index_list('persona_memory_entries')").fetchall()}
    assert "idx_persona_memory_scope" in memory_indexes
    assert "idx_persona_memory_session" in memory_indexes

    migrated.close_connection()


def test_persona_persistence_crud_and_user_scoping(db_instance: CharactersRAGDB):
    persona_id = db_instance.create_persona_profile(
        {
            "user_id": "user-1",
            "name": "Research Persona",
            "mode": "session_scoped",
            "system_prompt": "You are a focused assistant.",
            "character_card_id": 1,
            "is_active": True,
        }
    )
    assert isinstance(persona_id, str)

    profile = db_instance.get_persona_profile(persona_id, user_id="user-1")
    assert profile is not None
    assert profile["name"] == "Research Persona"
    assert profile["mode"] == "session_scoped"
    assert profile["is_active"] is True
    assert profile["use_persona_state_context_default"] is True
    expected_version = int(profile["version"])

    assert db_instance.update_persona_profile(
        persona_id=persona_id,
        user_id="user-1",
        update_data={
            "mode": "persistent_scoped",
            "is_active": True,
            "use_persona_state_context_default": False,
        },
        expected_version=expected_version,
    )
    updated_profile = db_instance.get_persona_profile(persona_id, user_id="user-1")
    assert updated_profile is not None
    assert updated_profile["mode"] == "persistent_scoped"
    assert updated_profile["use_persona_state_context_default"] is False

    inserted_scope_count = db_instance.replace_persona_scope_rules(
        persona_id=persona_id,
        user_id="user-1",
        rules=[
            {"rule_type": "conversation_id", "rule_value": "conv-a", "include": True},
            {"rule_type": "media_tag", "rule_value": "physics", "include": True},
        ],
    )
    assert inserted_scope_count == 2
    scope_rules = db_instance.list_persona_scope_rules(persona_id=persona_id, user_id="user-1")
    assert len(scope_rules) == 2
    assert {rule["rule_type"] for rule in scope_rules} == {"conversation_id", "media_tag"}

    inserted_policy_count = db_instance.replace_persona_policy_rules(
        persona_id=persona_id,
        user_id="user-1",
        rules=[
            {"rule_kind": "mcp_tool", "rule_name": "knowledge.search", "allowed": True},
            {
                "rule_kind": "skill",
                "rule_name": "digest",
                "allowed": True,
                "require_confirmation": False,
                "max_calls_per_turn": 2,
            },
        ],
    )
    assert inserted_policy_count == 2
    policy_rules = db_instance.list_persona_policy_rules(persona_id=persona_id, user_id="user-1")
    assert len(policy_rules) == 2
    assert {rule["rule_kind"] for rule in policy_rules} == {"mcp_tool", "skill"}

    session_id = db_instance.create_persona_session(
        {
            "persona_id": persona_id,
            "user_id": "user-1",
            "mode": "persistent_scoped",
            "reuse_allowed": True,
            "status": "active",
            "scope_snapshot_json": {"conversations": ["conv-a"], "media_tags": ["physics"]},
            "preferences_json": {
                "use_memory_context": True,
                "use_companion_context": False,
                "memory_top_k": 4,
            },
        }
    )
    session = db_instance.get_persona_session(session_id, user_id="user-1")
    assert session is not None
    assert session["persona_id"] == persona_id
    assert session["reuse_allowed"] is True
    assert session["scope_snapshot"]["conversations"] == ["conv-a"]
    assert session["activity_surface"] == "api.persona"
    assert session["preferences"]["use_memory_context"] is True
    assert session["preferences"]["use_companion_context"] is False
    assert session["preferences"]["memory_top_k"] == 4
    session_version = int(session["version"])

    assert db_instance.update_persona_session(
        session_id=session_id,
        user_id="user-1",
        update_data={
            "status": "paused",
            "activity_surface": "companion.conversation",
            "preferences_json": {
                "use_memory_context": False,
                "use_companion_context": True,
                "memory_top_k": 7,
            },
        },
        expected_version=session_version,
    )
    paused_session = db_instance.get_persona_session(session_id, user_id="user-1")
    assert paused_session is not None
    assert paused_session["status"] == "paused"
    assert paused_session["activity_surface"] == "companion.conversation"
    assert paused_session["preferences"]["use_memory_context"] is False
    assert paused_session["preferences"]["use_companion_context"] is True
    assert paused_session["preferences"]["memory_top_k"] == 7

    memory_id = db_instance.add_persona_memory_entry(
        {
            "persona_id": persona_id,
            "user_id": "user-1",
            "memory_type": "summary",
            "content": "User prefers concise evidence-backed responses.",
            "scope_snapshot_id": "scope_1",
            "session_id": "sess_1",
            "salience": 0.9,
        }
    )
    memories = db_instance.list_persona_memory_entries(user_id="user-1", persona_id=persona_id)
    assert len(memories) == 1
    assert memories[0]["id"] == memory_id
    assert memories[0]["scope_snapshot_id"] == "scope_1"
    assert memories[0]["session_id"] == "sess_1"
    assert memories[0]["archived"] is False

    _ = db_instance.add_persona_memory_entry(
        {
            "persona_id": persona_id,
            "user_id": "user-1",
            "memory_type": "summary",
            "content": "Scope/session isolated memory.",
            "scope_snapshot_id": "scope_2",
            "session_id": "sess_2",
            "salience": 0.7,
        }
    )
    scoped_memories = db_instance.list_persona_memory_entries(
        user_id="user-1",
        persona_id=persona_id,
        scope_snapshot_id="scope_1",
    )
    assert len(scoped_memories) == 1
    assert scoped_memories[0]["id"] == memory_id
    session_memories = db_instance.list_persona_memory_entries(
        user_id="user-1",
        persona_id=persona_id,
        session_id="sess_2",
    )
    assert len(session_memories) == 1
    assert session_memories[0]["session_id"] == "sess_2"

    assert db_instance.set_persona_memory_archived(
        entry_id=memory_id,
        user_id="user-1",
        persona_id=persona_id,
        archived=True,
    )
    visible_memories = db_instance.list_persona_memory_entries(
        user_id="user-1",
        persona_id=persona_id,
        scope_snapshot_id="scope_1",
        include_archived=False,
    )
    assert visible_memories == []

    assert db_instance.get_persona_profile(persona_id, user_id="user-2") is None
    assert db_instance.list_persona_profiles(user_id="user-2") == []
    assert db_instance.get_persona_session(session_id, user_id="user-2") is None
    assert db_instance.list_persona_sessions(user_id="user-2") == []
    assert not db_instance.set_persona_memory_archived(entry_id=memory_id, user_id="user-2", archived=False)


def test_backfill_persona_memory_scope_namespace_updates_only_missing_scope(db_instance: CharactersRAGDB):
    persona_id = db_instance.create_persona_profile(
        {
            "id": "persona-backfill",
            "user_id": "user-1",
            "name": "Backfill Persona",
            "mode": "persistent_scoped",
            "system_prompt": "",
            "is_active": True,
        }
    )

    missing_scope_entry_id = db_instance.add_persona_memory_entry(
        {
            "persona_id": persona_id,
            "user_id": "user-1",
            "memory_type": "summary",
            "content": "legacy-unscoped",
            "scope_snapshot_id": None,
            "session_id": None,
            "salience": 0.4,
        }
    )
    existing_scope_entry_id = db_instance.add_persona_memory_entry(
        {
            "persona_id": persona_id,
            "user_id": "user-1",
            "memory_type": "summary",
            "content": "already-scoped",
            "scope_snapshot_id": "scope_already",
            "session_id": None,
            "salience": 0.4,
        }
    )
    session_scoped_entry_id = db_instance.add_persona_memory_entry(
        {
            "persona_id": persona_id,
            "user_id": "user-1",
            "memory_type": "summary",
            "content": "session-scoped",
            "scope_snapshot_id": None,
            "session_id": "sess_1",
            "salience": 0.4,
        }
    )

    updated_count = db_instance.backfill_persona_memory_scope_namespace(
        user_id="user-1",
        persona_id=persona_id,
        scope_snapshot_id="persistent_legacy_pid_example",
        require_missing_session_id=True,
        include_archived=False,
        include_deleted=False,
    )
    assert updated_count == 1

    rows = db_instance.list_persona_memory_entries(
        user_id="user-1",
        persona_id=persona_id,
        include_archived=True,
        include_deleted=True,
        limit=50,
        offset=0,
    )
    by_id = {str(row.get("id")): row for row in rows}
    assert by_id[missing_scope_entry_id]["scope_snapshot_id"] == "persistent_legacy_pid_example"
    assert by_id[existing_scope_entry_id]["scope_snapshot_id"] == "scope_already"
    assert by_id[session_scoped_entry_id]["scope_snapshot_id"] in (None, "")
