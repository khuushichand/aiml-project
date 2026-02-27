"""Unit tests for ChaChaNotes schema conversion around v26 migrations."""

import re
from collections.abc import Generator
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB

pytestmark = pytest.mark.unit


@pytest.fixture
def char_rag_db(tmp_path: Path) -> Generator[CharactersRAGDB, None, None]:
    """Provide a temporary CharactersRAGDB instance and close all connections on teardown."""
    db = CharactersRAGDB(db_path=str(tmp_path / "dummy.db"), client_id="test")
    try:
        yield db
    finally:
        db.close_all_connections()


def test_postgres_statement_conversion_includes_persona_persistence_tables(
    char_rag_db: CharactersRAGDB,
) -> None:
    """Verify v26 conversion output includes persona persistence tables and indexes."""

    sql = char_rag_db._MIGRATION_SQL_V25_TO_V26
    assert isinstance(sql, str) and "persona_profiles" in sql

    stmts = char_rag_db._convert_sqlite_schema_to_postgres_statements(sql)
    assert isinstance(stmts, list) and len(stmts) > 0

    full = "\n".join(stmts)
    assert "CREATE TABLE IF NOT EXISTS persona_profiles" in full
    assert "CREATE TABLE IF NOT EXISTS persona_scope_rules" in full
    assert "CREATE TABLE IF NOT EXISTS persona_policy_rules" in full
    assert "CREATE TABLE IF NOT EXISTS persona_sessions" in full
    assert "CREATE TABLE IF NOT EXISTS persona_memory_entries" in full
    assert "idx_persona_profiles_user_active" in full
    assert "idx_persona_scope_rules_persona" in full
    assert "idx_persona_policy_rules_persona" in full
    assert "idx_persona_sessions_user" in full
    assert "idx_persona_memory_persona" in full
    assert re.search(r"SET\s+version\s*=\s*26", full, flags=re.IGNORECASE)


def test_postgres_statement_conversion_includes_persona_memory_namespace_migration(
    char_rag_db: CharactersRAGDB,
) -> None:
    """Verify v27 conversion output includes persona memory namespace columns/indexes."""

    sql = char_rag_db._MIGRATION_SQL_V26_TO_V27
    assert isinstance(sql, str) and "persona_memory_entries" in sql

    stmts = char_rag_db._convert_sqlite_schema_to_postgres_statements(sql)
    assert isinstance(stmts, list) and len(stmts) > 0

    full = "\n".join(stmts)
    assert "ALTER TABLE persona_memory_entries" in full
    assert "scope_snapshot_id TEXT" in full
    assert "session_id TEXT" in full
    assert "idx_persona_memory_scope" in full
    assert "idx_persona_memory_session" in full
    assert re.search(r"SET\s+version\s*=\s*27", full, flags=re.IGNORECASE)


def test_postgres_statement_conversion_includes_persona_profile_state_context_default_migration(
    char_rag_db: CharactersRAGDB,
) -> None:
    """Verify v28 conversion output includes persona profile default state-context column."""

    sql = char_rag_db._MIGRATION_SQL_V27_TO_V28
    assert isinstance(sql, str) and "persona_profiles" in sql

    stmts = char_rag_db._convert_sqlite_schema_to_postgres_statements(sql)
    assert isinstance(stmts, list) and len(stmts) > 0

    full = "\n".join(stmts)
    assert "ALTER TABLE persona_profiles" in full
    assert "use_persona_state_context_default BOOLEAN NOT NULL DEFAULT TRUE" in full
    assert re.search(r"SET\s+version\s*=\s*28", full, flags=re.IGNORECASE)


def test_postgres_statement_conversion_includes_moodboard_tables_migration(
    char_rag_db: CharactersRAGDB,
) -> None:
    """Verify v29 conversion output includes moodboard tables and indexes."""

    sql = char_rag_db._MIGRATION_SQL_V28_TO_V29
    assert isinstance(sql, str) and "moodboards" in sql

    stmts = char_rag_db._convert_sqlite_schema_to_postgres_statements(sql)
    assert isinstance(stmts, list) and len(stmts) > 0

    full = "\n".join(stmts)
    assert "CREATE TABLE IF NOT EXISTS moodboards" in full
    assert "CREATE TABLE IF NOT EXISTS moodboard_notes" in full
    assert "idx_moodboard_notes_board" in full
    assert "idx_moodboard_notes_note" in full
    assert re.search(r"SET\s+version\s*=\s*29", full, flags=re.IGNORECASE)
