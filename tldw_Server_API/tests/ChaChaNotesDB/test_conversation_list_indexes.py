import sqlite3
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit


def test_migration_from_previous_version_adds_conversation_list_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "conversation_list_indexes.sqlite"

    seed = CharactersRAGDB(db_path, "conversation-index-seed")
    seed.close_connection()

    target_names = {
        "idx_conversations_client_deleted_last_modified",
        "idx_conversations_client_character_deleted_last_modified",
        "idx_conversations_client_deleted_created_at",
    }

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "UPDATE db_schema_version SET version = ? WHERE schema_name = ?",
            (CharactersRAGDB._CURRENT_SCHEMA_VERSION - 1, CharactersRAGDB._SCHEMA_NAME),
        )
        for index_name in target_names:
            conn.execute(f"DROP INDEX IF EXISTS {index_name}")
        conn.commit()

    migrated = CharactersRAGDB(db_path, "conversation-index-migration-check")
    conn = migrated.get_connection()

    version = conn.execute(
        "SELECT version FROM db_schema_version WHERE schema_name = ?",
        (CharactersRAGDB._SCHEMA_NAME,),
    ).fetchone()["version"]
    assert version == CharactersRAGDB._CURRENT_SCHEMA_VERSION

    existing_indexes = {
        row["name"] for row in conn.execute("PRAGMA index_list('conversations')").fetchall()
    }
    assert target_names.issubset(existing_indexes)

    migrated.close_connection()
