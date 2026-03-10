import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.tests.Characters.test_character_functionality_db import sample_card_data


pytestmark = pytest.mark.unit


LEGACY_CONVERSATION_COLUMNS = (
    "id",
    "root_id",
    "forked_from_message_id",
    "parent_conversation_id",
    "character_id",
    "title",
    "rating",
    "created_at",
    "last_modified",
    "deleted",
    "client_id",
    "version",
    "state",
    "topic_label",
    "cluster_id",
    "source",
    "external_ref",
    "topic_label_source",
    "topic_last_tagged_at",
    "topic_last_tagged_message_id",
)


LEGACY_CONVERSATIONS_SCHEMA_SQL = """
CREATE TABLE conversations(
  id TEXT PRIMARY KEY,
  root_id TEXT NOT NULL,
  forked_from_message_id TEXT REFERENCES messages(id) ON DELETE SET NULL,
  parent_conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
  character_id INTEGER REFERENCES character_cards(id) ON DELETE CASCADE ON UPDATE CASCADE,
  title TEXT,
  rating INTEGER CHECK(rating BETWEEN 1 AND 5),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  client_id TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  state TEXT NOT NULL DEFAULT 'in-progress' CHECK(state IN ('in-progress','resolved','backlog','non-viable')),
  topic_label TEXT,
  cluster_id TEXT,
  source TEXT,
  external_ref TEXT,
  topic_label_source TEXT,
  topic_last_tagged_at DATETIME,
  topic_last_tagged_message_id TEXT
);

CREATE INDEX idx_conversations_root ON conversations(root_id);
CREATE INDEX idx_conversations_parent ON conversations(parent_conversation_id);
CREATE INDEX idx_conv_char ON conversations(character_id);
CREATE INDEX idx_conversations_state ON conversations(state);
CREATE INDEX idx_conversations_cluster ON conversations(cluster_id);
CREATE INDEX idx_conversations_last_modified ON conversations(last_modified);
CREATE INDEX idx_conversations_topic_label ON conversations(topic_label);
CREATE INDEX idx_conversations_source_external_ref ON conversations(source, external_ref);

CREATE VIRTUAL TABLE conversations_fts
USING fts5(
  title,
  content='conversations',
  content_rowid='rowid'
);

CREATE TRIGGER conversations_ai
AFTER INSERT ON conversations BEGIN
  INSERT INTO conversations_fts(rowid,title)
  SELECT new.rowid,new.title
  WHERE new.deleted = 0 AND new.title IS NOT NULL;
END;

CREATE TRIGGER conversations_au
AFTER UPDATE ON conversations BEGIN
  INSERT INTO conversations_fts(conversations_fts,rowid,title)
  VALUES('delete',old.rowid,old.title);

  INSERT INTO conversations_fts(rowid,title)
  SELECT new.rowid,new.title
  WHERE new.deleted = 0 AND new.title IS NOT NULL;
END;

CREATE TRIGGER conversations_ad
AFTER DELETE ON conversations BEGIN
  INSERT INTO conversations_fts(conversations_fts,rowid,title)
  VALUES('delete',old.rowid,old.title);
END;
"""


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "conversation_assistant_identity.sqlite"


@pytest.fixture
def db_instance(db_path: Path) -> Iterator[CharactersRAGDB]:
    db = CharactersRAGDB(db_path, "assistant-identity-test-client")
    yield db
    db.close_connection()


@pytest.fixture
def character_id(db_instance: CharactersRAGDB) -> int:
    card_id = db_instance.add_character_card(sample_card_data(name="Assistant Identity Source"))
    assert card_id is not None
    return card_id


def _downgrade_conversations_to_v31(db_path: Path) -> None:
    legacy_column_csv = ", ".join(LEGACY_CONVERSATION_COLUMNS)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DROP INDEX IF EXISTS idx_conversations_root")
        conn.execute("DROP INDEX IF EXISTS idx_conversations_parent")
        conn.execute("DROP INDEX IF EXISTS idx_conv_char")
        conn.execute("DROP INDEX IF EXISTS idx_conversations_state")
        conn.execute("DROP INDEX IF EXISTS idx_conversations_cluster")
        conn.execute("DROP INDEX IF EXISTS idx_conversations_last_modified")
        conn.execute("DROP INDEX IF EXISTS idx_conversations_topic_label")
        conn.execute("DROP INDEX IF EXISTS idx_conversations_source_external_ref")
        conn.execute("DROP TRIGGER IF EXISTS conversations_ai")
        conn.execute("DROP TRIGGER IF EXISTS conversations_au")
        conn.execute("DROP TRIGGER IF EXISTS conversations_ad")
        conn.execute("DROP TABLE IF EXISTS conversations_fts")
        conn.execute("ALTER TABLE conversations RENAME TO conversations_v32")
        conn.executescript(LEGACY_CONVERSATIONS_SCHEMA_SQL)
        conn.execute(
            f"INSERT INTO conversations ({legacy_column_csv}) "
            f"SELECT {legacy_column_csv} FROM conversations_v32"
        )
        conn.execute("DROP TABLE conversations_v32")
        conn.execute(
            "UPDATE db_schema_version SET version = ? WHERE schema_name = ?",
            (31, CharactersRAGDB._SCHEMA_NAME),
        )
        conn.commit()


def test_legacy_character_conversation_backfills_assistant_identity(
    db_instance: CharactersRAGDB,
    character_id: int,
) -> None:
    conv_id = db_instance.add_conversation(
        {
            "id": "conv-character-1",
            "character_id": character_id,
            "title": "Legacy chat",
            "root_id": "conv-character-1",
            "client_id": db_instance.client_id,
        }
    )

    row = db_instance.get_conversation_by_id(conv_id)
    assert row is not None
    assert row["assistant_kind"] == "character"
    assert row["assistant_id"] == str(character_id)
    assert row["persona_memory_mode"] is None

    conversations = db_instance.get_conversations_for_user(db_instance.client_id)
    assert len(conversations) == 1
    assert conversations[0]["assistant_kind"] == "character"
    assert conversations[0]["assistant_id"] == str(character_id)


def test_persona_conversation_round_trips_assistant_identity(db_instance: CharactersRAGDB) -> None:
    conv_id = db_instance.add_conversation(
        {
            "id": "conv-persona-1",
            "assistant_kind": "persona",
            "assistant_id": "garden-helper",
            "persona_memory_mode": "read_only",
            "title": "Persona chat",
            "root_id": "conv-persona-1",
            "client_id": db_instance.client_id,
        }
    )

    row = db_instance.get_conversation_by_id(conv_id)
    assert row is not None
    assert row["character_id"] is None
    assert row["assistant_kind"] == "persona"
    assert row["assistant_id"] == "garden-helper"
    assert row["persona_memory_mode"] == "read_only"

    assert db_instance.update_conversation(
        conv_id,
        {"persona_memory_mode": "read_write"},
        expected_version=row["version"],
    )

    updated = db_instance.get_conversation_by_id(conv_id)
    assert updated is not None
    assert updated["assistant_kind"] == "persona"
    assert updated["assistant_id"] == "garden-helper"
    assert updated["persona_memory_mode"] == "read_write"


def test_migration_v31_to_v32_backfills_assistant_identity_for_legacy_rows(db_path: Path) -> None:
    seed = CharactersRAGDB(db_path, "assistant-identity-test-client")
    character_id = seed.add_character_card(sample_card_data(name="Migration Source"))
    conv_id = seed.add_conversation(
        {
            "id": "conv-migration-1",
            "character_id": character_id,
            "title": "Legacy migration chat",
            "root_id": "conv-migration-1",
            "client_id": seed.client_id,
        }
    )
    seed.close_connection()

    _downgrade_conversations_to_v31(db_path)

    migrated = CharactersRAGDB(db_path, "assistant-identity-test-client")
    conn = migrated.get_connection()
    version_row = conn.execute(
        "SELECT version FROM db_schema_version WHERE schema_name = ?",
        (CharactersRAGDB._SCHEMA_NAME,),
    ).fetchone()
    assert version_row is not None
    assert version_row["version"] == CharactersRAGDB._CURRENT_SCHEMA_VERSION

    migrated_row = migrated.get_conversation_by_id(conv_id)
    assert migrated_row is not None
    assert migrated_row["assistant_kind"] == "character"
    assert migrated_row["assistant_id"] == str(character_id)
    assert migrated_row["persona_memory_mode"] is None
    migrated.close_connection()
