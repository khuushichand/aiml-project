import re

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit


def test_postgres_statement_conversion_includes_chat_topic_metadata_and_flashcard_backlinks(tmp_path):
    db = CharactersRAGDB(db_path=str(tmp_path / "dummy.db"), client_id="test")

    sql = db._MIGRATION_SQL_V13_TO_V14
    assert isinstance(sql, str) and "conversation_clusters" in sql

    stmts = db._convert_sqlite_schema_to_postgres_statements(sql)
    assert isinstance(stmts, list) and len(stmts) > 0

    full = "\n".join(stmts)
    assert "ALTER TABLE conversations ADD COLUMN topic_label_source" in full
    assert "ALTER TABLE conversations ADD COLUMN topic_last_tagged_at" in full
    assert "ALTER TABLE conversations ADD COLUMN topic_last_tagged_message_id" in full
    assert "CREATE TABLE IF NOT EXISTS conversation_clusters" in full
    assert "ALTER TABLE flashcards ADD COLUMN conversation_id" in full
    assert "ALTER TABLE flashcards ADD COLUMN message_id" in full
    assert "idx_conversations_source_external_ref" in full
    assert "idx_flashcards_conversation" in full
    assert "idx_flashcards_message" in full
    assert re.search(r"SET\s+version\s*=\s*14", full, flags=re.IGNORECASE)
