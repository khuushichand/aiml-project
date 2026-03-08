import sqlite3
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "persona_exemplar_migration.sqlite"


def test_migration_v32_to_latest_creates_persona_exemplar_table(db_path: Path):
    db = CharactersRAGDB(db_path, "persona-exemplar-migration-seed")
    db.close_connection()

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "UPDATE db_schema_version SET version = ? WHERE schema_name = ?",
            (32, CharactersRAGDB._SCHEMA_NAME),
        )
        conn.execute("DROP TABLE IF EXISTS persona_exemplars")
        conn.commit()

    migrated = CharactersRAGDB(db_path, "persona-exemplar-migration-check")
    conn = migrated.get_connection()

    version = conn.execute(
        "SELECT version FROM db_schema_version WHERE schema_name = ?",
        (CharactersRAGDB._SCHEMA_NAME,),
    ).fetchone()["version"]
    assert version == CharactersRAGDB._CURRENT_SCHEMA_VERSION

    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='persona_exemplars'"
    ).fetchone()
    assert table is not None

    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info('persona_exemplars')").fetchall()
    }
    assert {
        "id",
        "persona_id",
        "user_id",
        "kind",
        "content",
        "tone",
        "scenario_tags_json",
        "capability_tags_json",
        "priority",
        "enabled",
        "source_type",
        "source_ref",
        "notes",
        "created_at",
        "last_modified",
        "deleted",
        "version",
    }.issubset(columns)

    indexes = {
        row["name"] for row in conn.execute("PRAGMA index_list('persona_exemplars')").fetchall()
    }
    assert "idx_persona_exemplars_persona" in indexes
    assert "idx_persona_exemplars_user" in indexes
    assert "idx_persona_exemplars_kind" in indexes
    assert "idx_persona_exemplars_enabled" in indexes

    migrated.close_connection()
