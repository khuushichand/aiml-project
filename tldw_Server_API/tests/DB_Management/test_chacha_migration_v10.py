import sqlite3

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit


def _bootstrap_v9_sqlite_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
PRAGMA foreign_keys = OFF;

CREATE TABLE db_schema_version(schema_name TEXT PRIMARY KEY NOT NULL, version INTEGER NOT NULL);
INSERT INTO db_schema_version(schema_name, version) VALUES ('rag_char_chat_schema', 9);

CREATE TABLE character_cards(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  client_id TEXT NOT NULL DEFAULT 'system_init',
  version INTEGER NOT NULL DEFAULT 1
);
INSERT INTO character_cards(id, name, deleted, client_id, version) VALUES (1, 'Default Assistant', 0, 'system_init', 1);

CREATE TABLE messages(
  id TEXT PRIMARY KEY,
  conversation_id TEXT,
  parent_message_id TEXT,
  sender TEXT NOT NULL,
  content TEXT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  client_id TEXT NOT NULL DEFAULT 'legacy',
  version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE conversations(
  id                     TEXT PRIMARY KEY,
  root_id                TEXT NOT NULL,
  forked_from_message_id TEXT REFERENCES messages(id) ON DELETE SET NULL,
  parent_conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
  character_id           INTEGER REFERENCES character_cards(id)
                          ON DELETE CASCADE ON UPDATE CASCADE,
  title        TEXT,
  rating       INTEGER CHECK(rating BETWEEN 1 AND 5),
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted      BOOLEAN  NOT NULL DEFAULT 0,
  client_id    TEXT     NOT NULL,
  version      INTEGER  NOT NULL DEFAULT 1
);

CREATE TABLE notes(
  id            TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  content       TEXT NOT NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN  NOT NULL DEFAULT 0,
  client_id     TEXT     NOT NULL DEFAULT 'unknown',
  version       INTEGER  NOT NULL DEFAULT 1
);

CREATE TABLE keywords(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  keyword TEXT NOT NULL,
  deleted BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE keyword_collections(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  deleted BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE flashcards(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  front TEXT,
  back TEXT,
  notes TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  client_id TEXT NOT NULL DEFAULT 'unknown',
  version INTEGER NOT NULL DEFAULT 1
);

INSERT INTO conversations(id, root_id, forked_from_message_id, parent_conversation_id, character_id, title, rating, created_at, last_modified, deleted, client_id, version)
VALUES ('conv-1', 'conv-1', NULL, NULL, 1, 'Legacy Chat', 5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 'user-1', 1);

INSERT INTO notes(id, title, content, created_at, last_modified, deleted, client_id, version)
VALUES ('note-1', 'Legacy Note', 'content', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 'user-1', 1);

/* Minimal FTS tables to satisfy schema verification */
CREATE VIRTUAL TABLE IF NOT EXISTS character_cards_fts USING fts5(name, description, personality, scenario, system_prompt, content='character_cards', content_rowid='id');
CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(title, content='conversations', content_rowid='rowid');
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(content, content='messages', content_rowid='rowid');
CREATE VIRTUAL TABLE IF NOT EXISTS keywords_fts USING fts5(keyword, content='keywords', content_rowid='id');
CREATE VIRTUAL TABLE IF NOT EXISTS keyword_collections_fts USING fts5(name, content='keyword_collections', content_rowid='id');
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(title, content, content='notes', content_rowid='rowid');
CREATE VIRTUAL TABLE IF NOT EXISTS flashcards_fts USING fts5(front, back, notes, content='flashcards', content_rowid='id');
"""
    )
    conn.commit()
    conn.close()


def test_sqlite_migration_v9_to_v10_backfills_and_indexes(tmp_path):
    db_path = tmp_path / "chacha_v9.db"
    _bootstrap_v9_sqlite_db(str(db_path))

    # Trigger migration to v10
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")
    db.close_connection()

    with sqlite3.connect(db_path) as conn:
        version = conn.execute(
            "SELECT version FROM db_schema_version WHERE schema_name = ?", ("rag_char_chat_schema",)
        ).fetchone()[0]
        assert version == 10

        # Conversations should have state backfilled and new columns/indexes
        conv_cols = [row[1] for row in conn.execute("PRAGMA table_info('conversations')").fetchall()]
        assert {"state", "topic_label", "cluster_id", "source", "external_ref"}.issubset(set(conv_cols))
        state_value = conn.execute("SELECT state FROM conversations WHERE id = 'conv-1'").fetchone()[0]
        assert state_value == "in-progress"

        conv_indexes = {row[1] for row in conn.execute("PRAGMA index_list('conversations')").fetchall()}
        assert {"idx_conversations_state", "idx_conversations_cluster", "idx_conversations_last_modified", "idx_conversations_topic_label"}.issubset(
            conv_indexes
        )

        # Notes should have backlink columns
        note_cols = [row[1] for row in conn.execute("PRAGMA table_info('notes')").fetchall()]
        assert {"conversation_id", "message_id"}.issubset(set(note_cols))

        note_indexes = {row[1] for row in conn.execute("PRAGMA index_list('notes')").fetchall()}
        assert {"idx_notes_conversation", "idx_notes_message"}.issubset(note_indexes)
