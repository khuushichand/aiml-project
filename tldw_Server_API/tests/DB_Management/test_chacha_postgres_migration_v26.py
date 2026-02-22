import re

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit


def test_postgres_statement_conversion_includes_persona_persistence_tables(tmp_path):
    db = CharactersRAGDB(db_path=str(tmp_path / "dummy.db"), client_id="test")

    sql = db._MIGRATION_SQL_V25_TO_V26
    assert isinstance(sql, str) and "persona_profiles" in sql

    stmts = db._convert_sqlite_schema_to_postgres_statements(sql)
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
