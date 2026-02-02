# ChaChaNotes_DB.py
# Description: DB Library for Character Cards, Chats, and Notes.
#
from __future__ import annotations

"""
ChaChaNotes_DB.py
-----------------

A comprehensive SQLite-based library for managing data related to character cards,
chat conversations, messages, notes, keywords, and their interconnections.

This library provides a structured approach to database interactions, including:
- Schema management with versioning.
- Thread-safe database connections using `threading.local`.
- CRUD (Create, Read, Update, Delete) operations for all major entities.
- Optimistic locking for concurrent update and delete operations using a `version` field.
- Soft deletion for records, preserving data history.
- Full-Text Search (FTS5) capabilities for character cards, conversations, messages,
  notes, keywords, and keyword collections, primarily managed by SQL triggers.
- Automated change tracking via a `sync_log` table, largely populated by SQL triggers,
  with manual logging for linking table modifications.
- A transaction context manager for safe and explicit transaction handling.
- Custom exceptions for database-specific errors, schema issues, input validation,
  and concurrency conflicts.

Key entities managed:
- Character Cards: Detailed profiles for characters.
- Conversations: Chat sessions, potentially linked to characters.
- Messages: Individual messages within conversations, supporting text and images.
- Notes: Free-form text notes.
- Keywords: Tags or labels that can be associated with conversations, notes, and collections.
- Keyword Collections: Groupings of keywords.

The library requires a `client_id` upon initialization, which is used to attribute
changes in the `sync_log` and in individual records.
"""
# Imports
import sqlite3
import json
import uuid
import re
from contextlib import contextmanager
from configparser import ConfigParser
from datetime import datetime, timezone, timedelta
from pathlib import Path
import threading
from loguru import logger
from typing import List, Dict, Optional, Any, Union, Set, Tuple
try:  # Prefer psycopg v3 sql helper, fall back to psycopg2 if available
    from psycopg import sql as psycopg_sql  # type: ignore
except Exception:  # pragma: no cover - compatibility fallback
    try:
        from psycopg2 import sql as psycopg_sql  # type: ignore
    except Exception:  # pragma: no cover - driver not installed
        psycopg_sql = None  # type: ignore
#
# Third-Party Libraries
from loguru import logger
#
# Local Imports
#
from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseBackend,
    DatabaseConfig,
    DatabaseError as BackendDatabaseError,
    QueryResult,
)
from tldw_Server_API.app.core.DB_Management.backends.query_utils import (
    normalise_params,
    prepare_backend_many_statement,
    prepare_backend_statement,
    replace_insert_or_ignore,
    transform_sqlite_query_for_postgres,
)
from tldw_Server_API.app.core.DB_Management.backends.fts_translator import FTSQueryTranslator
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.content_backend import get_content_backend
from tldw_Server_API.app.core.config import load_comprehensive_config, settings
#
########################################################################################################################
#
# Functions:

# --- Order-by validation helpers (defense in depth) ---
_ORDER_BY_COLUMN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")
_ORDER_BY_EXPR_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?"
    r"(?:\s+COLLATE\s+NOCASE)?"
    r"(?:\s+(?:ASC|DESC))?$",
    re.IGNORECASE,
)
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# --- Custom Exceptions ---
class CharactersRAGDBError(Exception):
    """Base exception for CharactersRAGDB related errors."""
    pass


class SchemaError(CharactersRAGDBError):
    """Exception for schema version mismatches or migration failures."""
    pass


class InputError(ValueError):
    """Custom exception for input validation errors."""
    pass


class ConflictError(CharactersRAGDBError):
    """
    Indicates a conflict due to concurrent modification or unique constraint violation.

    This can occur if a record's version doesn't match an expected version during
    an update/delete operation (optimistic locking), or if an insert/update
    violates a unique constraint (e.g., duplicate name).

    Attributes:
        entity (Optional[str]): The type of entity involved in the conflict (e.g., "character_cards").
        entity_id (Any): The ID or unique identifier of the entity involved.
    """

    def __init__(
        self,
        message: str = "Conflict detected.",
        entity: Optional[str] = None,
        entity_id: Any = None,
        identifier: Any = None,
    ):
        super().__init__(message)
        if entity_id is None and identifier is not None:
            entity_id = identifier
        self.entity = entity
        self.entity_id = entity_id

    def __str__(self):
        base = super().__str__()
        details = []
        if self.entity:
            details.append(f"Entity: {self.entity}")
        if self.entity_id:
            details.append(f"ID: {self.entity_id}")
        return f"{base} ({', '.join(details)})" if details else base


class BackendCursorAdapter:
    """Adapter exposing QueryResult via a cursor-like interface."""

    def __init__(self, result: QueryResult):
        self._result = result
        self._index = 0
        self.rowcount = result.rowcount
        self.lastrowid = result.lastrowid
        self.description = result.description

    def fetchall(self):
        return list(self._result.rows)

    def fetchone(self):
        if self._index >= len(self._result.rows):
            return None
        row = self._result.rows[self._index]
        self._index += 1
        return row

    def fetchmany(self, size: Optional[int] = None):
        if size is None or size <= 0:
            size = len(self._result.rows) - self._index
        end = min(self._index + size, len(self._result.rows))
        rows = self._result.rows[self._index:end]
        self._index = end
        return list(rows)

    def __iter__(self):
        return iter(self._result.rows)

    def close(self):
        self._result = QueryResult(rows=[], rowcount=0)
        self.rowcount = 0
        self.lastrowid = None
        self.description = None


class BackendCursorWrapper:
    """Cursor wrapper that routes operations through the configured backend."""

    def __init__(self, db: 'CharactersRAGDB', connection):
        self._db = db
        self._connection = connection
        self._result: Optional[QueryResult] = None
        self._adapter: Optional[BackendCursorAdapter] = None
        self.rowcount: int = -1
        self.lastrowid: Optional[int] = None
        self.description = None

    def execute(self, query: str, params: Optional[Union[Tuple, List, Dict]] = None):
        prepared_query, prepared_params = self._db._prepare_backend_statement(query, params)
        self._result = self._db.backend.execute(
            prepared_query,
            prepared_params,
            connection=self._connection,
        )
        self._adapter = BackendCursorAdapter(self._result)
        self.rowcount = self._result.rowcount
        self.lastrowid = self._result.lastrowid
        self.description = self._result.description
        return self

    def executemany(self, query: str, params_list: List[Union[Tuple, List, Dict]]):
        prepared_query, prepared_params_list = self._db._prepare_backend_many_statement(query, params_list)
        self._result = self._db.backend.execute_many(
            prepared_query,
            prepared_params_list,
            connection=self._connection,
        )
        self._adapter = BackendCursorAdapter(self._result)
        self.rowcount = self._result.rowcount
        self.lastrowid = self._result.lastrowid
        self.description = self._result.description
        return self

    def fetchone(self) -> Optional[Dict[str, Any]]:
        if not self._adapter:
            return None
        row = self._adapter.fetchone()
        return dict(row) if row else None

    def fetchall(self) -> List[Dict[str, Any]]:
        if not self._adapter:
            return []
        return [dict(row) for row in self._adapter.fetchall()]

    def fetchmany(self, size: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self._adapter:
            return []
        rows = self._adapter.fetchmany(size)
        return [dict(row) for row in rows]

    def close(self):
        if self._adapter:
            self._adapter.close()
        self._result = None
        self._adapter = None
        self.rowcount = -1
        self.lastrowid = None
        self.description = None


class BackendConnectionWrapper:
    """Connection wrapper that returns backend-aware cursors."""

    def __init__(self, db: 'CharactersRAGDB', connection):
        self._db = db
        self._connection = connection

    def cursor(self):
        if self._db.backend_type == BackendType.SQLITE:
            return self._connection.cursor()
        return BackendCursorWrapper(self._db, self._connection)

    def execute(self, query: str, params: Optional[Union[Tuple, List, Dict]] = None):
        cursor = self.cursor()
        return cursor.execute(query, params)

    def executemany(self, query: str, params_list: List[Union[Tuple, List, Dict]]):
        cursor = self.cursor()
        return cursor.executemany(query, params_list)

    def executescript(self, script: str):
        statements = [stmt.strip() for stmt in script.split(';') if stmt.strip()]
        cursor = self.cursor()
        for stmt in statements:
            cursor.execute(stmt)
        return cursor

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    @property
    def in_transaction(self) -> bool:
        if self._db.backend_type == BackendType.SQLITE:
            return self._connection.in_transaction
        return True

    def __getattr__(self, item):
        return getattr(self._connection, item)


class BackendManagedTransaction:
    """Context manager leveraging the backend's native transaction handling."""

    def __init__(self, db: 'CharactersRAGDB'):
        self._db = db
        self._raw_conn = None
        self._wrapper = None
        self._managed = False
        self._depth = 0

    def __enter__(self):
        self._raw_conn = self._db._get_thread_connection()
        self._depth = getattr(self._db._local, "tx_depth", 0)
        self._managed = self._depth == 0
        setattr(self._db._local, "tx_depth", self._depth + 1)
        self._wrapper = BackendConnectionWrapper(self._db, self._raw_conn)
        return self._wrapper

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._managed and self._raw_conn is not None:
                if exc_type is None:
                    try:
                        self._raw_conn.commit()
                    except Exception as commit_exc:
                        logger.error(
                            "Commit failed for backend transaction on %s: %s",
                            self._db.db_path_str,
                            commit_exc,
                            exc_info=True,
                        )
                        try:
                            self._raw_conn.rollback()
                        except Exception as rollback_exc:  # noqa: BLE001
                            logger.error(
                                "Rollback after commit failure also failed on %s: %s",
                                self._db.db_path_str,
                                rollback_exc,
                                exc_info=True,
                            )
                        raise CharactersRAGDBError(f"Database commit failed: {commit_exc}") from commit_exc
                else:
                    try:
                        self._raw_conn.rollback()
                    except Exception as rollback_exc:  # noqa: BLE001
                        logger.error(
                            "Rollback failed for backend transaction on %s: %s",
                            self._db.db_path_str,
                            rollback_exc,
                            exc_info=True,
                        )
        finally:
            setattr(self._db._local, "tx_depth", self._depth)
            self._wrapper = None
            self._raw_conn = None
        return False


# --- Database Class ---
class CharactersRAGDB:
    """
    Manages SQLite connections and operations for the Character Cards, Chats, and Notes database.

    This class provides a high-level API for interacting with the SQLite database,
    encapsulating schema management, connection handling, and data manipulation.
    It ensures thread-safety for database connections through `threading.local`.

    Key features:
    - Initialization with a specific database path and a unique `client_id`.
    - Automatic schema creation and version checking/migration (currently to V4).
    - Thread-local SQLite connection management, including WAL mode and checkpointing.
    - Methods for CRUD operations on all entities, many featuring optimistic locking.
    - Soft deletion for most entities.
    - Full-Text Search (FTS5) support, with updates primarily handled by database triggers.
    - Synchronization logging to `sync_log` table, mostly via triggers, except for
      many-to-many link table changes which are logged by Python methods.
    - A transaction context manager for grouping operations.

    Attributes:
        db_path (Path): The absolute path to the SQLite database file, or Path(":memory:").
        client_id (str): The identifier for the client instance using this database.
        is_memory_db (bool): True if the database is in-memory.
        db_path_str (str): String representation of the database path for SQLite connection.
    """
    _CURRENT_SCHEMA_VERSION = 19  # Schema v19 adds voice assistant analytics tables
    _SCHEMA_NAME = "rag_char_chat_schema"  # Used for the db_schema_version table
    _ALLOWED_CONVERSATION_STATES: Tuple[str, ...] = ("in-progress", "resolved", "backlog", "non-viable")
    _DEFAULT_CONVERSATION_STATE = "in-progress"

    _FTS_CONFIG: List[Tuple[str, str, List[str]]] = [
        (
            "character_cards_fts",
            "character_cards",
            ["name", "description", "personality", "scenario", "system_prompt"],
        ),
        (
            "conversations_fts",
            "conversations",
            ["title"],
        ),
        (
            "messages_fts",
            "messages",
            ["content"],
        ),
        (
            "keywords_fts",
            "keywords",
            ["keyword"],
        ),
        (
            "keyword_collections_fts",
            "keyword_collections",
            ["name"],
        ),
        (
            "notes_fts",
            "notes",
            ["title", "content"],
        ),
        (
            "flashcards_fts",
            "flashcards",
            ["front", "back", "notes"],
        ),
        (
            "quiz_questions_fts",
            "quiz_questions",
            ["question_text", "explanation"],
        ),
    ]

    _POSTGRES_SEQUENCE_TABLES: Tuple[Tuple[str, str], ...] = (
        ("character_cards", "id"),
        ("keywords", "id"),
        ("keyword_collections", "id"),
        ("sync_log", "change_id"),
        ("decks", "id"),
        ("flashcards", "id"),
        ("flashcard_reviews", "id"),
        ("quizzes", "id"),
        ("quiz_questions", "id"),
        ("quiz_attempts", "id"),
        ("writing_templates", "id"),
        ("writing_themes", "id"),
        ("voice_command_events", "id"),
    )

    _FULL_SCHEMA_SQL_V4 = """
/*───────────────────────────────────────────────────────────────
  RAG Character-Chat Schema  -  Version 4   (2025-05-14)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

/*----------------------------------------------------------------
  0. Schema-version registry
----------------------------------------------------------------*/
CREATE TABLE IF NOT EXISTS db_schema_version(
  schema_name TEXT PRIMARY KEY NOT NULL,
  version     INTEGER NOT NULL
);
INSERT OR IGNORE INTO db_schema_version(schema_name,version)
VALUES('rag_char_chat_schema',0);

/*----------------------------------------------------------------
  1. Character profiles  (FTS5 external-content)
----------------------------------------------------------------*/
CREATE TABLE IF NOT EXISTS character_cards(
  id            INTEGER  PRIMARY KEY AUTOINCREMENT,
  name          TEXT     UNIQUE NOT NULL,
  description   TEXT,
  personality   TEXT,
  scenario      TEXT,
  system_prompt TEXT,
  image                     BLOB,
  post_history_instructions TEXT,
  first_message             TEXT,
  message_example           TEXT,
  creator_notes             TEXT,
  alternate_greetings       TEXT,
  tags                      TEXT,
  creator                   TEXT,
  character_version         TEXT,
  extensions                TEXT,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN  NOT NULL DEFAULT 0,
  client_id     TEXT     NOT NULL DEFAULT 'unknown',
  version       INTEGER  NOT NULL DEFAULT 1
);

/* Ensure default character card (ID 1) exists */
INSERT OR IGNORE INTO character_cards
    (id, name, description, personality, scenario, system_prompt, image,
     post_history_instructions, first_message, message_example,
     creator_notes, alternate_greetings, tags, creator, character_version, extensions,
     created_at, last_modified, client_id, version, deleted)
VALUES
    (1, 'Default Assistant', 'A general-purpose assistant.', NULL, NULL, NULL, NULL, NULL,
     'Hello! How can I help you today?', NULL, NULL, '[]', '[]', 'System', '1.0', '{}',
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'system_init', 1, 0);
/* End of insertion of default character card */

CREATE VIRTUAL TABLE IF NOT EXISTS character_cards_fts
USING fts5(
  name, description, personality, scenario, system_prompt,
  content='character_cards',
  content_rowid='id'
);

DROP TRIGGER IF EXISTS character_cards_ai;
DROP TRIGGER IF EXISTS character_cards_au;
DROP TRIGGER IF EXISTS character_cards_ad;

CREATE TRIGGER character_cards_ai
AFTER INSERT ON character_cards BEGIN
  INSERT INTO character_cards_fts(rowid,name,description,personality,scenario,system_prompt)
  SELECT new.id,new.name,new.description,new.personality,new.scenario,new.system_prompt
  WHERE new.deleted = 0;
END;

CREATE TRIGGER character_cards_au
AFTER UPDATE ON character_cards BEGIN
  INSERT INTO character_cards_fts(character_cards_fts,rowid,
                                  name,description,personality,scenario,system_prompt)
  VALUES('delete',old.id,old.name,old.description,old.personality,old.scenario,old.system_prompt);

  INSERT INTO character_cards_fts(rowid,name,description,personality,scenario,system_prompt)
  SELECT new.id,new.name,new.description,new.personality,new.scenario,new.system_prompt
  WHERE new.deleted = 0;
END;

CREATE TRIGGER character_cards_ad
AFTER DELETE ON character_cards BEGIN
  INSERT INTO character_cards_fts(character_cards_fts,rowid,
                                  name,description,personality,scenario,system_prompt)
  VALUES('delete',old.id,old.name,old.description,old.personality,old.scenario,old.system_prompt);
END;

/*----------------------------------------------------------------
  2. Conversations
----------------------------------------------------------------*/
CREATE TABLE IF NOT EXISTS conversations(
  id                     TEXT PRIMARY KEY,            /* UUID */
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
CREATE INDEX IF NOT EXISTS idx_conversations_root   ON conversations(root_id);
CREATE INDEX IF NOT EXISTS idx_conversations_parent ON conversations(parent_conversation_id);
CREATE INDEX IF NOT EXISTS idx_conv_char           ON conversations(character_id);

CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts
USING fts5(
  title,
  content='conversations',
  content_rowid='rowid'
);

DROP TRIGGER IF EXISTS conversations_ai;
DROP TRIGGER IF EXISTS conversations_au;
DROP TRIGGER IF EXISTS conversations_ad;

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

/*----------------------------------------------------------------
  3. Messages
----------------------------------------------------------------*/
CREATE TABLE IF NOT EXISTS messages(
  id                TEXT PRIMARY KEY,                 /* UUID */
  conversation_id   TEXT  NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  parent_message_id TEXT  REFERENCES messages(id)     ON DELETE SET NULL,
  sender            TEXT  NOT NULL,
  content           TEXT, -- Text content of the message (nullable for image-only)
  image_data        BLOB DEFAULT NULL,
  image_mime_type   TEXT DEFAULT NULL,
  timestamp         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ranking           INTEGER,
  last_modified     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted           BOOLEAN NOT NULL DEFAULT 0,
  client_id         TEXT    NOT NULL,
  version           INTEGER NOT NULL DEFAULT 1
);
/* ... indexes for messages ... */
CREATE INDEX IF NOT EXISTS idx_msgs_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_msgs_parent       ON messages(parent_message_id);
CREATE INDEX IF NOT EXISTS idx_msgs_timestamp    ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_msgs_ranking      ON messages(ranking);
CREATE INDEX IF NOT EXISTS idx_msgs_conv_ts      ON messages(conversation_id,timestamp);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
USING fts5(
  content,
  content='messages',
  content_rowid='rowid'
);

DROP TRIGGER IF EXISTS messages_ai;
DROP TRIGGER IF EXISTS messages_au;
DROP TRIGGER IF EXISTS messages_ad;

CREATE TRIGGER messages_ai
AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid,content)
  SELECT new.rowid,new.content
  WHERE new.deleted = 0;
END;

CREATE TRIGGER messages_au
AFTER UPDATE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts,rowid,content)
  VALUES('delete',old.rowid,old.content);

  INSERT INTO messages_fts(rowid,content)
  SELECT new.rowid,new.content
  WHERE new.deleted = 0;
END;

CREATE TRIGGER messages_ad
AFTER DELETE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts,rowid,content)
  VALUES('delete',old.rowid,old.content);
END;

/*----------------------------------------------------------------
  3b. Message images (multi-image support)
----------------------------------------------------------------*/
CREATE TABLE IF NOT EXISTS message_images(
  message_id      TEXT    NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  position        INTEGER NOT NULL,
  image_data      BLOB    NOT NULL,
  image_mime_type TEXT    NOT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(message_id, position)
);

CREATE INDEX IF NOT EXISTS idx_message_images_message ON message_images(message_id);

/*----------------------------------------------------------------
  4. Keywords
----------------------------------------------------------------*/
CREATE TABLE IF NOT EXISTS keywords(
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  keyword       TEXT    UNIQUE NOT NULL COLLATE NOCASE,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN  NOT NULL DEFAULT 0,
  client_id     TEXT     NOT NULL DEFAULT 'unknown',
  version       INTEGER  NOT NULL DEFAULT 1
);

CREATE VIRTUAL TABLE IF NOT EXISTS keywords_fts
USING fts5(
  keyword,
  content='keywords',
  content_rowid='id'
);

/* ───── clean slate ─────────────────────────────────────────── */
DROP TRIGGER IF EXISTS keywords_ai;
DROP TRIGGER IF EXISTS keywords_au;
DROP TRIGGER IF EXISTS keywords_bd;

/* ───── AFTER INSERT → add to index if not deleted ─────────── */
CREATE TRIGGER keywords_ai
AFTER INSERT ON keywords BEGIN
  INSERT INTO keywords_fts(rowid, keyword)
  SELECT new.id, new.keyword
  WHERE new.deleted = 0;
END;

/* ───── AFTER UPDATE → conditional delete + add -────────────── */
CREATE TRIGGER keywords_au
AFTER UPDATE ON keywords BEGIN
  /* delete the old doc only if it was indexed */
  INSERT INTO keywords_fts(keywords_fts, rowid, keyword)
  SELECT 'delete', old.id, old.keyword
  WHERE old.deleted = 0;

  /* add the new doc if it should be indexed */
  INSERT INTO keywords_fts(rowid, keyword)
  SELECT new.id, new.keyword
  WHERE new.deleted = 0;
END;

/* ───── BEFORE DELETE → remove from index if present ────────── */
CREATE TRIGGER keywords_bd
BEFORE DELETE ON keywords BEGIN
  INSERT INTO keywords_fts(keywords_fts, rowid, keyword)
  SELECT 'delete', old.id, old.keyword
  WHERE old.deleted = 0;
END;

/*----------------------------------------------------------------
  5. Keyword collections
----------------------------------------------------------------*/
CREATE TABLE IF NOT EXISTS keyword_collections(
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT    UNIQUE NOT NULL COLLATE NOCASE,
  parent_id     INTEGER REFERENCES keyword_collections(id)
                         ON DELETE SET NULL ON UPDATE CASCADE,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN  NOT NULL DEFAULT 0,
  client_id     TEXT     NOT NULL DEFAULT 'unknown',
  version       INTEGER  NOT NULL DEFAULT 1
);

CREATE VIRTUAL TABLE IF NOT EXISTS keyword_collections_fts
USING fts5(
  name,
  content='keyword_collections',
  content_rowid='id'
);

DROP TRIGGER IF EXISTS keyword_collections_ai;
DROP TRIGGER IF EXISTS keyword_collections_au;
DROP TRIGGER IF EXISTS keyword_collections_ad;

CREATE TRIGGER keyword_collections_ai
AFTER INSERT ON keyword_collections BEGIN
  INSERT INTO keyword_collections_fts(rowid,name)
  SELECT new.id,new.name
  WHERE new.deleted = 0;
END;

CREATE TRIGGER keyword_collections_au
AFTER UPDATE ON keyword_collections BEGIN
  INSERT INTO keyword_collections_fts(keyword_collections_fts,rowid,name)
  VALUES('delete',old.id,old.name);

  INSERT INTO keyword_collections_fts(rowid,name)
  SELECT new.id,new.name
  WHERE new.deleted = 0;
END;

CREATE TRIGGER keyword_collections_ad
AFTER DELETE ON keyword_collections BEGIN
  INSERT INTO keyword_collections_fts(keyword_collections_fts,rowid,name)
  VALUES('delete',old.id,old.name);
END;

/*----------------------------------------------------------------
  6. Notes
----------------------------------------------------------------*/
CREATE TABLE IF NOT EXISTS notes(
  id            TEXT PRIMARY KEY,                     /* UUID */
  title         TEXT NOT NULL,
  content       TEXT NOT NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN  NOT NULL DEFAULT 0,
  client_id     TEXT     NOT NULL DEFAULT 'unknown',
  version       INTEGER  NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_notes_last_modified ON notes(last_modified);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts
USING fts5(
  title,content,
  content='notes',
  content_rowid='rowid'
);

DROP TRIGGER IF EXISTS notes_ai;
DROP TRIGGER IF EXISTS notes_au;
DROP TRIGGER IF EXISTS notes_ad;

CREATE TRIGGER notes_ai
AFTER INSERT ON notes BEGIN
  INSERT INTO notes_fts(rowid,title,content)
  SELECT new.rowid,new.title,new.content
  WHERE new.deleted = 0;
END;

CREATE TRIGGER notes_au
AFTER UPDATE ON notes BEGIN
  INSERT INTO notes_fts(notes_fts,rowid,title,content)
  VALUES('delete',old.rowid,old.title,old.content);

  INSERT INTO notes_fts(rowid,title,content)
  SELECT new.rowid,new.title,new.content
  WHERE new.deleted = 0;
END;

CREATE TRIGGER notes_ad
AFTER DELETE ON notes BEGIN
  INSERT INTO notes_fts(notes_fts,rowid,title,content)
  VALUES('delete',old.rowid,old.title,old.content);
END;

/*----------------------------------------------------------------
  7. Linking tables (no FTS)
----------------------------------------------------------------*/
CREATE TABLE IF NOT EXISTS conversation_keywords(
  conversation_id TEXT    NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  keyword_id      INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE ON UPDATE CASCADE,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(conversation_id,keyword_id)
);
CREATE INDEX IF NOT EXISTS idx_convkw_kw ON conversation_keywords(keyword_id);

CREATE TABLE IF NOT EXISTS collection_keywords(
  collection_id INTEGER NOT NULL REFERENCES keyword_collections(id) ON DELETE CASCADE ON UPDATE CASCADE,
  keyword_id    INTEGER NOT NULL REFERENCES keywords(id)            ON DELETE CASCADE ON UPDATE CASCADE,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(collection_id,keyword_id)
);
CREATE INDEX IF NOT EXISTS idx_collkw_kw ON collection_keywords(keyword_id);

CREATE TABLE IF NOT EXISTS note_keywords(
  note_id    TEXT    NOT NULL REFERENCES notes(id)                 ON DELETE CASCADE ON UPDATE CASCADE,
  keyword_id INTEGER NOT NULL REFERENCES keywords(id)              ON DELETE CASCADE ON UPDATE CASCADE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(note_id,keyword_id)
);
CREATE INDEX IF NOT EXISTS idx_notekw_kw ON note_keywords(keyword_id);

/*----------------------------------------------------------------
  8. Sync log (plus triggers)
----------------------------------------------------------------*/
CREATE TABLE IF NOT EXISTS sync_log(
  change_id   INTEGER  PRIMARY KEY AUTOINCREMENT,
  entity      TEXT     NOT NULL,
  entity_id   TEXT     NOT NULL,
  operation   TEXT     NOT NULL CHECK(operation IN('create','update','delete')),
  timestamp   DATETIME NOT NULL,
  client_id   TEXT     NOT NULL,
  version     INTEGER  NOT NULL,
  payload     TEXT     NOT NULL          /* JSON blob */
);
CREATE INDEX IF NOT EXISTS idx_sync_log_ts     ON sync_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_sync_log_entity ON sync_log(entity,entity_id);

/*-- drop any pre-existing sync triggers -----------*/
DROP TRIGGER IF EXISTS messages_sync_create;
DROP TRIGGER IF EXISTS messages_sync_update;
DROP TRIGGER IF EXISTS messages_sync_delete;
DROP TRIGGER IF EXISTS messages_sync_undelete;

DROP TRIGGER IF EXISTS conversations_sync_create;
DROP TRIGGER IF EXISTS conversations_sync_update;
DROP TRIGGER IF EXISTS conversations_sync_delete;
DROP TRIGGER IF EXISTS conversations_sync_undelete;

DROP TRIGGER IF EXISTS character_cards_sync_create;
DROP TRIGGER IF EXISTS character_cards_sync_update;
DROP TRIGGER IF EXISTS character_cards_sync_delete;
DROP TRIGGER IF EXISTS character_cards_sync_undelete;

DROP TRIGGER IF EXISTS notes_sync_create;
DROP TRIGGER IF EXISTS notes_sync_update;
DROP TRIGGER IF EXISTS notes_sync_delete;
DROP TRIGGER IF EXISTS notes_sync_undelete;

DROP TRIGGER IF EXISTS keywords_sync_create;
DROP TRIGGER IF EXISTS keywords_sync_update;
DROP TRIGGER IF EXISTS keywords_sync_delete;
DROP TRIGGER IF EXISTS keywords_sync_undelete;

DROP TRIGGER IF EXISTS keyword_collections_sync_create;
DROP TRIGGER IF EXISTS keyword_collections_sync_update;
DROP TRIGGER IF EXISTS keyword_collections_sync_delete;
DROP TRIGGER IF EXISTS keyword_collections_sync_undelete;

/*-- sync triggers: messages ---------------*/
CREATE TRIGGER messages_sync_create
AFTER INSERT ON messages BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('messages',NEW.id,'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'conversation_id',NEW.conversation_id,'parent_message_id',NEW.parent_message_id,
                     'sender',NEW.sender,'content',NEW.content,
                     'image_mime_type',NEW.image_mime_type,
                     'timestamp',NEW.timestamp,'ranking',NEW.ranking,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER messages_sync_update
AFTER UPDATE ON messages
WHEN OLD.deleted = NEW.deleted AND (
     OLD.content IS NOT NEW.content OR
     OLD.image_data IS NOT NEW.image_data OR
     OLD.image_mime_type IS NOT NEW.image_mime_type OR
     OLD.ranking IS NOT NEW.ranking OR
     OLD.parent_message_id IS NOT NEW.parent_message_id OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('messages',NEW.id,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'conversation_id',NEW.conversation_id,'parent_message_id',NEW.parent_message_id,
                     'sender',NEW.sender,'content',NEW.content,
                     'image_mime_type',NEW.image_mime_type,
                     'timestamp',NEW.timestamp,'ranking',NEW.ranking,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER messages_sync_delete
AFTER UPDATE ON messages
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('messages',NEW.id,'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

/* messages_sync_delete and messages_sync_undelete don't strictly need image_data in payload
   as 'delete' just tombstones, and 'undelete' (as 'update') would repopulate all fields.
   The 'undelete' trigger would need to include the image fields if they are to be restored.
*/
CREATE TRIGGER messages_sync_undelete
AFTER UPDATE ON messages
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('messages',NEW.id,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'conversation_id',NEW.conversation_id,'parent_message_id',NEW.parent_message_id,
                     'sender',NEW.sender,'content',NEW.content,
                     'image_mime_type',NEW.image_mime_type,
                     'timestamp',NEW.timestamp,'ranking',NEW.ranking,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

/*-- sync triggers: conversations -----------*/
CREATE TRIGGER conversations_sync_create
AFTER INSERT ON conversations BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('conversations',NEW.id,'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'root_id',NEW.root_id,'forked_from_message_id',NEW.forked_from_message_id,
                     'parent_conversation_id',NEW.parent_conversation_id,'character_id',NEW.character_id,'title',NEW.title,
                     'rating',NEW.rating,'created_at',NEW.created_at,'last_modified',NEW.last_modified,'deleted',NEW.deleted,
                     'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER conversations_sync_update
AFTER UPDATE ON conversations
WHEN OLD.deleted = NEW.deleted AND (
     OLD.title IS NOT NEW.title OR
     OLD.rating IS NOT NEW.rating OR
     OLD.forked_from_message_id IS NOT NEW.forked_from_message_id OR
     OLD.parent_conversation_id IS NOT NEW.parent_conversation_id OR
     OLD.character_id IS NOT NEW.character_id OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('conversations',NEW.id,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'root_id',NEW.root_id,'forked_from_message_id',NEW.forked_from_message_id,
                     'parent_conversation_id',NEW.parent_conversation_id,'character_id',NEW.character_id,'title',NEW.title,
                     'rating',NEW.rating,'created_at',NEW.created_at,'last_modified',NEW.last_modified,'deleted',NEW.deleted,
                     'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER conversations_sync_delete
AFTER UPDATE ON conversations
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('conversations',NEW.id,'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER conversations_sync_undelete
AFTER UPDATE ON conversations
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('conversations',NEW.id,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'root_id',NEW.root_id,'forked_from_message_id',NEW.forked_from_message_id,
                     'parent_conversation_id',NEW.parent_conversation_id,'character_id',NEW.character_id,'title',NEW.title,
                     'rating',NEW.rating,'created_at',NEW.created_at,'last_modified',NEW.last_modified,'deleted',NEW.deleted,
                     'client_id',NEW.client_id,'version',NEW.version));
END;

/*-- sync triggers: character_cards ---------*/
CREATE TRIGGER character_cards_sync_create
AFTER INSERT ON character_cards BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('character_cards',CAST(NEW.id AS TEXT),'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'description',NEW.description,'personality',NEW.personality,
                     'scenario',NEW.scenario,'post_history_instructions',NEW.post_history_instructions,
                     'first_message',NEW.first_message,'message_example',NEW.message_example,'creator_notes',NEW.creator_notes,
                     'system_prompt',NEW.system_prompt,'alternate_greetings',NEW.alternate_greetings,'tags',NEW.tags,'creator',NEW.creator,
                     'character_version',NEW.character_version,'extensions',NEW.extensions,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER character_cards_sync_update
AFTER UPDATE ON character_cards
WHEN OLD.deleted = NEW.deleted AND (
     OLD.name IS NOT NEW.name OR
     OLD.description IS NOT NEW.description OR
     OLD.personality IS NOT NEW.personality OR
     OLD.scenario IS NOT NEW.scenario OR
     OLD.image IS NOT NEW.image OR
     OLD.post_history_instructions IS NOT NEW.post_history_instructions OR
     OLD.first_message IS NOT NEW.first_message OR
     OLD.message_example IS NOT NEW.message_example OR
     OLD.creator_notes IS NOT NEW.creator_notes OR
     OLD.system_prompt IS NOT NEW.system_prompt OR
     OLD.alternate_greetings IS NOT NEW.alternate_greetings OR
     OLD.tags IS NOT NEW.tags OR
     OLD.creator IS NOT NEW.creator OR
     OLD.character_version IS NOT NEW.character_version OR
     OLD.extensions IS NOT NEW.extensions OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('character_cards',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'description',NEW.description,'personality',NEW.personality,
                     'scenario',NEW.scenario,'post_history_instructions',NEW.post_history_instructions,
                     'first_message',NEW.first_message,'message_example',NEW.message_example,'creator_notes',NEW.creator_notes,
                     'system_prompt',NEW.system_prompt,'alternate_greetings',NEW.alternate_greetings,'tags',NEW.tags,'creator',NEW.creator,
                     'character_version',NEW.character_version,'extensions',NEW.extensions,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER character_cards_sync_delete
AFTER UPDATE ON character_cards
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('character_cards',CAST(NEW.id AS TEXT),'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER character_cards_sync_undelete
AFTER UPDATE ON character_cards
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('character_cards',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'description',NEW.description,'personality',NEW.personality,
                     'scenario',NEW.scenario,'post_history_instructions',NEW.post_history_instructions,
                     'first_message',NEW.first_message,'message_example',NEW.message_example,'creator_notes',NEW.creator_notes,
                     'system_prompt',NEW.system_prompt,'alternate_greetings',NEW.alternate_greetings,'tags',NEW.tags,'creator',NEW.creator,
                     'character_version',NEW.character_version,'extensions',NEW.extensions,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

/*-- sync triggers: notes ---------------*/
CREATE TRIGGER notes_sync_create
AFTER INSERT ON notes BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('notes',NEW.id,'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'title',NEW.title,'content',NEW.content,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER notes_sync_update
AFTER UPDATE ON notes
WHEN OLD.deleted = NEW.deleted AND (
     OLD.title IS NOT NEW.title OR
     OLD.content IS NOT NEW.content OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('notes',NEW.id,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'title',NEW.title,'content',NEW.content,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER notes_sync_delete
AFTER UPDATE ON notes
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('notes',NEW.id,'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER notes_sync_undelete
AFTER UPDATE ON notes
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('notes',NEW.id,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'title',NEW.title,'content',NEW.content,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

/*-- sync triggers: keywords ----*/
CREATE TRIGGER keywords_sync_create
AFTER INSERT ON keywords BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('keywords',CAST(NEW.id AS TEXT),'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'keyword',NEW.keyword,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER keywords_sync_update
AFTER UPDATE ON keywords
WHEN OLD.deleted = NEW.deleted AND (
     OLD.keyword IS NOT NEW.keyword OR -- Though keyword itself is unlikely to change if it's the unique identifier
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('keywords',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'keyword',NEW.keyword,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER keywords_sync_delete
AFTER UPDATE ON keywords
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('keywords',CAST(NEW.id AS TEXT),'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER keywords_sync_undelete
AFTER UPDATE ON keywords
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('keywords',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'keyword',NEW.keyword,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;


/*-- sync triggers: keyword_collections ----*/
CREATE TRIGGER keyword_collections_sync_create
AFTER INSERT ON keyword_collections BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('keyword_collections',CAST(NEW.id AS TEXT),'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'parent_id',NEW.parent_id,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER keyword_collections_sync_update
AFTER UPDATE ON keyword_collections
WHEN OLD.deleted = NEW.deleted AND (
     OLD.name IS NOT NEW.name OR
     OLD.parent_id IS NOT NEW.parent_id OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('keyword_collections',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'parent_id',NEW.parent_id,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER keyword_collections_sync_delete
AFTER UPDATE ON keyword_collections
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('keyword_collections',CAST(NEW.id AS TEXT),'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER keyword_collections_sync_undelete
AFTER UPDATE ON keyword_collections
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('keyword_collections',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'parent_id',NEW.parent_id,'created_at',NEW.created_at,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

/*----------------------------------------------------------------
  Finalise version bump
----------------------------------------------------------------*/
UPDATE db_schema_version
   SET version = 4
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 4;
"""

    # --- Migration: V4 -> V5 (Flashcards/Decks/Reviews) ---
    _MIGRATION_SQL_V4_TO_V5 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 5 - Flashcards/Decks/SRS (2025-09-21)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

/* Decks table */
CREATE TABLE IF NOT EXISTS decks(
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT UNIQUE NOT NULL,
  description   TEXT,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN  NOT NULL DEFAULT 0,
  client_id     TEXT     NOT NULL DEFAULT 'unknown',
  version       INTEGER  NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_decks_deleted ON decks(deleted);
CREATE INDEX IF NOT EXISTS idx_decks_last_modified ON decks(last_modified);

/* Flashcards table - with integer id for FTS external-content */
CREATE TABLE IF NOT EXISTS flashcards(
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  uuid             TEXT UNIQUE NOT NULL,
  deck_id          INTEGER REFERENCES decks(id) ON DELETE SET NULL,
  front            TEXT NOT NULL,
  back             TEXT NOT NULL,
  notes            TEXT,
  is_cloze         BOOLEAN NOT NULL DEFAULT 0,
  tags_json        TEXT,
  source_ref_type  TEXT CHECK(source_ref_type IN ('media','message','note','manual')) DEFAULT 'manual',
  source_ref_id    TEXT,
  ef               REAL NOT NULL DEFAULT 2.5,
  interval_days    INTEGER NOT NULL DEFAULT 0,
  repetitions      INTEGER NOT NULL DEFAULT 0,
  lapses           INTEGER NOT NULL DEFAULT 0,
  due_at           DATETIME,
  last_reviewed_at DATETIME,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted          BOOLEAN NOT NULL DEFAULT 0,
  client_id        TEXT NOT NULL DEFAULT 'unknown',
  version          INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_flashcards_deck_id ON flashcards(deck_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_due_at ON flashcards(due_at);
CREATE INDEX IF NOT EXISTS idx_flashcards_deleted ON flashcards(deleted);
CREATE INDEX IF NOT EXISTS idx_flashcards_created_at ON flashcards(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_flashcards_uuid ON flashcards(uuid);

/* FTS for flashcards (front/back/notes) */
CREATE VIRTUAL TABLE IF NOT EXISTS flashcards_fts
USING fts5(
  front, back, notes,
  content='flashcards',
  content_rowid='id'
);

DROP TRIGGER IF EXISTS flashcards_ai;
DROP TRIGGER IF EXISTS flashcards_au;
DROP TRIGGER IF EXISTS flashcards_ad;

CREATE TRIGGER flashcards_ai
AFTER INSERT ON flashcards BEGIN
  INSERT INTO flashcards_fts(rowid,front,back,notes)
  SELECT new.id,new.front,new.back,new.notes
  WHERE new.deleted = 0;
END;

CREATE TRIGGER flashcards_au
AFTER UPDATE ON flashcards BEGIN
  INSERT INTO flashcards_fts(flashcards_fts,rowid,front,back,notes)
  VALUES('delete',old.id,old.front,old.back,old.notes);

  INSERT INTO flashcards_fts(rowid,front,back,notes)
  SELECT new.id,new.front,new.back,new.notes
  WHERE new.deleted = 0;
END;

CREATE TRIGGER flashcards_ad
AFTER DELETE ON flashcards BEGIN
  INSERT INTO flashcards_fts(flashcards_fts,rowid,front,back,notes)
  VALUES('delete',old.id,old.front,old.back,old.notes);
END;

/* Flashcard keyword linking */
CREATE TABLE IF NOT EXISTS flashcard_keywords(
  card_id    INTEGER NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
  keyword_id INTEGER NOT NULL REFERENCES keywords(id)  ON DELETE CASCADE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(card_id, keyword_id)
);
CREATE INDEX IF NOT EXISTS idx_flashcard_kw_kw ON flashcard_keywords(keyword_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_kw_card ON flashcard_keywords(card_id);

/* Reviews table (history of SRS reviews) */
CREATE TABLE IF NOT EXISTS flashcard_reviews(
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id                INTEGER NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
  reviewed_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  rating                 INTEGER NOT NULL,
  answer_time_ms         INTEGER,
  scheduled_interval_days INTEGER,
  new_ef                 REAL,
  new_repetitions        INTEGER,
  was_lapse              BOOLEAN NOT NULL DEFAULT 0,
  client_id              TEXT NOT NULL DEFAULT 'unknown'
);
CREATE INDEX IF NOT EXISTS idx_flashcard_reviews_card ON flashcard_reviews(card_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_reviews_time ON flashcard_reviews(reviewed_at);

/* Sync triggers for decks */
DROP TRIGGER IF EXISTS decks_sync_create;
DROP TRIGGER IF EXISTS decks_sync_update;
DROP TRIGGER IF EXISTS decks_sync_delete;
DROP TRIGGER IF EXISTS decks_sync_undelete;

CREATE TRIGGER decks_sync_create
AFTER INSERT ON decks BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('decks',CAST(NEW.id AS TEXT),'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'description',NEW.description,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER decks_sync_update
AFTER UPDATE ON decks
WHEN OLD.deleted = NEW.deleted AND (
     OLD.name IS NOT NEW.name OR
     OLD.description IS NOT NEW.description OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('decks',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'description',NEW.description,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER decks_sync_delete
AFTER UPDATE ON decks
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('decks',CAST(NEW.id AS TEXT),'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER decks_sync_undelete
AFTER UPDATE ON decks
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('decks',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'description',NEW.description,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

/* Sync triggers for flashcards */
DROP TRIGGER IF EXISTS flashcards_sync_create;
DROP TRIGGER IF EXISTS flashcards_sync_update;
DROP TRIGGER IF EXISTS flashcards_sync_delete;
DROP TRIGGER IF EXISTS flashcards_sync_undelete;

CREATE TRIGGER flashcards_sync_create
AFTER INSERT ON flashcards BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('flashcards',NEW.uuid,'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('uuid',NEW.uuid,'deck_id',NEW.deck_id,'front',NEW.front,'back',NEW.back,
                     'notes',NEW.notes,'is_cloze',NEW.is_cloze,'tags_json',NEW.tags_json,
                     'ef',NEW.ef,'interval_days',NEW.interval_days,'repetitions',NEW.repetitions,
                     'lapses',NEW.lapses,'due_at',NEW.due_at,'last_reviewed_at',NEW.last_reviewed_at,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER flashcards_sync_update
AFTER UPDATE ON flashcards
WHEN OLD.deleted = NEW.deleted AND (
     OLD.deck_id IS NOT NEW.deck_id OR
     OLD.front IS NOT NEW.front OR
     OLD.back IS NOT NEW.back OR
     OLD.notes IS NOT NEW.notes OR
     OLD.is_cloze IS NOT NEW.is_cloze OR
     OLD.tags_json IS NOT NEW.tags_json OR
     OLD.ef IS NOT NEW.ef OR
     OLD.interval_days IS NOT NEW.interval_days OR
     OLD.repetitions IS NOT NEW.repetitions OR
     OLD.lapses IS NOT NEW.lapses OR
     OLD.due_at IS NOT NEW.due_at OR
     OLD.last_reviewed_at IS NOT NEW.last_reviewed_at OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('flashcards',NEW.uuid,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('uuid',NEW.uuid,'deck_id',NEW.deck_id,'front',NEW.front,'back',NEW.back,
                     'notes',NEW.notes,'is_cloze',NEW.is_cloze,'tags_json',NEW.tags_json,
                     'ef',NEW.ef,'interval_days',NEW.interval_days,'repetitions',NEW.repetitions,
                     'lapses',NEW.lapses,'due_at',NEW.due_at,'last_reviewed_at',NEW.last_reviewed_at,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER flashcards_sync_delete
AFTER UPDATE ON flashcards
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('flashcards',NEW.uuid,'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('uuid',NEW.uuid,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER flashcards_sync_undelete
AFTER UPDATE ON flashcards
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('flashcards',NEW.uuid,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('uuid',NEW.uuid,'deck_id',NEW.deck_id,'front',NEW.front,'back',NEW.back,
                     'notes',NEW.notes,'is_cloze',NEW.is_cloze,'tags_json',NEW.tags_json,
                     'ef',NEW.ef,'interval_days',NEW.interval_days,'repetitions',NEW.repetitions,
                     'lapses',NEW.lapses,'due_at',NEW.due_at,'last_reviewed_at',NEW.last_reviewed_at,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

/* Finalise version bump to 5 */
UPDATE db_schema_version
   SET version = 5
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 5;
"""

    # --- Migration: V5 -> V6 (Flashcard model_type + extra) ---
    _MIGRATION_SQL_V5_TO_V6 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 6 - Flashcard model_type + extra (2025-09-21)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

ALTER TABLE flashcards ADD COLUMN model_type TEXT NOT NULL DEFAULT 'basic' CHECK(model_type IN ('basic','basic_reverse','cloze'));
ALTER TABLE flashcards ADD COLUMN extra TEXT;

UPDATE db_schema_version
   SET version = 6
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 6;
"""

    # --- Migration: V6 -> V7 (Flashcard reverse flag) ---
    _MIGRATION_SQL_V6_TO_V7 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 7 - Flashcard reverse flag (2025-09-21)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

ALTER TABLE flashcards ADD COLUMN reverse BOOLEAN NOT NULL DEFAULT 0;

UPDATE db_schema_version
   SET version = 7
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 7;
"""

    # --- Migration: V7 -> V8 (Message images table) ---
    _MIGRATION_SQL_V7_TO_V8 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 8 - Message images table (2025-10-14)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS message_images(
  message_id      TEXT    NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  position        INTEGER NOT NULL,
  image_data      BLOB    NOT NULL,
  image_mime_type TEXT    NOT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(message_id, position)
);

CREATE INDEX IF NOT EXISTS idx_message_images_message ON message_images(message_id);

INSERT OR IGNORE INTO message_images (message_id, position, image_data, image_mime_type, created_at)
SELECT id, 0, image_data, image_mime_type, CURRENT_TIMESTAMP
FROM messages
WHERE image_data IS NOT NULL;

UPDATE db_schema_version
   SET version = 8
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 8;
"""

    # --- Migration: V8 -> V9 (Notes Graph: note_edges table) ---
    _MIGRATION_SQL_V8_TO_V9 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 9 - Notes Graph manual edges (2025-11-11)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

/* Explicit manual note edges (per user). Derived edges are NOT persisted. */
CREATE TABLE IF NOT EXISTS note_edges(
  edge_id       TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL,
  from_note_id  TEXT NOT NULL,
  to_note_id    TEXT NOT NULL,
  type          TEXT NOT NULL, /* 'manual' (MVP) */
  directed      INTEGER NOT NULL DEFAULT 0,
  weight        REAL DEFAULT 1.0,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by    TEXT NOT NULL,
  metadata      JSON
);

/* Canonicalization for undirected edges (enforced at application layer).
   Self-loop prevention (from_note_id != to_note_id) is also enforced at the
   application layer for portability. We intentionally do not add a DB-level
   CHECK constraint here because the Postgres migration transformer does not
   currently translate SQLite CHECK clauses. */

/* Helpful indexes */
CREATE INDEX IF NOT EXISTS idx_note_edges_user_from_to ON note_edges(user_id, from_note_id, to_note_id);
CREATE INDEX IF NOT EXISTS idx_note_edges_user_type     ON note_edges(user_id, type);
CREATE INDEX IF NOT EXISTS idx_note_edges_user_to       ON note_edges(user_id, to_note_id);

/* Uniqueness for undirected edges after canonicalization */
CREATE UNIQUE INDEX IF NOT EXISTS uniq_note_edges_undirected ON note_edges(user_id, type, directed, from_note_id, to_note_id);

UPDATE db_schema_version
   SET version = 9
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 9;
"""

    # --- Migration: V9 -> V10 (Chat metadata + note backlinks + indexes) ---
    _MIGRATION_SQL_V9_TO_V10 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 10 - Chat metadata + note backlinks (2025-11-20)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

/* Conversations: state/topic/cluster/source/external_ref */
ALTER TABLE conversations ADD COLUMN state TEXT NOT NULL DEFAULT 'in-progress' CHECK(state IN ('in-progress','resolved','backlog','non-viable'));
ALTER TABLE conversations ADD COLUMN topic_label TEXT;
ALTER TABLE conversations ADD COLUMN cluster_id TEXT;
ALTER TABLE conversations ADD COLUMN source TEXT;
ALTER TABLE conversations ADD COLUMN external_ref TEXT;

/* Backfill legacy rows to default state */
UPDATE conversations SET state = 'in-progress' WHERE state IS NULL OR TRIM(state) = '';

/* Helpful indexes for new filters/orderings */
CREATE INDEX IF NOT EXISTS idx_conversations_state ON conversations(state);
CREATE INDEX IF NOT EXISTS idx_conversations_cluster ON conversations(cluster_id);
CREATE INDEX IF NOT EXISTS idx_conversations_last_modified ON conversations(last_modified);
CREATE INDEX IF NOT EXISTS idx_conversations_topic_label ON conversations(topic_label);

/* Notes: backlinks to conversations/messages */
ALTER TABLE notes ADD COLUMN conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL;
ALTER TABLE notes ADD COLUMN message_id TEXT REFERENCES messages(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_notes_conversation ON notes(conversation_id);
CREATE INDEX IF NOT EXISTS idx_notes_message ON notes(message_id);

UPDATE db_schema_version
   SET version = 10
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 10;
"""

    # --- Migration: V10 -> V11 (Allow NULL message content) ---
    _MIGRATION_SQL_V10_TO_V11 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 11 - Nullable message content (2025-11-25)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = OFF;

DROP TRIGGER IF EXISTS messages_ai;
DROP TRIGGER IF EXISTS messages_au;
DROP TRIGGER IF EXISTS messages_ad;
DROP TRIGGER IF EXISTS messages_sync_create;
DROP TRIGGER IF EXISTS messages_sync_update;
DROP TRIGGER IF EXISTS messages_sync_delete;
DROP TRIGGER IF EXISTS messages_sync_undelete;

DROP TABLE IF EXISTS messages_fts;
DROP TABLE IF EXISTS messages_new;

CREATE TABLE IF NOT EXISTS messages_new(
  id                TEXT PRIMARY KEY,                 /* UUID */
  conversation_id   TEXT  NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  parent_message_id TEXT  REFERENCES messages_new(id) ON DELETE SET NULL,
  sender            TEXT  NOT NULL,
  content           TEXT, -- Text content of the message (nullable for image-only)
  image_data        BLOB DEFAULT NULL,
  image_mime_type   TEXT DEFAULT NULL,
  timestamp         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ranking           INTEGER,
  last_modified     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted           BOOLEAN NOT NULL DEFAULT 0,
  client_id         TEXT    NOT NULL,
  version           INTEGER NOT NULL DEFAULT 1
);

INSERT INTO messages_new (
  id, conversation_id, parent_message_id, sender, content, image_data, image_mime_type,
  timestamp, ranking, last_modified, deleted, client_id, version
)
SELECT
  id, conversation_id, parent_message_id, sender, content, image_data, image_mime_type,
  timestamp, ranking, last_modified, deleted, client_id, version
FROM messages;

DROP TABLE messages;
ALTER TABLE messages_new RENAME TO messages;

CREATE INDEX IF NOT EXISTS idx_msgs_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_msgs_parent       ON messages(parent_message_id);
CREATE INDEX IF NOT EXISTS idx_msgs_timestamp    ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_msgs_ranking      ON messages(ranking);
CREATE INDEX IF NOT EXISTS idx_msgs_conv_ts      ON messages(conversation_id,timestamp);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
USING fts5(
  content,
  content='messages',
  content_rowid='rowid'
);

CREATE TRIGGER messages_ai
AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid,content)
  SELECT new.rowid,new.content
  WHERE new.deleted = 0;
END;

CREATE TRIGGER messages_au
AFTER UPDATE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts,rowid,content)
  VALUES('delete',old.rowid,old.content);

  INSERT INTO messages_fts(rowid,content)
  SELECT new.rowid,new.content
  WHERE new.deleted = 0;
END;

CREATE TRIGGER messages_ad
AFTER DELETE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts,rowid,content)
  VALUES('delete',old.rowid,old.content);
END;

CREATE TRIGGER messages_sync_create
AFTER INSERT ON messages BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('messages',NEW.id,'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'conversation_id',NEW.conversation_id,'parent_message_id',NEW.parent_message_id,
                     'sender',NEW.sender,'content',NEW.content,
                     'image_mime_type',NEW.image_mime_type,
                     'timestamp',NEW.timestamp,'ranking',NEW.ranking,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER messages_sync_update
AFTER UPDATE ON messages
WHEN OLD.deleted = NEW.deleted AND (
     OLD.content IS NOT NEW.content OR
     OLD.image_data IS NOT NEW.image_data OR
     OLD.image_mime_type IS NOT NEW.image_mime_type OR
     OLD.ranking IS NOT NEW.ranking OR
     OLD.parent_message_id IS NOT NEW.parent_message_id OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('messages',NEW.id,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'conversation_id',NEW.conversation_id,'parent_message_id',NEW.parent_message_id,
                     'sender',NEW.sender,'content',NEW.content,
                     'image_mime_type',NEW.image_mime_type,
                     'timestamp',NEW.timestamp,'ranking',NEW.ranking,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER messages_sync_delete
AFTER UPDATE ON messages
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('messages',NEW.id,'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER messages_sync_undelete
AFTER UPDATE ON messages
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('messages',NEW.id,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'conversation_id',NEW.conversation_id,'parent_message_id',NEW.parent_message_id,
                     'sender',NEW.sender,'content',NEW.content,
                     'image_mime_type',NEW.image_mime_type,
                     'timestamp',NEW.timestamp,'ranking',NEW.ranking,
                     'last_modified',NEW.last_modified,'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

INSERT INTO messages_fts(messages_fts) VALUES('rebuild');

PRAGMA foreign_keys = ON;

UPDATE db_schema_version
   SET version = 11
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 11;
"""

    # --- Migration: V11 -> V12 (Quizzes + attempts) ---
    _MIGRATION_SQL_V11_TO_V12 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 12 - Quizzes (2025-12-01)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

/* Quizzes table */
CREATE TABLE IF NOT EXISTS quizzes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  workspace_tag TEXT,
  media_id INTEGER,
  total_questions INTEGER DEFAULT 0,
  time_limit_seconds INTEGER,
  passing_score INTEGER,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  client_id TEXT NOT NULL DEFAULT 'unknown',
  version INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quizzes_media_id ON quizzes(media_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_deleted ON quizzes(deleted);
CREATE INDEX IF NOT EXISTS idx_quizzes_last_modified ON quizzes(last_modified);

/* Quiz questions */
CREATE TABLE IF NOT EXISTS quiz_questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
  question_type TEXT NOT NULL CHECK(question_type IN ('multiple_choice', 'true_false', 'fill_blank')),
  question_text TEXT NOT NULL,
  options TEXT,
  correct_answer TEXT NOT NULL,
  explanation TEXT,
  points INTEGER NOT NULL DEFAULT 1,
  order_index INTEGER NOT NULL DEFAULT 0,
  tags_json TEXT,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  client_id TEXT NOT NULL DEFAULT 'unknown',
  version INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz_id ON quiz_questions(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_deleted ON quiz_questions(deleted);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_order ON quiz_questions(quiz_id, order_index);

/* FTS for quiz questions */
CREATE VIRTUAL TABLE IF NOT EXISTS quiz_questions_fts
USING fts5(
  question_text, explanation,
  content='quiz_questions',
  content_rowid='id'
);

DROP TRIGGER IF EXISTS quiz_questions_ai;
DROP TRIGGER IF EXISTS quiz_questions_au;
DROP TRIGGER IF EXISTS quiz_questions_ad;

CREATE TRIGGER quiz_questions_ai
AFTER INSERT ON quiz_questions BEGIN
  INSERT INTO quiz_questions_fts(rowid, question_text, explanation)
  SELECT new.id, new.question_text, new.explanation
  WHERE new.deleted = 0;
END;

CREATE TRIGGER quiz_questions_au
AFTER UPDATE ON quiz_questions BEGIN
  INSERT INTO quiz_questions_fts(quiz_questions_fts,rowid,question_text,explanation)
  VALUES('delete',old.id,old.question_text,old.explanation);

  INSERT INTO quiz_questions_fts(rowid, question_text, explanation)
  SELECT new.id, new.question_text, new.explanation
  WHERE new.deleted = 0;
END;

CREATE TRIGGER quiz_questions_ad
AFTER DELETE ON quiz_questions BEGIN
  INSERT INTO quiz_questions_fts(quiz_questions_fts,rowid,question_text,explanation)
  VALUES('delete',old.id,old.question_text,old.explanation);
END;

/* Quiz attempts */
CREATE TABLE IF NOT EXISTS quiz_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME,
  score INTEGER,
  total_possible INTEGER NOT NULL,
  time_spent_seconds INTEGER,
  questions_snapshot TEXT,
  answers TEXT,
  client_id TEXT NOT NULL DEFAULT 'unknown'
);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_quiz_id ON quiz_attempts(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_completed_at ON quiz_attempts(completed_at);

UPDATE db_schema_version
   SET version = 12
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 12;
"""

    # --- Migration: V12 -> V13 (Message metadata) ---
    _MIGRATION_SQL_V12_TO_V13 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 13 - Message metadata (2026-01-07)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS message_metadata(
  message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
  tool_calls_json TEXT,
  extra_json TEXT,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

UPDATE db_schema_version
   SET version = 13
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 13;
"""

    # --- Migration: V13 -> V14 (Chat topic metadata + clusters + flashcard backlinks) ---
    _MIGRATION_SQL_V13_TO_V14 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 14 - Chat topic metadata + clusters (2026-01-20)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

/* Conversations: topic tagging metadata */
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS topic_label_source TEXT CHECK(topic_label_source IN ('manual','auto'));
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS topic_last_tagged_at DATETIME;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS topic_last_tagged_message_id TEXT;

/* Cluster metadata */
CREATE TABLE IF NOT EXISTS conversation_clusters(
  cluster_id TEXT PRIMARY KEY,
  title TEXT,
  centroid TEXT,
  size INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

/* Helpful indexes */
CREATE INDEX IF NOT EXISTS idx_conversations_source_external_ref ON conversations(source, external_ref);

/* Flashcards: backlinks to conversations/messages */
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS message_id TEXT REFERENCES messages(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_flashcards_conversation ON flashcards(conversation_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_message ON flashcards(message_id);

UPDATE db_schema_version
   SET version = 14
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 14;
"""

    # --- Migration: V14 -> V15 (Writing Playground persistence) ---
    _MIGRATION_SQL_V14_TO_V15 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 15 - Writing Playground persistence (2026-02-10)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS writing_sessions(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  schema_version INTEGER NOT NULL DEFAULT 1,
  version_parent_id TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  client_id TEXT NOT NULL DEFAULT 'unknown',
  version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_writing_sessions_deleted ON writing_sessions(deleted);
CREATE INDEX IF NOT EXISTS idx_writing_sessions_last_modified ON writing_sessions(last_modified);
CREATE INDEX IF NOT EXISTS idx_writing_sessions_name ON writing_sessions(name);

CREATE TABLE IF NOT EXISTS writing_templates(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  payload_json TEXT NOT NULL,
  schema_version INTEGER NOT NULL DEFAULT 1,
  version_parent_id TEXT,
  is_default BOOLEAN NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  client_id TEXT NOT NULL DEFAULT 'unknown',
  version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_writing_templates_deleted ON writing_templates(deleted);
CREATE INDEX IF NOT EXISTS idx_writing_templates_last_modified ON writing_templates(last_modified);

CREATE TABLE IF NOT EXISTS writing_themes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  class_name TEXT,
  css TEXT,
  schema_version INTEGER NOT NULL DEFAULT 1,
  version_parent_id TEXT,
  is_default BOOLEAN NOT NULL DEFAULT 0,
  order_index INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  client_id TEXT NOT NULL DEFAULT 'unknown',
  version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_writing_themes_deleted ON writing_themes(deleted);
CREATE INDEX IF NOT EXISTS idx_writing_themes_last_modified ON writing_themes(last_modified);
CREATE INDEX IF NOT EXISTS idx_writing_themes_order ON writing_themes(order_index);

DROP TRIGGER IF EXISTS writing_sessions_sync_create;
DROP TRIGGER IF EXISTS writing_sessions_sync_update;
DROP TRIGGER IF EXISTS writing_sessions_sync_delete;
DROP TRIGGER IF EXISTS writing_sessions_sync_undelete;

CREATE TRIGGER writing_sessions_sync_create
AFTER INSERT ON writing_sessions BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_sessions',NEW.id,'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'payload_json',NEW.payload_json,
                     'schema_version',NEW.schema_version,'version_parent_id',NEW.version_parent_id,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER writing_sessions_sync_update
AFTER UPDATE ON writing_sessions
WHEN OLD.deleted = NEW.deleted AND (
     OLD.name IS NOT NEW.name OR
     OLD.payload_json IS NOT NEW.payload_json OR
     OLD.schema_version IS NOT NEW.schema_version OR
     OLD.version_parent_id IS NOT NEW.version_parent_id OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_sessions',NEW.id,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'payload_json',NEW.payload_json,
                     'schema_version',NEW.schema_version,'version_parent_id',NEW.version_parent_id,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER writing_sessions_sync_delete
AFTER UPDATE ON writing_sessions
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_sessions',NEW.id,'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER writing_sessions_sync_undelete
AFTER UPDATE ON writing_sessions
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_sessions',NEW.id,'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'payload_json',NEW.payload_json,
                     'schema_version',NEW.schema_version,'version_parent_id',NEW.version_parent_id,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

DROP TRIGGER IF EXISTS writing_templates_sync_create;
DROP TRIGGER IF EXISTS writing_templates_sync_update;
DROP TRIGGER IF EXISTS writing_templates_sync_delete;
DROP TRIGGER IF EXISTS writing_templates_sync_undelete;

CREATE TRIGGER writing_templates_sync_create
AFTER INSERT ON writing_templates BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_templates',CAST(NEW.id AS TEXT),'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'payload_json',NEW.payload_json,
                     'schema_version',NEW.schema_version,'version_parent_id',NEW.version_parent_id,
                     'is_default',NEW.is_default,'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER writing_templates_sync_update
AFTER UPDATE ON writing_templates
WHEN OLD.deleted = NEW.deleted AND (
     OLD.name IS NOT NEW.name OR
     OLD.payload_json IS NOT NEW.payload_json OR
     OLD.schema_version IS NOT NEW.schema_version OR
     OLD.version_parent_id IS NOT NEW.version_parent_id OR
     OLD.is_default IS NOT NEW.is_default OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_templates',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'payload_json',NEW.payload_json,
                     'schema_version',NEW.schema_version,'version_parent_id',NEW.version_parent_id,
                     'is_default',NEW.is_default,'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER writing_templates_sync_delete
AFTER UPDATE ON writing_templates
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_templates',CAST(NEW.id AS TEXT),'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER writing_templates_sync_undelete
AFTER UPDATE ON writing_templates
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_templates',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'payload_json',NEW.payload_json,
                     'schema_version',NEW.schema_version,'version_parent_id',NEW.version_parent_id,
                     'is_default',NEW.is_default,'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

DROP TRIGGER IF EXISTS writing_themes_sync_create;
DROP TRIGGER IF EXISTS writing_themes_sync_update;
DROP TRIGGER IF EXISTS writing_themes_sync_delete;
DROP TRIGGER IF EXISTS writing_themes_sync_undelete;

CREATE TRIGGER writing_themes_sync_create
AFTER INSERT ON writing_themes BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_themes',CAST(NEW.id AS TEXT),'create',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'class_name',NEW.class_name,'css',NEW.css,
                     'schema_version',NEW.schema_version,'version_parent_id',NEW.version_parent_id,
                     'is_default',NEW.is_default,'order_index',NEW.order_index,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER writing_themes_sync_update
AFTER UPDATE ON writing_themes
WHEN OLD.deleted = NEW.deleted AND (
     OLD.name IS NOT NEW.name OR
     OLD.class_name IS NOT NEW.class_name OR
     OLD.css IS NOT NEW.css OR
     OLD.schema_version IS NOT NEW.schema_version OR
     OLD.version_parent_id IS NOT NEW.version_parent_id OR
     OLD.is_default IS NOT NEW.is_default OR
     OLD.order_index IS NOT NEW.order_index OR
     OLD.last_modified IS NOT NEW.last_modified OR
     OLD.version IS NOT NEW.version)
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_themes',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'class_name',NEW.class_name,'css',NEW.css,
                     'schema_version',NEW.schema_version,'version_parent_id',NEW.version_parent_id,
                     'is_default',NEW.is_default,'order_index',NEW.order_index,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

CREATE TRIGGER writing_themes_sync_delete
AFTER UPDATE ON writing_themes
WHEN OLD.deleted = 0 AND NEW.deleted = 1
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_themes',CAST(NEW.id AS TEXT),'delete',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'deleted',NEW.deleted,'last_modified',NEW.last_modified,
                     'version',NEW.version,'client_id',NEW.client_id));
END;

CREATE TRIGGER writing_themes_sync_undelete
AFTER UPDATE ON writing_themes
WHEN OLD.deleted = 1 AND NEW.deleted = 0
BEGIN
  INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
  VALUES('writing_themes',CAST(NEW.id AS TEXT),'update',NEW.last_modified,NEW.client_id,NEW.version,
         json_object('id',NEW.id,'name',NEW.name,'class_name',NEW.class_name,'css',NEW.css,
                     'schema_version',NEW.schema_version,'version_parent_id',NEW.version_parent_id,
                     'is_default',NEW.is_default,'order_index',NEW.order_index,
                     'created_at',NEW.created_at,'last_modified',NEW.last_modified,
                     'deleted',NEW.deleted,'client_id',NEW.client_id,'version',NEW.version));
END;

UPDATE db_schema_version
   SET version = 15
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 15;
"""

    # --- Migration: V15 -> V16 (Writing Wordclouds) ---
    _MIGRATION_SQL_V15_TO_V16 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 16 - Writing Wordclouds (2026-01-24)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS writing_wordclouds(
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'queued',
  options_json TEXT NOT NULL,
  words_json TEXT,
  meta_json TEXT,
  error TEXT,
  input_chars INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  client_id TEXT NOT NULL DEFAULT 'unknown'
);
CREATE INDEX IF NOT EXISTS idx_writing_wordclouds_status ON writing_wordclouds(status);
CREATE INDEX IF NOT EXISTS idx_writing_wordclouds_last_modified ON writing_wordclouds(last_modified);

UPDATE db_schema_version
   SET version = 16
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 16;
"""

    # --- Migration: V16 -> V17 (Workspace tag for quizzes) ---
    _MIGRATION_SQL_V16_TO_V17 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 17 - Quizzes workspace_tag (2026-02-18)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS workspace_tag TEXT;
CREATE INDEX IF NOT EXISTS idx_quizzes_workspace_tag ON quizzes(workspace_tag);

UPDATE db_schema_version
   SET version = 17
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 17;
"""

    _MIGRATION_SQL_V17_TO_V18 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 18 - Voice Assistant Tables (2026-01-26)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

-- Voice Commands: User-defined voice command triggers
CREATE TABLE IF NOT EXISTS voice_commands (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    phrases TEXT NOT NULL,        -- JSON array of trigger phrases
    action_type TEXT NOT NULL,    -- mcp_tool|workflow|custom|llm_chat
    action_config TEXT NOT NULL,  -- JSON configuration
    priority INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    requires_confirmation INTEGER DEFAULT 0,
    description TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_voice_commands_user_id ON voice_commands(user_id);
CREATE INDEX IF NOT EXISTS idx_voice_commands_enabled ON voice_commands(enabled, deleted);

-- Voice Sessions: Track voice assistant session state
CREATE TABLE IF NOT EXISTS voice_sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    state TEXT NOT NULL DEFAULT 'idle',  -- idle|listening|processing|speaking|awaiting_confirmation|error
    context TEXT,                 -- JSON session context
    conversation_history TEXT,    -- JSON array of turns
    pending_intent TEXT,          -- JSON pending intent awaiting confirmation
    last_action_result TEXT,      -- JSON last action result
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_voice_sessions_user_id ON voice_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_last_activity ON voice_sessions(last_activity);

-- Sync log triggers for voice_commands
DROP TRIGGER IF EXISTS voice_commands_insert_sync;
DROP TRIGGER IF EXISTS voice_commands_update_sync;

CREATE TRIGGER IF NOT EXISTS voice_commands_insert_sync
AFTER INSERT ON voice_commands
BEGIN
    INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
    VALUES(
        'voice_commands',
        NEW.id,
        'create',
        NEW.created_at,
        'system',
        1,
        json_object(
            'id',NEW.id,
            'user_id',NEW.user_id,
            'name',NEW.name,
            'phrases',NEW.phrases,
            'action_type',NEW.action_type,
            'action_config',NEW.action_config,
            'priority',NEW.priority,
            'enabled',NEW.enabled,
            'requires_confirmation',NEW.requires_confirmation,
            'description',NEW.description,
            'created_at',NEW.created_at,
            'updated_at',NEW.updated_at,
            'deleted',NEW.deleted
        )
    );
END;

CREATE TRIGGER IF NOT EXISTS voice_commands_update_sync
AFTER UPDATE ON voice_commands
BEGIN
    INSERT INTO sync_log(entity,entity_id,operation,timestamp,client_id,version,payload)
    VALUES(
        'voice_commands',
        NEW.id,
        'update',
        NEW.updated_at,
        'system',
        1,
        json_object(
            'id',NEW.id,
            'user_id',NEW.user_id,
            'name',NEW.name,
            'phrases',NEW.phrases,
            'action_type',NEW.action_type,
            'action_config',NEW.action_config,
            'priority',NEW.priority,
            'enabled',NEW.enabled,
            'requires_confirmation',NEW.requires_confirmation,
            'description',NEW.description,
            'created_at',NEW.created_at,
            'updated_at',NEW.updated_at,
            'deleted',NEW.deleted
        )
    );
END;

UPDATE db_schema_version
   SET version = 18
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 18;
"""

    _MIGRATION_SQL_V18_TO_V19 = """
/*───────────────────────────────────────────────────────────────
  Migration to Version 19 - Voice Assistant Analytics (2026-01-27)
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

-- Voice Command Events: Track usage for analytics
CREATE TABLE IF NOT EXISTS voice_command_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id TEXT,
    command_name TEXT,
    user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    success INTEGER DEFAULT 1,
    response_time_ms REAL,
    session_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_voice_command_events_user_time
    ON voice_command_events(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_voice_command_events_command_time
    ON voice_command_events(command_id, created_at);

UPDATE db_schema_version
   SET version = 19
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 19;
"""

    _MIGRATION_SQL_V10_TO_V11_POSTGRES = """
ALTER TABLE messages ALTER COLUMN content DROP NOT NULL;
"""

    def __init__(
        self,
        db_path: Union[str, Path],
        client_id: str,
        *,
        backend: DatabaseBackend | None = None,
        config: ConfigParser | None = None,
    ):
        """
        Initializes the CharactersRAGDB instance.

        Sets up the database path, client ID, and ensures the schema is
        initialized or migrated to the current version (_CURRENT_SCHEMA_VERSION).

        Args:
            db_path: Path to the SQLite database file (e.g., "data/app.db")
                     or ":memory:" for an in-memory database.
            client_id: A unique identifier for this client instance. Used for
                       tracking changes in the sync log and records. Must not be empty.

        Raises:
            ValueError: If `client_id` is empty or None.
            CharactersRAGDBError: If database directory creation fails, or if
                                  database initialization/schema setup encounters
                                  a critical error.
            SchemaError: If schema migration or versioning issues occur.
        """
        if isinstance(db_path, Path):
            resolved_path = db_path.resolve()
            is_memory = False
        else:
            is_memory = db_path == ':memory:'
            resolved_path = Path(db_path).resolve() if not is_memory else Path(":memory:")

        self.is_memory_db = is_memory
        self.db_path = resolved_path
        self.db_path_str = ':memory:' if self.is_memory_db else str(self.db_path)

        if not client_id:
            raise ValueError("Client ID cannot be empty or None.")
        self.client_id = client_id

        self.backend = self._resolve_backend(backend=backend, config=config)
        self.backend_type = self.backend.backend_type

        if self.backend_type != BackendType.SQLITE:
            self.is_memory_db = False

        if self.backend_type == BackendType.SQLITE and not self.is_memory_db:
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise CharactersRAGDBError(
                    f"Failed to create database directory {self.db_path.parent}: {e}"
                ) from e

        logger.info(
            f"Initializing CharactersRAGDB for path: {self.db_path_str} "
            f"[Client ID: {self.client_id}] (backend={self.backend_type.value})"
        )
        self._local = threading.local()
        self._schema_lock = threading.RLock()
        try:
            self._initialize_schema()
            logger.debug(f"CharactersRAGDB initialization completed successfully for {self.db_path_str}")
        except (CharactersRAGDBError, sqlite3.Error) as e:
            logger.critical(f"FATAL: DB Initialization failed for {self.db_path_str}: {e}", exc_info=True)
            self.close_connection()  # Attempt to clean up
            raise CharactersRAGDBError(f"Database initialization failed: {e}") from e
        except Exception as e:
            logger.critical(f"FATAL: Unexpected error during DB Initialization for {self.db_path_str}: {e}",
                            exc_info=True)
            self.close_connection()
            raise CharactersRAGDBError(f"Unexpected database initialization error: {e}") from e

    # --- Backend Resolution Helpers ---
    def _resolve_backend(
        self,
        *,
        backend: DatabaseBackend | None,
        config: ConfigParser | None,
    ) -> DatabaseBackend:
        """Select the database backend instance for this content store."""
        if backend is not None:
            return backend

        parser: ConfigParser | None = config
        if parser is None:
            try:
                parser = load_comprehensive_config()
            except Exception:
                parser = None

        if parser is not None:
            candidate = get_content_backend(parser)
            if candidate and candidate.backend_type == BackendType.POSTGRESQL:
                return candidate

        fallback_config = DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=self.db_path_str,
        )
        return DatabaseBackendFactory.create_backend(fallback_config)


    def _prepare_backend_statement(
        self,
        query: str,
        params: Optional[Union[Tuple, List, Dict]] = None,
    ) -> Tuple[str, Optional[Union[Tuple, Dict]]]:
        return prepare_backend_statement(
            self.backend_type,
            query,
            params,
            transformer=self._transform_query_for_backend
            if self.backend_type == BackendType.POSTGRESQL
            else None,
            ensure_returning=False,
        )

    def _prepare_backend_many_statement(
        self,
        query: str,
        params_list: List[Union[Tuple, List, Dict]],
    ) -> Tuple[str, List[Union[Tuple, Dict]]]:
        converted_query, prepared_params = prepare_backend_many_statement(
            self.backend_type,
            query,
            params_list,
            transformer=self._transform_query_for_backend
            if self.backend_type == BackendType.POSTGRESQL
            else None,
            ensure_returning=False,
        )
        return converted_query, prepared_params

    def _normalise_params(
        self,
        params: Optional[Union[List, Tuple, Dict, Any]],
    ) -> Optional[Union[Tuple, Dict]]:
        return normalise_params(params)

    def _transform_query_for_backend(self, query: str) -> str:
        if self.backend_type != BackendType.POSTGRESQL:
            return query
        return transform_sqlite_query_for_postgres(query)


    def _open_new_connection(self):
        try:
            pool = self.backend.get_pool()
            conn = pool.get_connection()
            # Apply per-tenant session guard for PostgreSQL (RLS via current_setting('app.current_user_id'))
            if self.backend_type == BackendType.POSTGRESQL and self.client_id:
                conn = self._apply_postgres_client_scope(conn, pool)
            return conn
        except BackendDatabaseError as exc:
            raise CharactersRAGDBError(f"Failed to acquire database connection: {exc}") from exc

    def _apply_postgres_client_scope(self, conn, pool):
        """Best-effort helper to set session-scoped client_id in PostgreSQL.

        Ensures failed SET/COMMIT attempts do not leave pooled connections in a
        broken transaction state by rolling back (or replacing) the connection.
        """
        user_value = str(self.client_id)

        def _set_session(target) -> None:
            cur = target.cursor()
            if psycopg_sql is not None:  # type: ignore[name-defined]
                statement = psycopg_sql.SQL(
                    "SELECT set_config('app.current_user_id', {}, false)"
                ).format(psycopg_sql.Literal(user_value))
                cur.execute(statement)
            else:
                cur.execute(
                    "SELECT set_config('app.current_user_id', %s, false)",
                    (user_value,),
                )

        def _replace_connection(bad_conn) -> Any:
            try:
                bad_conn.close()
            except Exception:
                pass
            try:
                pool.return_connection(bad_conn)
            except Exception:
                pass
            return pool.get_connection()

        def _safe_rollback(target, context: str) -> bool:
            try:
                target.rollback()
                return True
            except Exception as rollback_exc:  # noqa: BLE001
                logger.warning(
                    "Rollback failed after %s while setting PostgreSQL session scope: %s",
                    context,
                    rollback_exc,
                )
                return False

        try:
            _set_session(conn)
            try:
                conn.commit()
            except Exception as commit_exc:  # noqa: BLE001
                logger.warning(
                    "Commit failed after setting PostgreSQL session scope; attempting rollback: %s",
                    commit_exc,
                )
                if not _safe_rollback(conn, "commit failure"):
                    conn = _replace_connection(conn)
                    try:
                        _set_session(conn)
                        conn.commit()
                    except Exception as retry_exc:  # noqa: BLE001
                        logger.warning(
                            "Retrying PostgreSQL session scope setup failed: %s",
                            retry_exc,
                        )
                        _safe_rollback(conn, "retry failure")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to set PostgreSQL session scope; attempting rollback: %s",
                exc,
            )
            if not _safe_rollback(conn, "SET failure"):
                conn = _replace_connection(conn)
                try:
                    _set_session(conn)
                    conn.commit()
                except Exception as retry_exc:  # noqa: BLE001
                    logger.warning(
                        "Retrying PostgreSQL session scope setup failed: %s",
                        retry_exc,
                    )
                    _safe_rollback(conn, "retry failure")
        return conn

    def _release_connection(self, connection) -> None:
        try:
            if self.backend_type == BackendType.SQLITE:
                thread_id = threading.get_ident()
                try:
                    pool = self.backend.get_pool()
                    pool._connections[thread_id] = None  # type: ignore[attr-defined]
                    if hasattr(pool._local, 'connection'):  # type: ignore[attr-defined]
                        pool._local.connection = None  # type: ignore[attr-defined]
                except AttributeError:
                    pass
                try:
                    connection.close()
                except sqlite3.Error:
                    pass
            else:
                self.backend.get_pool().return_connection(connection)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error while releasing connection: %s", exc)

    def _ensure_sqlite_backend(self) -> None:
        if self.backend_type != BackendType.SQLITE:
            return

    # --- Connection Management ---
    def _get_thread_connection(self) -> Any:
        """
        Retrieve (or open) the thread-local connection for the configured backend.

        For SQLite we maintain a single `sqlite3.Connection` per thread and ensure it
        stays usable (re-opening on failure). For PostgreSQL we borrow a pooled
        connection and cache it per thread until explicitly released.

        Returns:
            Backend-specific connection handle suitable for use with
            :class:`BackendConnectionWrapper`.

        Raises:
            CharactersRAGDBError: If acquiring a connection from the backend fails.
        """
        conn = getattr(self._local, 'conn', None)

        if self.backend_type == BackendType.SQLITE:
            pool = self.backend.get_pool()
            if conn is not None:
                try:
                    conn.execute("SELECT 1")
                    return conn
                except (sqlite3.ProgrammingError, sqlite3.OperationalError):
                    logger.warning(
                        "Thread-local connection for %s was closed or became unusable. Reopening.",
                        self.db_path_str,
                    )
                    try:
                        conn.close()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to close database connection: %s", exc)
                    try:
                        # Prefer public helper to clear thread-local connection state
                        if hasattr(pool, 'clear_thread_local_connection'):
                            pool.clear_thread_local_connection()  # type: ignore[attr-defined]
                    except Exception:
                        # Best-effort; ignore if pool doesn't expose the helper
                        pass
                    conn = None
                    self._local.conn = None

            if conn is None:
                conn = self._open_new_connection()
                self._local.conn = conn
                logger.debug(
                    "Opened/Reopened SQLite connection to %s for thread %s",
                    self.db_path_str,
                    threading.get_ident(),
                )
            return conn

        # Non-SQLite backend: reuse connection if still open, otherwise borrow anew.
        if conn is not None and getattr(conn, "closed", False):
            self._release_connection(conn)
            conn = None
            self._local.conn = None

        if conn is None:
            conn = self._open_new_connection()
            self._local.conn = conn
            logger.debug(
                "Acquired backend connection (%s) for thread %s",
                self.backend_type.value,
                threading.get_ident(),
            )
        return conn

    def get_connection(self) -> Any:
        """Return the active connection wrapper for the current thread."""
        raw_conn = self._get_thread_connection()
        if self.backend_type == BackendType.SQLITE:
            return raw_conn
        return BackendConnectionWrapper(self, raw_conn)

    def close_connection(self):
        """
        Closes the current thread's database connection.

        If the database is file-based and in WAL mode, it attempts to perform
        a WAL checkpoint (TRUNCATE) before closing to commit changes from the WAL file
        to the main database file.
        If a transaction is active and uncommitted on this connection, it attempts a rollback.
        Clears the connection reference from `threading.local` for the current thread.
        """
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            return

        try:
            if self.backend_type == BackendType.SQLITE:
                if not self.is_memory_db:
                    if conn.in_transaction:
                        try:
                            logger.warning(
                                "Connection to %s is in an uncommitted transaction during close. Attempting rollback.",
                                self.db_path_str,
                            )
                            conn.rollback()
                        except sqlite3.Error as rb_err:
                            logger.error(
                                "Rollback attempt during close for %s failed: %s",
                                self.db_path_str,
                                rb_err,
                            )

                    if not conn.in_transaction:
                        mode_row = conn.execute("PRAGMA journal_mode;").fetchone()
                        if mode_row and mode_row[0].lower() == 'wal':
                            try:
                                logger.debug(
                                    "Attempting WAL checkpoint (TRUNCATE) before closing %s on thread %s.",
                                    self.db_path_str,
                                    threading.get_ident(),
                                )
                                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                                logger.debug("WAL checkpoint TRUNCATE executed for %s.", self.db_path_str)
                            except sqlite3.Error as cp_err:
                                logger.warning("WAL checkpoint failed for %s: %s", self.db_path_str, cp_err)

                conn.close()
                logger.debug(
                    "Closed SQLite connection for thread %s to %s.",
                    threading.get_ident(),
                    self.db_path_str,
                )
            else:
                self.backend.get_pool().return_connection(conn)
                logger.debug(
                    "Returned backend connection (%s) for thread %s.",
                    self.backend_type.value,
                    threading.get_ident(),
                )
        except sqlite3.Error as exc:
            logger.warning(
                "Error during SQLite connection close/checkpoint for %s on thread %s: %s",
                self.db_path_str,
                threading.get_ident(),
                exc,
            )
        finally:
            if hasattr(self._local, 'conn'):
                self._local.conn = None
            if self.backend_type == BackendType.SQLITE:
                try:
                    pool = self.backend.get_pool()
                    if hasattr(pool, 'clear_thread_local_connection'):
                        pool.clear_thread_local_connection()  # type: ignore[attr-defined]
                except Exception:
                    pass

    def close_all_connections(self) -> None:
        """
        Force-close all backend connections managed by this instance.

        Primarily used in tests/shutdown to ensure no background SQLite threads remain.
        """
        try:
            pool = self.backend.get_pool()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to retrieve backend pool while closing connections: %s", exc)
            pool = None

        if self.backend_type == BackendType.SQLITE and pool is not None:
            close_all = getattr(pool, "close_all", None)
            if callable(close_all):
                try:
                    close_all()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Error closing all SQLite connections for %s: %s", self.db_path_str, exc)
        elif pool is not None:
            try:
                pool.close_all()
            except AttributeError:
                pass
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error closing all backend connections for %s: %s", self.db_path_str, exc)

        # Reset thread-local reference regardless of backend
        try:
            self._local = threading.local()
        except Exception:
            pass

    def backup_database(self, backup_file_path: str) -> bool:
        """
        Creates a backup of the current database to the specified file path.

        Args:
            backup_file_path (str): The path to save the backup database file.

        Returns:
            bool: True if the backup was successful, False otherwise.
        """
        logger.info(f"Starting database backup from '{self.db_path_str}' to '{backup_file_path}'")
        # src_conn is managed by get_connection and should not be closed by this method directly
        # backup_conn is local to this method and must be closed
        backup_conn: Optional[sqlite3.Connection] = None
        try:
            # Ensure the backup file path is not the same as the source for file-based DBs
            if not self.is_memory_db and self.db_path.resolve() == Path(backup_file_path).resolve():
                logger.error("Backup path cannot be the same as the source database path.")
                raise ValueError("Backup path cannot be the same as the source database path.")

            src_conn = self.get_connection()

            # Ensure parent directory for backup_file_path exists
            backup_db_path_obj = Path(backup_file_path)
            backup_db_path_obj.parent.mkdir(parents=True, exist_ok=True)

            backup_conn = sqlite3.connect(str(backup_db_path_obj)) # Use string path for connect

            logger.debug(f"Source DB connection: {src_conn}")
            logger.debug(f"Backup DB connection: {backup_conn} to file {str(backup_db_path_obj)}")

            # Perform the backup
            src_conn.backup(backup_conn, pages=0, progress=None)

            logger.info(f"Database backup successful from '{self.db_path_str}' to '{str(backup_db_path_obj)}'")
            return True
        except ValueError as ve: # Catch specific ValueError for path mismatch first
            logger.error(f"ValueError during database backup: {ve}", exc_info=True)
            return False
        except sqlite3.Error as e:
            logger.error(f"SQLite error during database backup: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error during database backup: {e}", exc_info=True)
            return False
        finally:
            if backup_conn:
                try:
                    backup_conn.close()
                    logger.debug("Closed backup database connection.")
                except sqlite3.Error as e:
                    logger.warning(f"Error closing backup database connection: {e}")
            # Source connection (src_conn) is managed by the thread-local mechanism
            # and should not be closed here to allow continued use of the DB instance.

    # --- Query Execution ---
    def execute_query(
        self,
        query: str,
        params: Optional[Union[tuple, Dict[str, Any]]] = None,
        *,
        commit: bool = False,
        script: bool = False,
    ) -> Any:
        """
        Executes a single SQL query or an entire SQL script.

        Args:
            query: The SQL query string or script.
            params: Optional parameters for the query (tuple or dict).
                    Not used if `script` is True. Defaults to None.
            commit: If True, and not within an explicit transaction context managed
                    by `with db.transaction():`, commits the transaction after execution.
                    Defaults to False.
            script: If True, executes the query string as an SQL script using `executescript`.
                    `params` are ignored if `script` is True. Defaults to False.

        Returns:
            The sqlite3.Cursor object after execution.

        Raises:
            ConflictError: If an SQLite IntegrityError due to a "unique constraint failed" occurs.
            CharactersRAGDBError: For other SQLite errors or general query execution failures.
        """
        conn = self.get_connection()
        try:
            logger.debug(
                "Executing SQL (script=%s, backend=%s): %s... Params: %s...",
                script,
                self.backend_type.value,
                query[:300],
                str(params)[:200],
            )

            if script:
                cursor = conn.executescript(query)
            else:
                prepared_query, prepared_params = self._prepare_backend_statement(query, params)
                cursor = conn.cursor()
                cursor.execute(prepared_query, prepared_params or ())

            if commit:
                try:
                    if self.backend_type == BackendType.SQLITE:
                        if not conn.in_transaction:
                            conn.commit()
                            logger.debug("Committed directly by execute_query.")
                    else:
                        conn.commit()
                except Exception as exc:
                    logger.error(
                        "Commit failed after execute_query on backend %s: %s",
                        self.backend_type.value,
                        exc,
                        exc_info=True,
                    )
                    raise CharactersRAGDBError(f"Database commit failed: {exc}") from exc
            return cursor
        except sqlite3.IntegrityError as e:
            logger.warning(f"Integrity constraint violation: {query[:300]}... Error: {e}")
            # Distinguish unique constraint from other integrity errors if possible
            if "unique constraint failed" in str(e).lower():
                raise ConflictError(message=f"Unique constraint violation: {e}") from e
            raise CharactersRAGDBError(
                f"Database constraint violation: {e}") from e  # Broader for other integrity issues
        except sqlite3.Error as e:
            logger.error(f"Query execution failed: {query[:300]}... Error: {e}", exc_info=True)
            raise CharactersRAGDBError(f"Query execution failed: {e}") from e
        except BackendDatabaseError as exc:
            msg = str(exc).lower()
            if "duplicate key" in msg or "unique constraint" in msg:
                raise ConflictError(message=f"Database constraint violation: {exc}") from exc
            logger.error(
                "Backend query execution failed (%s): %s",
                self.backend_type.value,
                exc,
                exc_info=True,
            )
            raise CharactersRAGDBError(f"Query execution failed: {exc}") from exc

    def execute_many(
        self,
        query: str,
        params_list: List[tuple],
        *,
        commit: bool = False,
    ) -> Optional[Any]:
        """
        Executes a parameterized SQL query multiple times with a list of parameter sets.

        Args:
            query: The SQL query string.
            params_list: A list of tuples, where each tuple contains parameters for one execution.
                         If empty or invalid, the method returns None without executing.
            commit: If True, and not within an explicit transaction context,
                    commits the transaction after execution. Defaults to False.

        Returns:
            The sqlite3.Cursor object after execution, or None if params_list is empty/invalid.

        Raises:
            ConflictError: If an SQLite IntegrityError due to a "unique constraint failed" occurs during batch.
            CharactersRAGDBError: For other SQLite errors or general batch execution failures.
        """
        conn = self.get_connection()
        if not isinstance(params_list, list) or not params_list:
            logger.debug("execute_many called with empty or invalid params_list.")
            return None
        try:
            logger.debug(
                "Executing Many on backend %s: %s... with %d sets.",
                self.backend_type.value,
                query[:150],
                len(params_list),
            )
            prepared_query, prepared_params_list = self._prepare_backend_many_statement(query, params_list)
            cursor = conn.cursor()
            cursor.executemany(prepared_query, prepared_params_list)
            if commit:
                try:
                    if self.backend_type == BackendType.SQLITE:
                        if not conn.in_transaction:
                            conn.commit()
                            logger.debug("Committed Many directly by execute_many.")
                    else:
                        conn.commit()
                except Exception as exc:
                    logger.error(
                        "Commit failed after execute_many on backend %s: %s",
                        self.backend_type.value,
                        exc,
                        exc_info=True,
                    )
                    raise CharactersRAGDBError(f"Database commit failed: {exc}") from exc
            return cursor
        except sqlite3.IntegrityError as e:
            logger.warning(f"Integrity constraint violation during batch: {query[:150]}... Error: {e}")
            if "unique constraint failed" in str(e).lower():
                raise ConflictError(message=f"Unique constraint violation during batch: {e}") from e
            raise CharactersRAGDBError(f"Database constraint violation during batch: {e}") from e
        except sqlite3.Error as e:
            logger.error(f"Execute Many failed: {query[:150]}... Error: {e}", exc_info=True)
            raise CharactersRAGDBError(f"Execute Many failed: {e}") from e
        except BackendDatabaseError as exc:
            msg = str(exc).lower()
            if "duplicate key" in msg or "unique constraint" in msg:
                raise ConflictError(message=f"Database constraint violation during batch: {exc}") from exc
            logger.error(
                "Backend execute_many failed (%s): %s",
                self.backend_type.value,
                exc,
                exc_info=True,
            )
            raise CharactersRAGDBError(f"Execute Many failed: {exc}") from exc

    # --- Transaction Context ---
    def transaction(self) -> Union['TransactionContextManager', BackendManagedTransaction]:
        """Return a context manager for database transactions."""
        if self.backend_type == BackendType.SQLITE:
            return TransactionContextManager(self)
        return BackendManagedTransaction(self)

    # --- Schema Initialization and Migration ---
    def _get_db_version(self, conn: sqlite3.Connection) -> int:
        """
        Retrieves the current schema version from the `db_schema_version` table
        for the schema named `self._SCHEMA_NAME`.

        Args:
            conn: The active sqlite3.Connection.

        Returns:
            The current schema version as an integer, or 0 if the table or entry
            for `self._SCHEMA_NAME` does not exist (indicating a fresh database).

        Raises:
            SchemaError: If there is an unexpected SQL error while querying the version,
                         other than "no such table".
        """
        try:
            cursor = conn.execute("SELECT version FROM db_schema_version WHERE schema_name = ? LIMIT 1",
                                  (self._SCHEMA_NAME,))
            result = cursor.fetchone()
            return result['version'] if result else 0
        except sqlite3.Error as e:
            if "no such table" in str(e).lower() and "db_schema_version" in str(e).lower():
                return 0
            logger.error(f"Could not determine database schema version for '{self._SCHEMA_NAME}': {e}", exc_info=True)
            raise SchemaError(f"Could not determine schema version for '{self._SCHEMA_NAME}': {e}") from e
        except BackendDatabaseError as e:
            if "does not exist" in str(e).lower():
                return 0
            logger.error(
                "Could not determine database schema version for '%s' (backend %s): %s",
                self._SCHEMA_NAME,
                self.backend_type.value,
                e,
                exc_info=True,
            )
            raise SchemaError(
                f"Could not determine schema version for '{self._SCHEMA_NAME}': {e}"
            ) from e

    def _apply_schema_v4(self, conn: sqlite3.Connection):
        """
        Applies the full SQL schema for Version 4.

        This method executes the `_FULL_SCHEMA_SQL_V4` script, which defines
        all tables, FTS tables, triggers, and updates the schema version record in
        `db_schema_version` to 4.

        Args:
            conn: The active sqlite3.Connection. The operations are performed
                  within the transaction context managed by the caller (e.g., `_initialize_schema`).

        Raises:
            SchemaError: If the schema script execution fails or the version
                         is not correctly updated to 4 in `db_schema_version`.
        """
        logger.info(f"Applying schema Version 4 for '{self._SCHEMA_NAME}' to DB: {self.db_path_str}...")
        try:
            # Using conn.executescript directly as it manages its own transaction
            conn.executescript(self._FULL_SCHEMA_SQL_V4)
            logger.debug(f"[{self._SCHEMA_NAME} V4] Full schema script executed.")

            final_version = self._get_db_version(conn)
            if final_version != 4:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME} V4] Schema version update check failed. Expected 4, got: {final_version}")
            logger.info(f"[{self._SCHEMA_NAME} V4] Schema 4 applied and version confirmed for DB: {self.db_path_str}.")
        except sqlite3.OperationalError as e:
            # Compatibility repair path: if an older pre-versioned DB already has a
            # sync_log table without the 'entity_id' column, CREATE INDEX on
            # (entity, entity_id) will fail. Attempt to add the column, then rerun.
            if "no such column: entity_id" in str(e).lower():
                try:
                    # Detect existing sync_log definition
                    try:
                        rows = conn.execute("PRAGMA table_info(sync_log)").fetchall()
                    except sqlite3.Error:
                        rows = []
                    col_names = {r[1] if not isinstance(r, dict) else r.get('name') for r in rows} if rows else set()
                    if rows and ('entity_id' not in col_names):
                        logger.warning(
                            f"[{self._SCHEMA_NAME} V4] Detected legacy sync_log without 'entity_id'. Adding column for compatibility.")
                        # Add column without NOT NULL to avoid rewrite; acceptable for legacy fix
                        conn.execute("ALTER TABLE sync_log ADD COLUMN entity_id TEXT")
                    # Re-run the full schema to finish indexes/triggers idempotently
                    conn.executescript(self._FULL_SCHEMA_SQL_V4)
                    final_version = self._get_db_version(conn)
                    if final_version != 4:
                        raise SchemaError(
                            f"[{self._SCHEMA_NAME} V4] Post-repair version check failed. Expected 4, got: {final_version}")
                    logger.info(f"[{self._SCHEMA_NAME} V4] Schema 4 applied after legacy sync_log repair for DB: {self.db_path_str}.")
                    return
                except Exception as repair_err:  # noqa: BLE001
                    logger.error(
                        f"[{self._SCHEMA_NAME} V4] Repair attempt after 'entity_id' error failed: {repair_err}",
                        exc_info=True,
                    )
                    raise SchemaError(
                        f"DB schema V4 setup failed for '{self._SCHEMA_NAME}': {e}") from e
            # Any other sqlite operational error: re-raise as SchemaError
            logger.error(f"[{self._SCHEMA_NAME} V4] Schema application failed: {e}", exc_info=True)
            raise SchemaError(f"DB schema V4 setup failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME} V4] Unexpected error during schema V4 application: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error applying schema V4 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v4_to_v5(self, conn: sqlite3.Connection):
        """
        Migrates the existing database from schema version 4 to 5 (adds
        flashcards/decks/reviews and related triggers/indices).
        """
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V4 to V5 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V4_TO_V5)
            final_version = self._get_db_version(conn)
            if final_version != 5:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V4->V5 failed version check. Expected 5, got: {final_version}")
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V5 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V4->V5 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V4->V5 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V4->V5: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V5 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v5_to_v6(self, conn: sqlite3.Connection):
        """
        Migrates schema from V5 to V6 (adds model_type, extra to flashcards).
        """
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V5 to V6 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V5_TO_V6)
            final_version = self._get_db_version(conn)
            if final_version != 6:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V5->V6 failed version check. Expected 6, got: {final_version}")
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V6 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V5->V6 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V5->V6 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V5->V6: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V6 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v6_to_v7(self, conn: sqlite3.Connection):
        """Migrates schema from V6 to V7 (adds reverse flag)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V6 to V7 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V6_TO_V7)
            final_version = self._get_db_version(conn)
            if final_version != 7:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V6->V7 failed version check. Expected 7, got: {final_version}")
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V7 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V6->V7 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V6->V7 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V6->V7: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V7 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v7_to_v8(self, conn: sqlite3.Connection):
        """Migrates schema from V7 to V8 (introduces message_images table)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V7 to V8 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V7_TO_V8)
            final_version = self._get_db_version(conn)
            if final_version != 8:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V7->V8 failed version check. Expected 8, got: {final_version}")
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V8 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V7->V8 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V7->V8 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V7->V8: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V8 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v8_to_v9(self, conn: sqlite3.Connection):
        """Migrates schema from V8 to V9 (adds note_edges for manual links)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V8 to V9 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V8_TO_V9)
            final_version = self._get_db_version(conn)
            if final_version != 9:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V8->V9 failed version check. Expected 9, got: {final_version}")
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V9 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V8->V9 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V8->V9 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V8->V9: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V9 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v9_to_v10(self, conn: sqlite3.Connection):
        """Migrates schema from V9 to V10 (chat metadata + note backlinks + indexes)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V9 to V10 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V9_TO_V10)
            final_version = self._get_db_version(conn)
            if final_version != 10:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V9->V10 failed version check. Expected 10, got: {final_version}"
                )
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V10 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V9->V10 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V9->V10 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V9->V10: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V10 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v10_to_v11(self, conn: sqlite3.Connection):
        """Migrates schema from V10 to V11 (nullable message content)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V10 to V11 for DB: {self.db_path_str}...")
        try:
            # Legacy safety: ensure columns referenced by the migration exist.
            # Some older databases marked as v10 may be missing message image/ranking columns.
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info('messages')").fetchall()}
            column_additions = {
                "image_data": "BLOB",
                "image_mime_type": "TEXT",
                "ranking": "INTEGER",
            }
            for col_name, col_type in column_additions.items():
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE messages ADD COLUMN {col_name} {col_type}")
            conn.executescript(self._MIGRATION_SQL_V10_TO_V11)
            final_version = self._get_db_version(conn)
            if final_version != 11:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V10->V11 failed version check. Expected 11, got: {final_version}"
                )
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V11 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V10->V11 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V10->V11 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V10->V11: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V11 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v11_to_v12(self, conn: sqlite3.Connection):
        """Migrates schema from V11 to V12 (quizzes + attempts)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V11 to V12 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V11_TO_V12)
            final_version = self._get_db_version(conn)
            if final_version != 12:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V11->V12 failed version check. Expected 12, got: {final_version}"
                )
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V12 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V11->V12 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V11->V12 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V11->V12: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V12 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v12_to_v13(self, conn: sqlite3.Connection):
        """Migrates schema from V12 to V13 (message metadata)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V12 to V13 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V12_TO_V13)
            final_version = self._get_db_version(conn)
            if final_version != 13:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V12->V13 failed version check. Expected 13, got: {final_version}"
                )
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V13 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V12->V13 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V12->V13 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V12->V13: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V13 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v13_to_v14(self, conn: sqlite3.Connection):
        """Migrates schema from V13 to V14 (chat topic metadata + clusters + flashcard backlinks)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V13 to V14 for DB: {self.db_path_str}...")
        try:
            conn.execute("PRAGMA foreign_keys = ON")

            def _column_names(table_name: str) -> set[str]:
                rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
                names: set[str] = set()
                for row in rows:
                    if isinstance(row, dict):
                        name = row.get("name")
                    else:
                        try:
                            name = row["name"]
                        except Exception:
                            name = row[1] if len(row) > 1 else None
                    if name:
                        names.add(str(name))
                return names

            conv_cols = _column_names("conversations")
            if "topic_label_source" not in conv_cols:
                conn.execute(
                    "ALTER TABLE conversations ADD COLUMN topic_label_source TEXT CHECK(topic_label_source IN ('manual','auto'))"
                )
            if "topic_last_tagged_at" not in conv_cols:
                conn.execute("ALTER TABLE conversations ADD COLUMN topic_last_tagged_at DATETIME")
            if "topic_last_tagged_message_id" not in conv_cols:
                conn.execute("ALTER TABLE conversations ADD COLUMN topic_last_tagged_message_id TEXT")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_clusters(
                  cluster_id TEXT PRIMARY KEY,
                  title TEXT,
                  centroid TEXT,
                  size INTEGER NOT NULL DEFAULT 0,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_source_external_ref ON conversations(source, external_ref)"
            )

            flash_cols = _column_names("flashcards")
            if "conversation_id" not in flash_cols:
                conn.execute(
                    "ALTER TABLE flashcards ADD COLUMN conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL"
                )
            if "message_id" not in flash_cols:
                conn.execute(
                    "ALTER TABLE flashcards ADD COLUMN message_id TEXT REFERENCES messages(id) ON DELETE SET NULL"
                )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_conversation ON flashcards(conversation_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_message ON flashcards(message_id)")

            conn.execute(
                "UPDATE db_schema_version SET version = 14 WHERE schema_name = 'rag_char_chat_schema' AND version < 14"
            )
            final_version = self._get_db_version(conn)
            if final_version != 14:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V13->V14 failed version check. Expected 14, got: {final_version}"
                )
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V14 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V13->V14 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V13->V14 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V13->V14: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V14 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v14_to_v15(self, conn: sqlite3.Connection):
        """Migrates schema from V14 to V15 (Writing Playground persistence)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V14 to V15 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V14_TO_V15)
            final_version = self._get_db_version(conn)
            if final_version != 15:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V14->V15 failed version check. Expected 15, got: {final_version}"
                )
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V15 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V14->V15 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V14->V15 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V14->V15: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V15 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v15_to_v16(self, conn: sqlite3.Connection):
        """Migrates schema from V15 to V16 (Writing Wordclouds)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V15 to V16 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V15_TO_V16)
            final_version = self._get_db_version(conn)
            if final_version != 16:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V15->V16 failed version check. Expected 16, got: {final_version}"
                )
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V16 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V15->V16 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V15->V16 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V15->V16: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V16 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v16_to_v17(self, conn: sqlite3.Connection):
        """Migrates schema from V16 to V17 (Workspace tag for quizzes)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V16 to V17 for DB: {self.db_path_str}...")
        try:
            # quizzes.workspace_tag already exists in earlier schema versions.
            # Add column only if missing to keep migration idempotent.
            try:
                cursor = conn.execute("PRAGMA table_info(quizzes)")
                columns = {row[1] for row in cursor.fetchall()}
            except sqlite3.Error:
                columns = set()

            if "workspace_tag" not in columns:
                conn.execute("ALTER TABLE quizzes ADD COLUMN workspace_tag TEXT")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_quizzes_workspace_tag ON quizzes(workspace_tag)")
            conn.execute(
                """
                UPDATE db_schema_version
                   SET version = 17
                 WHERE schema_name = 'rag_char_chat_schema'
                   AND version < 17;
                """
            )
            final_version = self._get_db_version(conn)
            if final_version != 17:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V16->V17 failed version check. Expected 17, got: {final_version}"
                )
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V17 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V16->V17 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V16->V17 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V16->V17: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V17 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v17_to_v18(self, conn: sqlite3.Connection):
        """Migrates schema from V17 to V18 (Voice Assistant tables)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V17 to V18 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V17_TO_V18)
            final_version = self._get_db_version(conn)
            if final_version != 18:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V17->V18 failed version check. Expected 18, got: {final_version}"
                )
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V18 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V17->V18 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V17->V18 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V17->V18: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V18 for '{self._SCHEMA_NAME}': {e}") from e

    def _migrate_from_v18_to_v19(self, conn: sqlite3.Connection):
        """Migrates schema from V18 to V19 (Voice Assistant analytics)."""
        logger.info(f"Migrating '{self._SCHEMA_NAME}' schema from V18 to V19 for DB: {self.db_path_str}...")
        try:
            conn.executescript(self._MIGRATION_SQL_V18_TO_V19)
            final_version = self._get_db_version(conn)
            if final_version != 19:
                raise SchemaError(
                    f"[{self._SCHEMA_NAME}] Migration V18->V19 failed version check. Expected 19, got: {final_version}"
                )
            logger.info(f"[{self._SCHEMA_NAME}] Migration to V19 completed.")
        except sqlite3.Error as e:
            logger.error(f"[{self._SCHEMA_NAME}] Migration V18->V19 failed: {e}", exc_info=True)
            raise SchemaError(f"Migration V18->V19 failed for '{self._SCHEMA_NAME}': {e}") from e
        except SchemaError:
            raise
        except Exception as e:
            logger.error(f"[{self._SCHEMA_NAME}] Unexpected error during migration V18->V19: {e}", exc_info=True)
            raise SchemaError(f"Unexpected error migrating to V19 for '{self._SCHEMA_NAME}': {e}") from e

    def _initialize_schema(self):
        if self.backend_type == BackendType.SQLITE:
            self._initialize_schema_sqlite()
        elif self.backend_type == BackendType.POSTGRESQL:
            self._initialize_schema_postgres()
        else:
            raise NotImplementedError(
                f"Schema initialization not implemented for backend {self.backend_type}"
            )
        self._ensure_message_metadata_table()

    def ensure_character_tables_ready(self) -> None:
        """
        Ensure the core character tables exist for this database instance.

        Tests occasionally delete the underlying SQLite files while keeping the cached
        CharactersRAGDB instance alive. When a new connection is opened afterwards,
        SQLite creates a fresh, empty database which no longer has the expected schema.
        This guard re-runs schema initialization if we detect that the character_cards
        table is missing.
        """
        if not hasattr(self, "_schema_lock"):
            self._schema_lock = threading.RLock()
        with self._schema_lock:
            try:
                self.execute_query("SELECT 1 FROM character_cards LIMIT 1")
                return
            except CharactersRAGDBError as exc:
                msg = str(exc).lower()
                missing_markers = (
                    "no such table",
                    "does not exist",
                    "missing relation",
                    "undefined table",
                )
                if "character_cards" not in msg or not any(marker in msg for marker in missing_markers):
                    raise
                logger.warning(
                    "Detected missing character_cards table for %s; re-initializing schema.",
                    self.db_path_str,
                )

            # If we reach here the core table is missing; attempt to re-initialize.
            self.close_connection()
            try:
                self._initialize_schema()
            except (SchemaError, CharactersRAGDBError):
                raise

            # Verify that the table now exists; if not, escalate as SchemaError.
            try:
                self.execute_query("SELECT 1 FROM character_cards LIMIT 1")
            except CharactersRAGDBError as exc:
                logger.error(
                    "Failed to verify character_cards table after schema re-initialization for %s: %s",
                    self.db_path_str,
                    exc,
                )
                raise SchemaError(
                    "Character cards table missing after schema re-initialization."
                ) from exc

    @staticmethod
    def _is_missing_character_table_error(error: CharactersRAGDBError) -> bool:
        message = str(error).lower()
        if "character_cards" not in message:
            return False
        missing_markers = (
            "no such table",
            "does not exist",
            "missing relation",
            "undefined table",
        )
        return any(marker in message for marker in missing_markers)

    def _initialize_schema_sqlite(self):
        """
        Initializes or migrates the database schema to `_CURRENT_SCHEMA_VERSION`.

        Checks the existing schema version.
        - If 0 (new DB): Applies the full current schema (`_apply_schema_v4`).
        - If current: Logs that schema is up to date.
        - If older: Raises SchemaError (migration paths not yet implemented beyond initial creation).
        - If newer: Raises SchemaError (database is newer than code supports).

        This method is called during `CharactersRAGDB` instantiation.
        Operations are performed within a transaction.

        Raises:
            SchemaError: If the database schema version is newer than supported by the code,
                         if a migration path is undefined for an older schema version,
                         or if any step in schema application/migration fails.
            CharactersRAGDBError: For unexpected errors during schema initialization.
        """
        conn = self.get_connection()
        current_initial_version = 0
        try:
            with TransactionContextManager(self): # Ensures atomicity for schema changes
                current_db_version = self._get_db_version(conn)
                current_initial_version = current_db_version # Store initial for messages
                target_version = self._CURRENT_SCHEMA_VERSION
                logger.info(
                    f"Checking DB schema '{self._SCHEMA_NAME}'. Current version: {current_db_version}. Code supports: {target_version}")

                if current_db_version == target_version:
                    logger.debug(f"Database schema '{self._SCHEMA_NAME}' is up to date (Version {target_version}).")
                    # Ensure helpful indexes that may have been introduced post-creation
                    try:
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_created_at ON flashcards(created_at)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_conversation ON flashcards(conversation_id)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_message ON flashcards(message_id)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_state ON conversations(state)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_cluster ON conversations(cluster_id)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_last_modified ON conversations(last_modified)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_topic_label ON conversations(topic_label)")
                        conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_conversations_source_external_ref ON conversations(source, external_ref)"
                        )
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_conversation ON notes(conversation_id)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_message ON notes(message_id)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_sessions_last_modified ON writing_sessions(last_modified)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_sessions_deleted ON writing_sessions(deleted)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_templates_last_modified ON writing_templates(last_modified)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_templates_deleted ON writing_templates(deleted)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_themes_last_modified ON writing_themes(last_modified)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_themes_deleted ON writing_themes(deleted)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_themes_order ON writing_themes(order_index)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_wordclouds_status ON writing_wordclouds(status)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_wordclouds_last_modified ON writing_wordclouds(last_modified)")
                    except sqlite3.Error:
                        pass
                    # Verify core FTS tables exist to avoid silent search failures
                    self._verify_required_fts_tables_sqlite(conn)
                    return
                if current_db_version > target_version:
                    raise SchemaError(
                        f"Database schema '{self._SCHEMA_NAME}' version ({current_db_version}) is newer than supported by code ({target_version}). Aborting.")

                if current_db_version == 0:
                    # New DB: apply V4 base then migrate to current target (>= V5)
                    self._apply_schema_v4(conn)
                    current_db_version = self._get_db_version(conn)
                    if target_version >= 5 and current_db_version == 4:
                        self._migrate_from_v4_to_v5(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 6 and current_db_version == 5:
                        self._migrate_from_v5_to_v6(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 7 and current_db_version == 6:
                        self._migrate_from_v6_to_v7(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 8 and current_db_version == 7:
                        self._migrate_from_v7_to_v8(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 9 and current_db_version == 8:
                        self._migrate_from_v8_to_v9(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 10 and current_db_version == 9:
                        self._migrate_from_v9_to_v10(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 11 and current_db_version == 10:
                        self._migrate_from_v10_to_v11(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 12 and current_db_version == 11:
                        self._migrate_from_v11_to_v12(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 13 and current_db_version == 12:
                        self._migrate_from_v12_to_v13(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 14 and current_db_version == 13:
                        self._migrate_from_v13_to_v14(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 15 and current_db_version == 14:
                        self._migrate_from_v14_to_v15(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 16 and current_db_version == 15:
                        self._migrate_from_v15_to_v16(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 17 and current_db_version == 16:
                        self._migrate_from_v16_to_v17(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 18 and current_db_version == 17:
                        self._migrate_from_v17_to_v18(conn)
                        current_db_version = self._get_db_version(conn)
                    if target_version >= 19 and current_db_version == 18:
                        self._migrate_from_v18_to_v19(conn)
                        current_db_version = self._get_db_version(conn)
                # Ensure helpful indexes that may have been introduced post-creation
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_created_at ON flashcards(created_at)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_conversation ON flashcards(conversation_id)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_message ON flashcards(message_id)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_state ON conversations(state)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_cluster ON conversations(cluster_id)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_last_modified ON conversations(last_modified)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_topic_label ON conversations(topic_label)")
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_conversations_source_external_ref ON conversations(source, external_ref)"
                    )
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_conversation ON notes(conversation_id)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_message ON notes(message_id)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_sessions_last_modified ON writing_sessions(last_modified)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_sessions_deleted ON writing_sessions(deleted)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_templates_last_modified ON writing_templates(last_modified)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_templates_deleted ON writing_templates(deleted)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_themes_last_modified ON writing_themes(last_modified)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_themes_deleted ON writing_themes(deleted)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_themes_order ON writing_themes(order_index)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_wordclouds_status ON writing_wordclouds(status)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_wordclouds_last_modified ON writing_wordclouds(last_modified)")
                except sqlite3.Error:
                    pass
                # Example for future migrations:
                # elif current_db_version == 1:
                #     self._migrate_from_v1_to_v2(conn)
                #     current_db_version = self._get_db_version(conn) # Refresh version
                #     if current_db_version == 2 and target_version > 2: # Continue if more migrations needed
                #         self._migrate_from_v2_to_v3(conn)
                #         # ...and so on
                if current_initial_version < target_version:
                    # If this was a brand new database (version 0), we have already
                    # applied the base schema and stepped migrations above. Skip
                    # the secondary migration-path dispatcher.
                    if current_initial_version == 0:
                        pass
                    # Handle known migration paths for pre-existing databases
                    elif current_initial_version == 4 and target_version >= 5:
                        self._migrate_from_v4_to_v5(conn)
                        current_db_version = self._get_db_version(conn)
                        if target_version >= 6 and current_db_version == 5:
                            self._migrate_from_v5_to_v6(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 7 and current_db_version == 6:
                            self._migrate_from_v6_to_v7(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 8 and current_db_version == 7:
                            self._migrate_from_v7_to_v8(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 9 and current_db_version == 8:
                            self._migrate_from_v8_to_v9(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 10 and current_db_version == 9:
                            self._migrate_from_v9_to_v10(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 11 and current_db_version == 10:
                            self._migrate_from_v10_to_v11(conn)
                            current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 5 and target_version >= 6:
                        self._migrate_from_v5_to_v6(conn)
                        current_db_version = self._get_db_version(conn)
                        if target_version >= 7 and current_db_version == 6:
                            self._migrate_from_v6_to_v7(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 8 and current_db_version == 7:
                            self._migrate_from_v7_to_v8(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 9 and current_db_version == 8:
                            self._migrate_from_v8_to_v9(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 10 and current_db_version == 9:
                            self._migrate_from_v9_to_v10(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 11 and current_db_version == 10:
                            self._migrate_from_v10_to_v11(conn)
                            current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 6 and target_version >= 7:
                        self._migrate_from_v6_to_v7(conn)
                        current_db_version = self._get_db_version(conn)
                        if target_version >= 8 and current_db_version == 7:
                            self._migrate_from_v7_to_v8(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 9 and current_db_version == 8:
                            self._migrate_from_v8_to_v9(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 10 and current_db_version == 9:
                            self._migrate_from_v9_to_v10(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 11 and current_db_version == 10:
                            self._migrate_from_v10_to_v11(conn)
                            current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 7 and target_version >= 8:
                        self._migrate_from_v7_to_v8(conn)
                        current_db_version = self._get_db_version(conn)
                        if target_version >= 9 and current_db_version == 8:
                            self._migrate_from_v8_to_v9(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 10 and current_db_version == 9:
                            self._migrate_from_v9_to_v10(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 11 and current_db_version == 10:
                            self._migrate_from_v10_to_v11(conn)
                            current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 8 and target_version >= 9:
                        self._migrate_from_v8_to_v9(conn)
                        current_db_version = self._get_db_version(conn)
                        if target_version >= 10 and current_db_version == 9:
                            self._migrate_from_v9_to_v10(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 11 and current_db_version == 10:
                            self._migrate_from_v10_to_v11(conn)
                            current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 9 and target_version >= 10:
                        self._migrate_from_v9_to_v10(conn)
                        current_db_version = self._get_db_version(conn)
                        if target_version >= 11 and current_db_version == 10:
                            self._migrate_from_v10_to_v11(conn)
                            current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 10 and target_version >= 11:
                        self._migrate_from_v10_to_v11(conn)
                        current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 11 and target_version >= 12:
                        self._migrate_from_v11_to_v12(conn)
                        current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 12 and target_version >= 13:
                        self._migrate_from_v12_to_v13(conn)
                        current_db_version = self._get_db_version(conn)
                        if target_version >= 14 and current_db_version == 13:
                            self._migrate_from_v13_to_v14(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 15 and current_db_version == 14:
                            self._migrate_from_v14_to_v15(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 16 and current_db_version == 15:
                            self._migrate_from_v15_to_v16(conn)
                            current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 13 and target_version >= 14:
                        self._migrate_from_v13_to_v14(conn)
                        current_db_version = self._get_db_version(conn)
                        if target_version >= 15 and current_db_version == 14:
                            self._migrate_from_v14_to_v15(conn)
                            current_db_version = self._get_db_version(conn)
                        if target_version >= 16 and current_db_version == 15:
                            self._migrate_from_v15_to_v16(conn)
                            current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 14 and target_version >= 15:
                        self._migrate_from_v14_to_v15(conn)
                        current_db_version = self._get_db_version(conn)
                        if target_version >= 16 and current_db_version == 15:
                            self._migrate_from_v15_to_v16(conn)
                            current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 15 and target_version >= 16:
                        self._migrate_from_v15_to_v16(conn)
                        current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 16 and target_version >= 17:
                        self._migrate_from_v16_to_v17(conn)
                        current_db_version = self._get_db_version(conn)
                    elif current_initial_version == 17 and target_version >= 18:
                        self._migrate_from_v17_to_v18(conn)
                        current_db_version = self._get_db_version(conn)
                    else:
                        raise SchemaError(
                            f"Migration path undefined for '{self._SCHEMA_NAME}' from version {current_initial_version} to {target_version}. "
                            f"Manual migration or a new database may be required.")
                else: # Should not be reached due to prior checks
                    raise SchemaError(f"Unexpected schema state: current {current_initial_version}, target {target_version}")

                if target_version >= 12 and current_db_version == 11:
                    self._migrate_from_v11_to_v12(conn)
                    current_db_version = self._get_db_version(conn)
                if target_version >= 13 and current_db_version == 12:
                    self._migrate_from_v12_to_v13(conn)
                    current_db_version = self._get_db_version(conn)
                if target_version >= 14 and current_db_version == 13:
                    self._migrate_from_v13_to_v14(conn)
                    current_db_version = self._get_db_version(conn)
                if target_version >= 15 and current_db_version == 14:
                    self._migrate_from_v14_to_v15(conn)
                    current_db_version = self._get_db_version(conn)
                if target_version >= 16 and current_db_version == 15:
                    self._migrate_from_v15_to_v16(conn)
                    current_db_version = self._get_db_version(conn)
                if target_version >= 17 and current_db_version == 16:
                    self._migrate_from_v16_to_v17(conn)
                    current_db_version = self._get_db_version(conn)
                if target_version >= 18 and current_db_version == 17:
                    self._migrate_from_v17_to_v18(conn)
                    current_db_version = self._get_db_version(conn)
                if target_version >= 19 and current_db_version == 18:
                    self._migrate_from_v18_to_v19(conn)
                    current_db_version = self._get_db_version(conn)

                final_version_check = self._get_db_version(conn)
                if final_version_check != target_version:
                    raise SchemaError(
                        f"Schema migration process completed, but final DB version is {final_version_check}, expected {target_version}. Manual check required.")
                # Verify core FTS tables after migrations complete
                self._verify_required_fts_tables_sqlite(conn)
                logger.info(
                    f"Database schema '{self._SCHEMA_NAME}' successfully initialized/migrated to version {final_version_check}.")

        except (SchemaError, sqlite3.Error) as e:
            logger.error(f"Schema initialization/migration failed for '{self._SCHEMA_NAME}': {e}", exc_info=True)
            raise SchemaError(f"Schema initialization/migration for '{self._SCHEMA_NAME}' failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during schema initialization for '{self._SCHEMA_NAME}': {e}", exc_info=True)
            raise CharactersRAGDBError(f"Unexpected error applying schema for '{self._SCHEMA_NAME}': {e}") from e

    def _verify_required_fts_tables_sqlite(self, conn: sqlite3.Connection) -> None:
        """Ensure required FTS tables exist in SQLite deployments.

        Uses the configured `_FTS_CONFIG` list to assert the presence of the
        matching virtual tables. Raises SchemaError with a helpful message on
        missing tables to prevent confusing search errors later.
        """
        try:
            required = {name for name, _, _ in self._FTS_CONFIG}
            if not required:
                return
            placeholders = ",".join(["?"] * len(required))
            cur = conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})",
                tuple(sorted(required)),
            )
            existing = {row[0] for row in cur.fetchall()}
            missing = required - existing
            if missing:
                raise SchemaError(
                    f"Missing required FTS tables for '{self._SCHEMA_NAME}': {', '.join(sorted(missing))}"
                )
        except sqlite3.Error as e:
            raise SchemaError(f"Failed verifying FTS tables for '{self._SCHEMA_NAME}': {e}") from e

    def _initialize_schema_postgres(self):
        """Bootstrap or migrate the ChaCha schema on PostgreSQL."""

        backend = self.backend
        target_version = self._CURRENT_SCHEMA_VERSION

        with backend.transaction() as conn:
            schema_exists = backend.table_exists('db_schema_version', connection=conn)

            if not schema_exists:
                self._apply_schema_v4_postgres(conn)
                current_version = 4
            else:
                current_version = self._get_schema_version_postgres(conn)

            if current_version < 5:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V4_TO_V5, conn, expected_version=5)
                current_version = 5

            if current_version < 6:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V5_TO_V6, conn, expected_version=6)
                current_version = 6

            if current_version < 7:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V6_TO_V7, conn, expected_version=7)
                current_version = 7

            if current_version < 8:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V7_TO_V8, conn, expected_version=8)
                current_version = 8

            if current_version < 9:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V8_TO_V9, conn, expected_version=9)
                current_version = 9

            if current_version < 10:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V9_TO_V10, conn, expected_version=10)
                current_version = 10
            if current_version < 11:
                self._apply_postgres_migration_script(
                    self._MIGRATION_SQL_V10_TO_V11_POSTGRES,
                    conn,
                    expected_version=11,
                )
                current_version = 11
            if current_version < 12:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V11_TO_V12, conn, expected_version=12)
                current_version = 12
            if current_version < 13:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V12_TO_V13, conn, expected_version=13)
                current_version = 13
            if current_version < 14:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V13_TO_V14, conn, expected_version=14)
                current_version = 14
            if current_version < 15:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V14_TO_V15, conn, expected_version=15)
                current_version = 15
            if current_version < 16:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V15_TO_V16, conn, expected_version=16)
                current_version = 16
            if current_version < 17:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V16_TO_V17, conn, expected_version=17)
                current_version = 17
            if current_version < 18:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V17_TO_V18, conn, expected_version=18)
                current_version = 18
            if current_version < 19:
                self._apply_postgres_migration_script(self._MIGRATION_SQL_V18_TO_V19, conn, expected_version=19)
                current_version = 19

            if current_version > target_version:
                raise SchemaError(
                    f"Database schema version ({current_version}) is newer than supported by code ({target_version})."
                )

            if current_version < target_version:
                logger.warning(
                    "ChaChaNotes PostgreSQL schema is at version %s but code expects %s. Pending migrations will "
                    "be addressed in a future update.",
                    current_version,
                    target_version,
                )

            try:
                # Namespace migration: if legacy 'keywords' exists, rename to 'chacha_keywords'
                try:
                    if self.backend.table_exists('keywords', connection=conn) and not self.backend.table_exists('chacha_keywords', connection=conn):
                        self.backend.execute("ALTER TABLE keywords RENAME TO chacha_keywords", connection=conn)
                except Exception as exc:
                    logger.warning("Failed to rename legacy keywords table: %s", exc)

                self._ensure_postgres_fts(conn)
                # Ensure helpful indexes that may have been introduced post-creation
                try:
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_flashcards_created_at ON flashcards(created_at)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_flashcards_conversation ON flashcards(conversation_id)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_flashcards_message ON flashcards(message_id)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_conversations_state ON conversations(state)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_conversations_cluster ON conversations(cluster_id)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_conversations_last_modified ON conversations(last_modified)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_conversations_topic_label ON conversations(topic_label)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_conversations_source_external_ref ON conversations(source, external_ref)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_notes_conversation ON notes(conversation_id)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_notes_message ON notes(message_id)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_writing_sessions_last_modified ON writing_sessions(last_modified)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_writing_sessions_deleted ON writing_sessions(deleted)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_writing_templates_last_modified ON writing_templates(last_modified)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_writing_templates_deleted ON writing_templates(deleted)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_writing_themes_last_modified ON writing_themes(last_modified)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_writing_themes_deleted ON writing_themes(deleted)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_writing_themes_order ON writing_themes(order_index)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_writing_wordclouds_status ON writing_wordclouds(status)",
                        connection=conn,
                    )
                    self.backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_writing_wordclouds_last_modified ON writing_wordclouds(last_modified)",
                        connection=conn,
                    )
                except Exception as exc:
                    logger.warning("Failed to ensure ChaChaNotes PostgreSQL indexes: %s", exc)
            except BackendDatabaseError as exc:
                raise SchemaError(f"Failed to ensure PostgreSQL FTS structures: {exc}") from exc

    def _ensure_postgres_fts(self, conn) -> None:
        """Ensure PostgreSQL full-text search structures exist for ChaCha entities."""

        backend = self.backend
        for fts_table, source_table, columns in self._FTS_CONFIG:
            actual_source = self._map_table_for_backend(source_table)
            backend.create_fts_table(
                table_name=fts_table,
                source_table=actual_source,
                columns=columns,
                connection=conn,
            )
        self._refresh_postgres_tsvectors(connection=conn)

    def _refresh_postgres_tsvectors(self, connection=None) -> None:
        """Populate/refresh tsvector columns backing Postgres FTS searches."""
        if self.backend_type != BackendType.POSTGRESQL:
            return

        backend = self.backend
        for fts_table, source_table, columns in self._FTS_CONFIG:
            actual_source = self._map_table_for_backend(source_table)
            fts_column = f"{fts_table}_tsv"
            concat_expr = " || ' ' || ".join(
                f"coalesce({backend.escape_identifier(col)}, '')" for col in columns
            )
            if not concat_expr:
                concat_expr = "''"

            update_sql = (
                f"UPDATE {backend.escape_identifier(actual_source)} "
                f"SET {backend.escape_identifier(fts_column)} = "
                f"to_tsvector('english', {concat_expr})"
            )
            try:
                backend.execute(update_sql, connection=connection)
            except BackendDatabaseError as exc:
                logger.warning(
                    "Failed to refresh PostgreSQL FTS vector for %s.%s: %s",
                    actual_source,
                    fts_column,
                    exc,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Unexpected error while refreshing PostgreSQL FTS vector for %s.%s: %s",
                    actual_source,
                    fts_column,
                    exc,
                )

    def rebuild_full_text_indexes(self) -> None:
        """Rebuild FTS indexes for the active backend."""

        if self.backend_type == BackendType.POSTGRESQL:
            try:
                for fts_table, source_table, columns in self._FTS_CONFIG:
                    actual_source = self._map_table_for_backend(source_table)
                    self.backend.create_fts_table(
                        table_name=fts_table,
                        source_table=actual_source,
                        columns=columns,
                        connection=None,
                    )
                self._refresh_postgres_tsvectors()
            except BackendDatabaseError as exc:
                raise CharactersRAGDBError(f"Failed to rebuild PostgreSQL FTS structures: {exc}") from exc
            return

        if self.backend_type == BackendType.SQLITE:
            try:
                with self.transaction() as conn:
                    for fts_table, _, _ in self._FTS_CONFIG:
                        conn.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('rebuild')")
            except sqlite3.Error as exc:
                raise CharactersRAGDBError(f"Failed to rebuild SQLite FTS structures: {exc}") from exc
            return

        raise NotImplementedError(f"FTS rebuild not supported for backend {self.backend_type.value}")

    # ----------------------
    # Message metadata (tool calls)
    # ----------------------
    def _ensure_message_metadata_table(self) -> None:
        """Ensure the message_metadata table exists for the active backend."""
        if self.backend_type == BackendType.SQLITE:
            self.execute_query(
                """
                CREATE TABLE IF NOT EXISTS message_metadata(
                  message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                  tool_calls_json TEXT,
                  extra_json TEXT,
                  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                script=False,
                commit=True,
            )
            return

        if self.backend_type == BackendType.POSTGRESQL:
            self.backend.execute(
                """
                CREATE TABLE IF NOT EXISTS message_metadata(
                  message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                  tool_calls_json TEXT,
                  extra_json TEXT,
                  last_modified TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            return

        raise NotImplementedError(
            f"message_metadata table creation not supported for backend {self.backend_type.value}"
        )

    def add_message_metadata(self, message_id: str, tool_calls: Optional[Any] = None, extra: Optional[Any] = None) -> bool:
        """Upsert per-message metadata such as tool calls.

        Stores JSON-serialized metadata in an auxiliary table `message_metadata`.
        The table is created on-demand if missing.
        """
        try:
            self._ensure_message_metadata_table()
            if self.backend_type == BackendType.SQLITE:
                query = (
                    "INSERT INTO message_metadata(message_id, tool_calls_json, extra_json, last_modified) "
                    "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
                    "ON CONFLICT(message_id) DO UPDATE SET tool_calls_json=excluded.tool_calls_json, "
                    "extra_json=excluded.extra_json, last_modified=CURRENT_TIMESTAMP"
                )
                self.execute_query(
                    query,
                    (
                        message_id,
                        json.dumps(tool_calls) if tool_calls is not None else None,
                        json.dumps(extra) if extra is not None else None,
                    ),
                    commit=True,
                )
                return True

            upsert = (
                "INSERT INTO message_metadata(message_id, tool_calls_json, extra_json, last_modified) "
                "VALUES (%s, %s, %s, NOW()) "
                "ON CONFLICT (message_id) DO UPDATE SET tool_calls_json = EXCLUDED.tool_calls_json, "
                "extra_json = EXCLUDED.extra_json, last_modified = NOW()"
            )
            self.backend.execute(
                upsert,
                (
                    message_id,
                    json.dumps(tool_calls) if tool_calls is not None else None,
                    json.dumps(extra) if extra is not None else None,
                ),
            )
            return True
        except Exception as e:
            logger.warning(f"add_message_metadata failed for message {message_id}: {e}")
            return False

    def get_message_metadata(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Fetch metadata for a message if present."""
        try:
            self._ensure_message_metadata_table()
            if self.backend_type == BackendType.SQLITE:
                cursor = self.execute_query(
                    "SELECT tool_calls_json, extra_json, last_modified FROM message_metadata WHERE message_id = ?",
                    (message_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                tc, ex, lm = row
            else:
                result = self.backend.execute(
                    "SELECT tool_calls_json, extra_json, last_modified FROM message_metadata WHERE message_id = %s",
                    (message_id,)
                )
                r = result.fetchone()
                if not r:
                    return None
                tc, ex, lm = r
            return {
                "tool_calls": json.loads(tc) if tc else None,
                "extra": json.loads(ex) if ex else None,
                "last_modified": lm,
            }
        except Exception:
            return None

    def _convert_sqlite_schema_to_postgres_statements(self, sql: str) -> List[str]:
        """Convert SQLite schema SQL into individual Postgres-compatible statements."""

        statements: List[str] = []
        buffer: List[str] = []
        in_block_comment = False
        skip_until_semicolon = False
        skip_trigger_block = False

        for raw_line in sql.splitlines():
            stripped = raw_line.strip()

            if not stripped:
                continue

            if in_block_comment:
                if '*/' in stripped:
                    in_block_comment = False
                continue

            if stripped.startswith('/*'):
                if '*/' not in stripped:
                    in_block_comment = True
                continue

            if stripped.startswith('--'):
                continue

            upper = stripped.upper()

            if upper.startswith('PRAGMA'):
                continue

            if skip_until_semicolon:
                if stripped.endswith(';'):
                    skip_until_semicolon = False
                continue

            if skip_trigger_block:
                if upper.endswith('END;'):
                    skip_trigger_block = False
                continue

            if 'CREATE VIRTUAL TABLE' in upper:
                if not stripped.endswith(';'):
                    skip_until_semicolon = True
                continue

            if upper.startswith('DROP TRIGGER'):
                if not stripped.endswith(';'):
                    skip_until_semicolon = True
                continue

            if upper.startswith('CREATE TRIGGER'):
                skip_trigger_block = True
                continue

            buffer.append(raw_line)

            if stripped.endswith(';'):
                statement = '\n'.join(buffer).strip()
                buffer = []
                transformed = self._transform_sqlite_schema_statement_for_postgres(statement)
                if transformed:
                    statements.append(transformed)

        return statements

    # ----------------------
    # Message metadata helpers (structured extras + backfill)
    # ----------------------
    def set_message_metadata_extra(self, message_id: str, extra: Dict[str, Any], merge: bool = True) -> bool:
        """Set or merge structured extra metadata for a message.

        Expected shape for `extra`:
          {
            "tool_results": { "<tool_call_id>": <any-json-serializable> },
            ... other namespaced keys ...,
            "version": 1
          }

        If merge=True and existing extra exists, perform a shallow merge; nested maps like
        tool_results are merged key-wise.
        """
        try:
            current = self.get_message_metadata(message_id) or {}
            current_extra = current.get('extra') or {}
            if merge and isinstance(current_extra, dict) and isinstance(extra, dict):
                merged = dict(current_extra)
                # Merge tool_results specially
                tr_existing = merged.get('tool_results') if isinstance(merged.get('tool_results'), dict) else {}
                tr_incoming = extra.get('tool_results') if isinstance(extra.get('tool_results'), dict) else {}
                if tr_existing or tr_incoming:
                    merged['tool_results'] = {**tr_existing, **tr_incoming}
                # Merge top-level keys (favor incoming)
                for k, v in extra.items():
                    if k == 'tool_results':
                        continue
                    merged[k] = v
                new_extra = merged
            else:
                new_extra = extra
            return self.add_message_metadata(message_id, tool_calls=current.get('tool_calls'), extra=new_extra)
        except Exception as e:
            logger.warning(f"set_message_metadata_extra failed for {message_id}: {e}")
            return False

    def set_message_rag_context(
        self,
        message_id: str,
        rag_context: Dict[str, Any],
        merge: bool = True
    ) -> bool:
        """
        Store RAG context (citations, retrieved documents, search settings) with a message.

        This persists RAG search results and citations in message_metadata.extra_json
        under the 'rag_context' key for later retrieval and export.

        Args:
            message_id: The message ID to attach RAG context to
            rag_context: Dict containing:
                - search_query: The original search query
                - search_mode: Search mode used (fts/vector/hybrid)
                - settings_snapshot: Key RAG settings used
                - retrieved_documents: List of retrieved docs with scores/excerpts
                - generated_answer: AI-generated answer (if any)
                - citations: Citation metadata
                - claims_verified: Verification results (if any)
                - timestamp: ISO timestamp
                - feedback_id: Analytics ID
            merge: If True, merge with existing extra data; if False, replace entire extra

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get current metadata to preserve other extra fields
            current = self.get_message_metadata(message_id) or {}
            current_extra = current.get('extra') or {}

            if merge and isinstance(current_extra, dict):
                # Merge: preserve existing extra fields, update rag_context
                new_extra = dict(current_extra)
                new_extra['rag_context'] = rag_context
            else:
                # Replace: only keep rag_context
                new_extra = {'rag_context': rag_context}

            return self.add_message_metadata(
                message_id,
                tool_calls=current.get('tool_calls'),
                extra=new_extra
            )
        except Exception as e:
            logger.warning(f"set_message_rag_context failed for {message_id}: {e}")
            return False

    def get_message_rag_context(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve RAG context stored with a message.

        Returns the rag_context dict from message_metadata.extra_json,
        or None if no RAG context is stored.
        """
        try:
            metadata = self.get_message_metadata(message_id)
            if not metadata:
                return None
            extra = metadata.get('extra')
            if not isinstance(extra, dict):
                return None
            return extra.get('rag_context')
        except Exception as e:
            logger.warning(f"get_message_rag_context failed for {message_id}: {e}")
            return None

    def get_messages_with_rag_context(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
        include_rag_context: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages for a conversation with optional RAG context attached.

        This is optimized for the Knowledge QA page to load conversation history
        with full citation data.

        Args:
            conversation_id: The conversation to fetch messages from
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            include_rag_context: If True, attach rag_context to each message

        Returns:
            List of message dicts, each optionally including 'rag_context' key
        """
        try:
            messages = self.get_messages_for_conversation(
                conversation_id,
                limit=limit,
                offset=offset
            )

            if not include_rag_context:
                return messages

            # Attach RAG context to each message
            for msg in messages:
                msg_id = msg.get('id')
                if msg_id:
                    rag_context = self.get_message_rag_context(msg_id)
                    if rag_context:
                        msg['rag_context'] = rag_context

            return messages
        except Exception as e:
            logger.warning(f"get_messages_with_rag_context failed for conversation {conversation_id}: {e}")
            return []

    def get_conversation_citations(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all citations from a conversation's messages.

        This aggregates all retrieved_documents from rag_context across
        all messages in a conversation, useful for export and citation
        bibliography generation.

        Returns:
            List of unique retrieved documents with their source message IDs
        """
        try:
            messages = self.get_messages_for_conversation(conversation_id, limit=1000)
            citations_by_id: Dict[str, Dict[str, Any]] = {}

            for msg in messages:
                msg_id = msg.get('id')
                if not msg_id:
                    continue

                rag_context = self.get_message_rag_context(msg_id)
                if not rag_context:
                    continue

                retrieved_docs = rag_context.get('retrieved_documents', [])
                for doc in retrieved_docs:
                    doc_id = doc.get('id') or doc.get('chunk_id') or f"anon_{len(citations_by_id)}"
                    if doc_id not in citations_by_id:
                        citations_by_id[doc_id] = {
                            **doc,
                            'message_ids': [msg_id],
                            'first_cited_at': msg.get('timestamp')
                        }
                    else:
                        if msg_id not in citations_by_id[doc_id]['message_ids']:
                            citations_by_id[doc_id]['message_ids'].append(msg_id)

            return list(citations_by_id.values())
        except Exception as e:
            logger.warning(f"get_conversation_citations failed for conversation {conversation_id}: {e}")
            return []

    def backfill_tool_calls_from_inline(self, strip_inline: bool = False, limit: Optional[int] = None) -> Dict[str, int]:
        """Scan assistant messages for an inline "[tool_calls]: <json>" suffix and backfill message_metadata.

        - Extracts JSON array/object after the last occurrence of "[tool_calls]:" (case-sensitive).
        - Persists it into `message_metadata.tool_calls_json`.
        - If `strip_inline=True`, removes the suffix from message content using optimistic locking.

        Returns counts: { scanned, matched, backfilled, stripped }
        """
        counts = {"scanned": 0, "matched": 0, "backfilled": 0, "stripped": 0}
        pattern = re.compile(r"\[tool_calls\]\s*:\s*(\{.*|\[.*)$", re.DOTALL)

        def _extract(content: str) -> Optional[Dict[str, Any]]:
            if not content:
                return None
            m = pattern.search(content)
            if not m:
                return None
            json_str = m.group(1).strip()
            try:
                data = json.loads(json_str)
                # Normalize: ensure list for tool_calls when object provided
                if isinstance(data, dict) and 'tool_calls' in data:
                    tool_calls = data.get('tool_calls')
                else:
                    tool_calls = data
                if isinstance(tool_calls, (list, dict)):
                    return {"tool_calls": tool_calls, "prefix_end": m.start(), "json_end": m.end()}
                return None
            except Exception:
                return None

        try:
            rows: List[Dict[str, Any]] = []
            if self.backend_type == BackendType.SQLITE:
                query = "SELECT id, content, version FROM messages WHERE sender = ? AND deleted = 0"
                params = ("assistant",)
                if limit and isinstance(limit, int):
                    query += " LIMIT ?"
                    params = ("assistant", limit)
                cur = self.execute_query(query, params)
                rows = [dict(r) for r in cur.fetchall()]
            else:
                q = "SELECT id, content, version FROM messages WHERE sender = %s AND deleted = false"
                params = ("assistant",)
                if limit and isinstance(limit, int):
                    q += " LIMIT %s"
                    params = ("assistant", limit)
                res = self.backend.execute(q, params)
                fetched = res.fetchall()
                # Convert to dicts (backend returns sequence rows)
                for r in fetched:
                    # Row maybe mapping or tuple; try subscripting by name first
                    try:
                        rows.append({"id": r[0], "content": r[1], "version": r[2]})
                    except Exception:
                        try:
                            rows.append({"id": r['id'], "content": r['content'], "version": r['version']})
                        except Exception:
                            pass

            for row in rows:
                counts["scanned"] += 1
                mid = row.get('id')
                content = row.get('content') or ""
                version = row.get('version') or 1
                extracted = _extract(content)
                if not extracted:
                    continue
                counts["matched"] += 1
                tool_calls = extracted.get('tool_calls')
                # Persist tool_calls array/object
                try:
                    if self.add_message_metadata(mid, tool_calls=tool_calls):
                        counts["backfilled"] += 1
                except Exception:
                    pass
                # Optionally strip inline suffix
                if strip_inline:
                    try:
                        # Trim content up to prefix_end
                        new_content = content[: int(extracted.get('prefix_end') or len(content))].rstrip()
                        self.update_message(mid, {"content": new_content}, expected_version=version)
                        counts["stripped"] += 1
                    except Exception:
                        # If version changed, skip silently
                        pass
        except Exception as e:
            logger.warning(f"backfill_tool_calls_from_inline encountered an error: {e}")
        return counts

    def _transform_sqlite_schema_statement_for_postgres(self, statement: str) -> Optional[str]:
        """Apply token-level rewrites so the statement can run on Postgres."""

        stmt = statement.strip()
        if not stmt:
            return None

        stmt = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'INTEGER\s+PRIMARY\s+KEY', 'BIGINT PRIMARY KEY', stmt, flags=re.IGNORECASE)

        def _replace_integer_references(match: re.Match[str]) -> str:
            suffix = match.group(1) or ''
            return f"BIGINT{suffix} REFERENCES"

        stmt = re.sub(
            r'INTEGER(\s+NOT\s+NULL)?\s+REFERENCES',
            _replace_integer_references,
            stmt,
            flags=re.IGNORECASE,
        )

        stmt = re.sub(r'BOOLEAN\s+NOT\s+NULL\s+DEFAULT\s+0', 'BOOLEAN NOT NULL DEFAULT FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN\s+NOT\s+NULL\s+DEFAULT\s+1', 'BOOLEAN NOT NULL DEFAULT TRUE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN\s+DEFAULT\s+0', 'BOOLEAN DEFAULT FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN\s+DEFAULT\s+1', 'BOOLEAN DEFAULT TRUE', stmt, flags=re.IGNORECASE)

        stmt = re.sub(r'DATETIME', 'TIMESTAMPTZ', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BLOB', 'BYTEA', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'COLLATE\s+NOCASE', '', stmt, flags=re.IGNORECASE)

        stmt = re.sub(r'WHERE\s+([A-Za-z_]+)\s*=\s*0', r'WHERE \1 = FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'WHERE\s+([A-Za-z_]+)\s*=\s*1', r'WHERE \1 = TRUE', stmt, flags=re.IGNORECASE)

        stmt = replace_insert_or_ignore(stmt)

        # Special-case: seed insert for character_cards uses integer for boolean 'deleted'.
        lower_stmt = stmt.lower()
        if lower_stmt.startswith('insert') and 'into character_cards' in lower_stmt:
            # Convert trailing deleted value 0/1 to boolean FALSE/TRUE for Postgres
            stmt = re.sub(r",\s*0\)\s*;\s*$", ", FALSE);", stmt)
            stmt = re.sub(r",\s*1\)\s*;\s*$", ", TRUE);", stmt)
            stmt = re.sub(r",\s*0\)\s*ON\s+CONFLICT", ", FALSE) ON CONFLICT", stmt, flags=re.IGNORECASE)
            stmt = re.sub(r",\s*1\)\s*ON\s+CONFLICT", ", TRUE) ON CONFLICT", stmt, flags=re.IGNORECASE)

        # Break circular FK between conversations/messages by dropping conversations->messages FK at create time
        if lower_stmt.startswith('create table') and 'create table if not exists conversations' in lower_stmt:
            # Remove the forked_from_message_id FK clause
            stmt = re.sub(
                r"forked_from_message_id\s+TEXT\s+REFERENCES\s+messages\s*\(\s*id\s*\)\s*ON\s+DELETE\s+SET\s+NULL,?",
                "forked_from_message_id TEXT,",
                stmt,
                flags=re.IGNORECASE,
            )

        # Namespace the 'keywords' table to avoid collision with Media DB keywords
        # Only adjust creation/references; triggers and FTS blocks are skipped earlier
        if 'create table if not exists keywords' in lower_stmt:
            stmt = re.sub(
                r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+keywords\s*\(",
                "CREATE TABLE IF NOT EXISTS chacha_keywords(",
                stmt,
                flags=re.IGNORECASE,
            )
        # Adjust references to keywords in foreign keys/content declarations
        stmt = re.sub(
            r"REFERENCES\s+keywords\s*\(\s*id\s*\)",
            "REFERENCES chacha_keywords(id)",
            stmt,
            flags=re.IGNORECASE,
        )
        stmt = re.sub(
            r"content='keywords'",
            "content='chacha_keywords'",
            stmt,
            flags=re.IGNORECASE,
        )

        if not stmt.endswith(';'):
            stmt = f"{stmt};"
        return stmt

    def _apply_schema_v4_postgres(self, conn) -> None:
        statements = self._convert_sqlite_schema_to_postgres_statements(self._FULL_SCHEMA_SQL_V4)

        deferred_sync_idx_stmt: Optional[str] = None
        for stmt in statements:
            up = stmt.upper().strip()
            if up.startswith("CREATE INDEX IF NOT EXISTS IDX_SYNC_LOG_ENTITY"):
                deferred_sync_idx_stmt = stmt
                continue
            self.backend.execute(stmt, connection=conn)

        # Create sync_log entity index depending on available columns
        try:
            cols = {c.get('name') for c in self.backend.get_table_info('sync_log', connection=conn)}
        except Exception:
            cols = set()

        if 'entity_id' in cols:
            self.backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_sync_log_entity ON sync_log(entity,entity_id)",
                connection=conn,
            )
        elif 'entity_uuid' in cols:
            self.backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_sync_log_entity ON sync_log(entity,entity_uuid)",
                connection=conn,
            )
        elif deferred_sync_idx_stmt:
            self.backend.execute(deferred_sync_idx_stmt, connection=conn)

        self._set_schema_version_postgres(conn, 4)
        self._sync_postgres_sequences(conn)

    def _apply_postgres_migration_script(self, script: str, conn, *, expected_version: int) -> None:
        statements = self._convert_sqlite_schema_to_postgres_statements(script)
        for stmt in statements:
            self.backend.execute(stmt, connection=conn)
        self._set_schema_version_postgres(conn, expected_version)
        self._sync_postgres_sequences(conn)
        # Ensure FTS tsvector for flashcards when schema contains flashcards (v5+)
        try:
            if expected_version >= 5:
                self._ensure_postgres_flashcards_tsvector(conn)
        except Exception as _e:
            logger.debug(f"Skipping ensure flashcards tsvector after migration to v{expected_version}: {_e}")

    def _get_schema_version_postgres(self, conn) -> int:
        result = self.backend.execute(
            "SELECT version FROM db_schema_version WHERE schema_name = %s LIMIT 1",
            (self._SCHEMA_NAME,),
            connection=conn,
        )
        value = result.scalar if result else None
        return int(value) if value is not None else 0

    def _set_schema_version_postgres(self, conn, version: int) -> None:
        self.backend.execute(
            """
            INSERT INTO db_schema_version(schema_name, version)
            VALUES (%s, %s)
            ON CONFLICT (schema_name) DO UPDATE SET version = EXCLUDED.version
            """,
            (self._SCHEMA_NAME, version),
            connection=conn,
        )

    def _sync_postgres_sequences(self, conn) -> None:
        """Ensure PostgreSQL sequences match current maxima for managed tables."""

        backend = self.backend
        ident = backend.escape_identifier

        for table_name, column_name in self._POSTGRES_SEQUENCE_TABLES:
            try:
                # Skip tables that may not exist yet at this schema version
                try:
                    if not backend.table_exists(table_name, connection=conn):
                        continue
                except Exception:
                    continue
                seq_result = backend.execute(
                    "SELECT pg_get_serial_sequence(%s, %s) AS seq",
                    (table_name, column_name),
                    connection=conn,
                )
                sequence_name = seq_result.scalar if seq_result else None
                if not sequence_name:
                    continue

                max_result = backend.execute(
                    (
                        f"SELECT COALESCE(MAX({ident(column_name)}), 0) AS max_id "
                        f"FROM {ident(table_name)}"
                    ),
                    connection=conn,
                )

                try:
                    max_id = int(max_result.scalar or 0)
                except (TypeError, ValueError):
                    max_id = 0

                if max_id <= 0:
                    backend.execute(
                        "SELECT setval(%s, %s, false)",
                        (sequence_name, 1),
                        connection=conn,
                    )
                else:
                    backend.execute(
                        "SELECT setval(%s, %s)",
                        (sequence_name, max_id),
                        connection=conn,
                    )
            except BackendDatabaseError as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to synchronize PostgreSQL sequence for %s.%s: %s",
                    table_name,
                    column_name,
                    exc,
                )

    # --- Internal Helpers ---
    def _get_current_utc_timestamp_iso(self) -> str:
        """
        Generates the current UTC timestamp in ISO 8601 format with 'Z' for UTC.

        Example: "2023-10-27T10:30:00.123Z"

        Returns:
            A string representing the current UTC timestamp with millisecond precision.
        """
        return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def _generate_uuid(self) -> str:
        """
        Generates a new UUID version 4.

        Returns:
            A string representation of the UUID.
        """
        return str(uuid.uuid4())

    def _map_table_for_backend(self, table_name: str) -> str:
        """Map logical table names to backend-specific physical names.

        This avoids name collisions with other modules when sharing a Postgres database.
        """
        if self.backend_type == BackendType.POSTGRESQL:
            mapping = {
                'keywords': 'chacha_keywords',
            }
            return mapping.get(table_name, table_name)
        return table_name

    # ----------------------
    # Notes Graph: manual edges (note_edges)
    # ----------------------
    def create_manual_note_edge(
        self,
        *,
        user_id: str,
        from_note_id: str,
        to_note_id: str,
        directed: bool = False,
        weight: Optional[float] = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: str,
    ) -> Dict[str, Any]:
        """Create a manual note edge, enforcing undirected canonicalization and uniqueness.

        Returns the created edge row as a dict. Raises ConflictError on duplicates.
        """
        if not user_id or not from_note_id or not to_note_id or created_by is None or created_by == "":
            raise InputError("user_id, from_note_id, to_note_id, and created_by are required")

        # Prevent self-loops for manual edges (regardless of directed flag)
        if from_note_id == to_note_id:
            raise InputError("from_note_id and to_note_id must differ (self-loops are not allowed)")

        # Canonicalize for undirected edges
        src = from_note_id
        dst = to_note_id
        if not directed and src > dst:
            src, dst = dst, src

        edge_id = self._generate_uuid()
        now_iso = self._get_current_utc_timestamp_iso()
        type_str = "manual"
        # Validate weight
        import math  # at top-level import preferred; see helper snippet below
        w = 1.0 if weight is None else float(weight)
        if not math.isfinite(w) or w < 0:
            raise InputError("weight must be a finite, non-negative number")

        try:
            with self.transaction() as conn:
                # Ensure endpoints exist (avoid dangling edges)
                if not conn.execute("SELECT 1 FROM notes WHERE id = ? AND deleted = 0", (src,)).fetchone():
                    raise InputError("from_note_id not found or deleted")
                if not conn.execute("SELECT 1 FROM notes WHERE id = ? AND deleted = 0", (dst,)).fetchone():
                    raise InputError("to_note_id not found or deleted")
                query = (
                    "INSERT INTO note_edges(edge_id, user_id, from_note_id, to_note_id, type, directed, weight, created_at, created_by, metadata) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                )
                params = (
                    edge_id,
                    str(user_id),
                    src,
                    dst,
                    type_str,
                    1 if directed else 0,
                    w,
                    now_iso,
                    created_by,
                    json.dumps(metadata) if metadata is not None else None,
                )
                conn.execute(query, params)

                # Log sync event
                payload = {
                    "edge_id": edge_id,
                    "user_id": str(user_id),
                    "from_note_id": src,
                    "to_note_id": dst,
                    "type": type_str,
                    "directed": bool(directed),
                    "weight": float(weight) if weight is not None else 1.0,
                    "created_at": now_iso,
                    "created_by": created_by,
                }
                entity_col = 'entity_id'
                if self.backend_type == BackendType.POSTGRESQL:
                    try:
                        cols = {c.get('name') for c in self.backend.get_table_info('sync_log', connection=conn)}
                        if 'entity_uuid' in cols and 'entity_id' not in cols:
                            entity_col = 'entity_uuid'
                    except Exception as e:
                        logger.debug("sync_log column introspection failed on {}: {}", self.backend_type.value, e)
                assert entity_col in ('entity_id', 'entity_uuid'), f"Unexpected sync_log id column: {entity_col}"
                conn.execute(
                    f"INSERT INTO sync_log (entity, {entity_col}, operation, timestamp, client_id, version, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("note_edges", edge_id, "create", now_iso, self.client_id, 1, json.dumps(payload)),
                )

                # Fetch inserted row
                cur = conn.execute(
                    "SELECT edge_id, user_id, from_note_id, to_note_id, type, directed, weight, created_at, created_by, metadata FROM note_edges WHERE edge_id = ?",
                    (edge_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise CharactersRAGDBError("Inserted edge not found")
                # Normalize metadata JSON
                out = dict(row)
                try:
                    if out.get("metadata") is not None and isinstance(out.get("metadata"), str):
                        out["metadata"] = json.loads(out["metadata"])  # type: ignore[arg-type]
                except Exception:
                    pass
                out["directed"] = bool(out.get("directed", 0))
                return out
        except sqlite3.IntegrityError as e:
            msg = str(e).lower()
            if "unique" in msg or "constraint" in msg:
                raise ConflictError("Duplicate manual link for this user and endpoints") from e
            raise CharactersRAGDBError(f"Failed to create manual note edge: {e}") from e
        except BackendDatabaseError as e:
            # Try to detect unique/duplicate
            msg = str(e).lower()
            if "duplicate key" in msg or "unique constraint" in msg:
                raise ConflictError("Duplicate manual link for this user and endpoints") from e
            raise CharactersRAGDBError(f"Backend error creating manual note edge: {e}") from e

    def delete_manual_note_edge(self, *, user_id: str, edge_id: str) -> bool:
        """Delete a manual note edge by id for the given user. Returns True if deleted."""
        if not user_id or not edge_id:
            raise InputError("user_id and edge_id are required")
        now_iso = self._get_current_utc_timestamp_iso()
        try:
            with self.transaction() as conn:
                cur = conn.execute(
                    "DELETE FROM note_edges WHERE edge_id = ? AND user_id = ?",
                    (edge_id, str(user_id)),
                )
                deleted = cur.rowcount > 0
                if deleted:
                    entity_col = 'entity_id'
                    if self.backend_type == BackendType.POSTGRESQL:
                        try:
                            cols = {c.get('name') for c in self.backend.get_table_info('sync_log', connection=conn)}
                            if 'entity_uuid' in cols and 'entity_id' not in cols:
                                entity_col = 'entity_uuid'
                        except Exception as e:
                            logger.debug("sync_log column introspection failed on {}: {}", self.backend_type.value, e)
                    assert entity_col in ('entity_id', 'entity_uuid'), f"Unexpected sync_log id column: {entity_col}"
                    conn.execute(
                        f"INSERT INTO sync_log (entity, {entity_col}, operation, timestamp, client_id, version, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        ("note_edges", edge_id, "delete", now_iso, self.client_id, 1, json.dumps({"edge_id": edge_id})),
                    )
                return deleted
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to delete manual note edge: {e}") from e
        except BackendDatabaseError as e:
            raise CharactersRAGDBError(f"Backend error deleting manual note edge: {e}") from e

    def _get_current_db_version(self, conn: sqlite3.Connection, table_name: str, pk_col_name: str,
                                pk_value: Any) -> int:
        """
        Fetches the current version of an active (not soft-deleted) record.

        Used for optimistic locking checks before an update or soft delete.

        Args:
            conn: The active sqlite3.Connection.
            table_name: The name of the table to query.
            pk_col_name: The name of the primary key column.
            pk_value: The value of the primary key for the record.

        Returns:
            The version number (integer) of the record if found and active.

        Raises:
            ConflictError: If the record is not found (with `entity` and `entity_id` attributes
                           set in the exception) or if the record is found but is soft-deleted.
        """
        if not (_SAFE_IDENTIFIER_RE.fullmatch(table_name or "") and _SAFE_IDENTIFIER_RE.fullmatch(pk_col_name or "")):
            raise CharactersRAGDBError(
                f"Unsafe identifier in version lookup: table={table_name!r}, column={pk_col_name!r}"
            )
        cursor = conn.execute(f"SELECT version, deleted FROM {table_name} WHERE {pk_col_name} = ?", (pk_value,))
        row = cursor.fetchone()

        if not row:
            logger.warning(f"Record not found in {table_name} with {pk_col_name} = {pk_value} for version check.")
            raise ConflictError(f"Record not found in {table_name}.", entity=table_name, entity_id=pk_value)

        if row['deleted']:
            logger.warning(f"Record in {table_name} with {pk_col_name} = {pk_value} is soft-deleted.")
            raise ConflictError(f"Record is soft-deleted in {table_name}.", entity=table_name, entity_id=pk_value)

        return row['version']

    def _ensure_json_string(self, data: Optional[Union[List, Dict, Set]]) -> Optional[str]:
        """
        Serializes Python list, dict, or set to a JSON string.

        If data is None, returns None. Converts sets to lists before serialization.

        Args:
            data: The Python object (list, dict, set) to serialize, or None.

        Returns:
            A JSON string representation of the data, or None if input was None.
        """
        if data is None:
            return None
        if isinstance(data, Set):
            data = list(data)  # Convert set to list before dumping
        return json.dumps(data)

    def _is_unique_violation(self, error: Exception) -> bool:
        """Return True if the provided backend error represents a unique constraint violation."""
        message = str(error).lower()
        return "unique constraint" in message or "duplicate key" in message

    def _deserialize_row_fields(self, row: sqlite3.Row, json_fields: List[str]) -> Optional[Dict[str, Any]]:
        """
        Converts a sqlite3.Row object to a dictionary, deserializing specified JSON fields.

        If a field listed in `json_fields` contains a string, it attempts to
        parse it as JSON. If parsing fails, the field value is set to None
        and a warning is logged.

        Args:
            row: The sqlite3.Row object to convert. If None, returns None.
            json_fields: A list of field names that should be treated as JSON strings
                         and deserialized.

        Returns:
            A dictionary representing the row with specified fields deserialized,
            or None if the input `row` is None.
        """
        if not row:
            return None
        item = dict(row)
        for field in json_fields:
            if field in item and isinstance(item[field], str):
                try:
                    item[field] = json.loads(item[field])
                except json.JSONDecodeError:
                    pk_val = item.get('id') or item.get('uuid', 'N/A')  # Try to get an identifier
                    logger.warning(
                        f"Failed to decode JSON for field '{field}' in row (ID: {pk_val}). Value: '{item[field][:100]}...'")
                    item[field] = None  # Or sensible default
        return item

    _CHARACTER_CARD_JSON_FIELDS = ['alternate_greetings', 'tags', 'extensions']

    # --- Character Card Methods ---
    @staticmethod
    def _ensure_json_string_from_mixed(data: Optional[Union[List, Dict, Set, str]]) -> Optional[str]:
        """
        Serializes Python list, dict, or set to a JSON string, or passes through an existing string.

        - If data is None, returns None.
        - If data is a list, dict, or set (converted to list), it is serialized to JSON.
        - If data is already a string, it attempts to validate it as JSON.
          - If valid JSON, the string is returned as is.
          - If not valid JSON, the string is returned as is (logged with DEBUG level).
          This behavior assumes that if a string is passed, it is either pre-formatted JSON
          or a plain string intended for a text field that happens to be JSON-serializable.

        Args:
            data: The Python object (list, dict, set, str) to process, or None.

        Returns:
            A JSON string representation of the data, the original string if it is
            valid JSON or a plain string, or None if input `data` was None.
        """
        if data is None:
            return None
        if isinstance(data, str):  # If it's already a string, assume it's valid JSON or pass it through
            try:
                json.loads(data)  # Validate if it's a JSON string
                return data
            except json.JSONDecodeError:
                logger.debug(f"Input string is not valid JSON, passing through: '{data[:100]}...'")
                return data
        if isinstance(data, Set):
            new_data = list(data)
            return json.dumps(new_data)
        return json.dumps(data)

    def add_character_card(self, card_data: Dict[str, Any]) -> Optional[int]:
        """
        Adds a new character card to the database.

        The `client_id` for the new record is taken from the `CharactersRAGDB` instance.
        `version` defaults to 1. `created_at` and `last_modified` are set to the
        current UTC time. Fields like `alternate_greetings`, `tags`, and `extensions`
        (from `_CHARACTER_CARD_JSON_FIELDS`) are stored as JSON strings.

        FTS updates (`character_cards_fts`) and `sync_log` entries for creations
        are handled automatically by SQL triggers.

        Args:
            card_data: A dictionary containing the character card data.
                       Required fields: 'name'.
                       Optional fields include: 'description', 'personality', 'scenario', 'image',
                       'post_history_instructions', 'first_message', 'message_example',
                       'creator_notes', 'system_prompt', 'alternate_greetings' (list/set/JSON str),
                       'tags' (list/set/JSON str), 'creator', 'character_version',
                       'extensions' (dict/JSON str).

        Returns:
            The integer ID of the newly created character card.

        Raises:
            InputError: If required fields (e.g., 'name') are missing or empty.
            ConflictError: If a character card with the same 'name' already exists.
            CharactersRAGDBError: For other database-related errors during insertion.
        """
        required_fields = ['name']
        for field in required_fields:
            if field not in card_data or not card_data[field]:
                raise InputError(f"Required field '{field}' is missing or empty.")

        now = self._get_current_utc_timestamp_iso()

        # Ensure JSON fields are strings or None
        def get_json_field_as_string(field_value):
            if isinstance(field_value, str):
                # Assume it's already a JSON string if it's a string
                return field_value
            return self._ensure_json_string(field_value)

        alt_greetings_json = get_json_field_as_string(card_data.get('alternate_greetings'))
        tags_json = get_json_field_as_string(card_data.get('tags'))
        extensions_json = get_json_field_as_string(card_data.get('extensions'))

        base_query = """
            INSERT INTO character_cards (
                name, description, personality, scenario, image, post_history_instructions,
                first_message, message_example, creator_notes, system_prompt,
                alternate_greetings, tags, creator, character_version, extensions,
                created_at, last_modified, client_id, version, deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            card_data['name'], card_data.get('description'), card_data.get('personality'),
            card_data.get('scenario'), card_data.get('image'), card_data.get('post_history_instructions'),
            card_data.get('first_message'), card_data.get('message_example'), card_data.get('creator_notes'),
            card_data.get('system_prompt'), alt_greetings_json, tags_json,
            card_data.get('creator'), card_data.get('character_version'), extensions_json,
            now, now, self.client_id, # created_at, last_modified, client_id
        )
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                if self.backend_type == BackendType.POSTGRESQL:
                    query = base_query + " RETURNING id"
                    exec_params = params + (1, False)
                    prepared_query, prepared_params = self._prepare_backend_statement(query, exec_params)
                    cursor.execute(prepared_query, prepared_params)
                    row = cursor.fetchone()
                    char_id = row['id'] if row else None
                else:
                    exec_params = params + (1, 0)
                    cursor.execute(base_query, exec_params)
                    char_id = cursor.lastrowid
                logger.info(f"Added character card '{card_data['name']}' with ID: {char_id}.")
                return char_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: character_cards.name" in str(e):
                logger.warning(f"Character card with name '{card_data['name']}' already exists.")
                raise ConflictError(f"Character card with name '{card_data['name']}' already exists.",
                                    entity="character_cards", entity_id=card_data['name']) from e
            raise CharactersRAGDBError(f"Database integrity error adding character card: {e}") from e
        except BackendDatabaseError as e:
            if self._is_unique_violation(e):
                logger.warning(
                    "Character card with name '%s' already exists (backend %s).",
                    card_data['name'],
                    self.backend_type.value,
                )
                raise ConflictError(
                    f"Character card with name '{card_data['name']}' already exists.",
                    entity="character_cards",
                    entity_id=card_data['name'],
                ) from e
            raise CharactersRAGDBError(f"Database integrity error adding character card: {e}") from e
        except CharactersRAGDBError as e:
            logger.error(f"Database error adding character card '{card_data.get('name')}': {e}")
            raise
        return None # Should not be reached

    def get_character_card_by_id(self, character_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific character card by its ID.

        Only non-deleted cards are returned. JSON fields (alternate_greetings,
        tags, extensions as defined in _CHARACTER_CARD_JSON_FIELDS)
        are deserialized from strings to Python objects.

        Args:
            character_id: The integer ID of the character card.

        Returns:
            A dictionary containing the character card data if found and not deleted,
            otherwise None.

        Raises:
            CharactersRAGDBError: For database errors during fetching.
        """
        query = "SELECT * FROM character_cards WHERE id = ? AND deleted = 0"
        try:
            cursor = self.execute_query(query, (character_id,))
            row = cursor.fetchone()
            return self._deserialize_row_fields(row, self._CHARACTER_CARD_JSON_FIELDS)
        except CharactersRAGDBError as e:
            logger.error(f"Database error fetching character card ID {character_id}: {e}")
            raise

    def get_character_card_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific character card by its unique name.

        Only non-deleted cards are returned. JSON fields (see `_CHARACTER_CARD_JSON_FIELDS`)
        are deserialized. Name comparison is case-sensitive as per default SQLite behavior
        because the schema column "name" does not specify `COLLATE NOCASE`.

        Args:
            name: The unique name of the character card.

        Returns:
            A dictionary containing character card data if found and not deleted,
            otherwise None.

        Raises:
            CharactersRAGDBError: For database errors during fetching.
        """
        query = "SELECT * FROM character_cards WHERE name = ? AND deleted = 0"
        try:
            cursor = self.execute_query(query, (name,))
            row = cursor.fetchone()
            return self._deserialize_row_fields(row, self._CHARACTER_CARD_JSON_FIELDS)
        except CharactersRAGDBError as e:
            if self._is_missing_character_table_error(e):
                logger.warning(
                    "Detected missing character_cards table while fetching by name; attempting schema recovery."
                )
                try:
                    self.ensure_character_tables_ready()
                    cursor = self.execute_query(query, (name,))
                    row = cursor.fetchone()
                    return self._deserialize_row_fields(row, self._CHARACTER_CARD_JSON_FIELDS)
                except (CharactersRAGDBError, SchemaError):
                    logger.error(
                        "Schema recovery failed while fetching character card by name '%s'.",
                        name,
                        exc_info=True,
                    )
                    raise
            logger.error(f"Database error fetching character card by name '{name}': {e}")
            raise

    def list_character_cards(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Lists character cards, ordered by name.

        Only non-deleted cards are returned. JSON fields (see `_CHARACTER_CARD_JSON_FIELDS`)
        are deserialized.

        Args:
            limit: The maximum number of cards to return. Defaults to 100.
            offset: The number of cards to skip before starting to return. Defaults to 0.

        Returns:
            A list of dictionaries, each representing a character card.
            The list may be empty if no cards are found.

        Raises:
            CharactersRAGDBError: For database errors during listing.
        """
        query = "SELECT * FROM character_cards WHERE deleted = 0 ORDER BY name LIMIT ? OFFSET ?"
        try:
            cursor = self.execute_query(query, (limit, offset))
            rows = cursor.fetchall()
            return [self._deserialize_row_fields(row, self._CHARACTER_CARD_JSON_FIELDS) for row in rows if row]
        except CharactersRAGDBError as e:
            logger.error(f"Database error listing character cards: {e}")
            raise

    def update_character_card(self, character_id: int, card_data: Dict[str, Any], expected_version: int) -> bool | None:
        """Update character card with optimistic locking."""
        logger.debug(
            f"Starting update_character_card for ID {character_id}, expected_version {expected_version} (SINGLE UPDATE STRATEGY)")

        # If card_data is empty, treat as a no-op as per original behavior.
        # No version check, no transaction, no version bump.
        if not card_data:
            logger.info(f"No data provided in card_data for character card update ID {character_id}. No-op.")
            return True

        now = self._get_current_utc_timestamp_iso()

        try:
            with self.transaction() as conn:
                logger.debug(f"Transaction started. Connection object: {id(conn)}")

                # Initial version check. This also confirms the record exists and is not deleted.
                current_db_version_initial_check = self._get_current_db_version(conn, "character_cards", "id",
                                                                                character_id)
                logger.debug(
                    f"Initial DB version: {current_db_version_initial_check}, Client expected: {expected_version}")

                if current_db_version_initial_check != expected_version:
                    raise ConflictError(
                        f"Update failed: version mismatch (db has {current_db_version_initial_check}, client expected {expected_version}) for character_cards ID {character_id}.",
                        entity="character_cards", entity_id=character_id
                    )

                set_clauses_sql = []
                params_for_set_clause = []
                fields_updated_log = []  # For logging which fields from payload were processed

                # Define fields that can be directly updated and JSON fields
                updatable_direct_fields = [
                    "name", "description", "personality", "scenario", "image",
                    "post_history_instructions", "first_message", "message_example",
                    "creator_notes", "system_prompt", "creator", "character_version"
                ]
                # self._CHARACTER_CARD_JSON_FIELDS is already defined in your class

                for key, value in card_data.items():
                    if key in self._CHARACTER_CARD_JSON_FIELDS:
                        set_clauses_sql.append(f"{key} = ?")
                        # Check if value is already a JSON string
                        if isinstance(value, str):
                            # Assume it's already a JSON string if it's a string
                            params_for_set_clause.append(value)
                        else:
                            params_for_set_clause.append(self._ensure_json_string(value))
                        fields_updated_log.append(key)
                    elif key in updatable_direct_fields:
                        set_clauses_sql.append(f"{key} = ?")
                        params_for_set_clause.append(value)
                        fields_updated_log.append(key)
                    elif key not in ['id', 'created_at', 'last_modified', 'version', 'client_id', 'deleted']:
                        # Log if a key in card_data is not recognized as updatable, but don't error.
                        # This matches the original sequential strategy's behavior of skipping unknown fields.
                        logger.warning(
                            f"Skipping unknown or non-updatable field '{key}' in update_character_card payload.")

                # If expected_version check passed, we always update metadata (last_modified, version, client_id),
                # effectively "touching" the record and bumping its version, even if fields_updated_log is empty
                # (meaning card_data might have contained only non-updatable fields like 'id', or only unknown fields).
                next_version_val = expected_version + 1

                # Add metadata fields to be updated
                set_clauses_sql.extend(["last_modified = ?", "version = ?", "client_id = ?"])
                params_for_set_clause.extend([now, next_version_val, self.client_id])

                # Construct the final query
                # The set_clauses_sql will always have at least the metadata updates if this point is reached.
                final_update_query = f"UPDATE character_cards SET {', '.join(set_clauses_sql)} WHERE id = ? AND version = ? AND deleted = 0"

                # WHERE clause parameters
                where_params = [character_id, expected_version]
                final_params = tuple(params_for_set_clause + where_params)

                logger.debug(f"Executing SINGLE character update query: {final_update_query}")
                logger.debug(f"Params: {final_params}")

                cursor = conn.execute(final_update_query, final_params)
                logger.debug(f"Character Update executed, rowcount: {cursor.rowcount}")

                if cursor.rowcount == 0:
                    # This could happen if a concurrent modification occurred between the initial version check and this UPDATE SQL.
                    # Re-check the record's state to provide a more specific error.
                    check_again_cursor = conn.execute("SELECT version, deleted FROM character_cards WHERE id = ?",
                                                      (character_id,))
                    final_state = check_again_cursor.fetchone()
                    msg = f"Update for character_cards ID {character_id} (expected v{expected_version}) affected 0 rows."
                    if not final_state:
                        msg = f"Character card ID {character_id} disappeared before update completion (expected v{expected_version})."
                    elif final_state['deleted']:
                        msg = f"Character card ID {character_id} was soft-deleted concurrently (expected v{expected_version} for update)."
                    elif final_state[
                        'version'] != expected_version:  # Version changed from what we expected for the WHERE clause
                        msg = f"Character card ID {character_id} version changed to {final_state['version']} concurrently (expected v{expected_version} for update's WHERE clause)."
                    else:  # This case implies the record was found with the correct version and not deleted, yet rowcount was 0. Unlikely.
                        msg = f"Update for character card ID {character_id} (expected v{expected_version}) affected 0 rows for an unknown reason after passing initial checks."
                    raise ConflictError(msg, entity="character_cards", entity_id=character_id)

                log_msg_fields_updated = f"Fields from payload processed: {fields_updated_log if fields_updated_log else 'None'}."
                logger.info(
                    f"Updated character card ID {character_id} (SINGLE UPDATE) from client-expected version {expected_version} to final DB version {next_version_val}. {log_msg_fields_updated}")
                return True

        except sqlite3.IntegrityError as e: # Catch unique constraint violation for name
            if "UNIQUE constraint failed: character_cards.name" in str(e):
                updated_name = card_data.get("name", "[name not in update_data]")
                logger.warning(f"Update for character card ID {character_id} failed: name '{updated_name}' already exists.")
                raise ConflictError(f"Cannot update character card ID {character_id}: name '{updated_name}' already exists.",
                                    entity="character_cards", entity_id=updated_name) from e # Use name as entity_id for this specific conflict
            logger.critical(f"DATABASE IntegrityError during update_character_card (SINGLE UPDATE STRATEGY) for ID {character_id}: {e}", exc_info=True)
            raise CharactersRAGDBError(f"Database integrity error during single update: {e}") from e
        except sqlite3.DatabaseError as e:
            logger.critical(f"DATABASE ERROR during update_character_card (SINGLE UPDATE STRATEGY) for ID {character_id}: {e}", exc_info=True)
            raise CharactersRAGDBError(f"Database error during single update: {e}") from e
        except BackendDatabaseError as e:
            if self._is_unique_violation(e):
                updated_name = card_data.get("name", "[name not in update_data]")
                logger.warning(
                    "Update for character card ID %s failed on backend %s: name '%s' already exists.",
                    character_id,
                    self.backend_type.value,
                    updated_name,
                )
                raise ConflictError(
                    f"Cannot update character card ID {character_id}: name '{updated_name}' already exists.",
                    entity="character_cards",
                    entity_id=updated_name,
                ) from e
            logger.critical(
                "Backend error during update_character_card (SINGLE UPDATE STRATEGY) for ID %s: %s",
                character_id,
                e,
                exc_info=True,
            )
            raise CharactersRAGDBError(f"Database error during single update: {e}") from e
        except ConflictError:  # Re-raise ConflictErrors from _get_current_db_version or manual checks
            logger.warning(f"ConflictError during update_character_card for ID {character_id}.",
                           exc_info=False)  # exc_info=True if needed
            raise
        except InputError:  # Should not happen if initial `if not card_data:` check is there.
            logger.warning(f"InputError during update_character_card for ID {character_id}.", exc_info=False)
            raise
        except Exception as e:  # Catch any other unexpected Python errors
            logger.error(
                f"Unexpected Python error in update_character_card (SINGLE UPDATE STRATEGY) for ID {character_id}: {e}",
                exc_info=True)
            raise CharactersRAGDBError(f"Unexpected error updating character card: {e}") from e

    def soft_delete_character_card(self, character_id: int, expected_version: int) -> bool | None:
        """
        Soft-deletes a character card using optimistic locking.

        Sets the `deleted` flag to 1, updates `last_modified`, increments `version`,
        and sets `client_id`. The operation succeeds only if `expected_version` matches
        the current database version and the card is not already deleted.

        If the card is already soft-deleted (idempotency check), the method considers
        this a success and returns True.

        FTS updates (removal from `character_cards_fts`) and `sync_log` entries for
        deletions (which are technically updates marking as deleted) are handled by SQL triggers.

        Args:
            character_id: The ID of the character card to soft-delete.
            expected_version: The version number the client expects the record to have.

        Returns:
            True if the soft-delete was successful or if the card was already soft-deleted.

        Raises:
            ConflictError: If the card is not found (and not already deleted), or
                           if `expected_version` does not match (and the card is active),
                           or if a concurrent modification prevents the update.
            CharactersRAGDBError: For other database-related errors.
        """
        now = self._get_current_utc_timestamp_iso()
        next_version_val = expected_version + 1

        query = "UPDATE character_cards SET deleted = 1, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ? AND deleted = 0"
        params = (now, next_version_val, self.client_id, character_id, expected_version)

        try:
            with self.transaction() as conn:
                try:
                    current_db_version = self._get_current_db_version(conn, "character_cards", "id", character_id)
                    # If here, record is active.
                except ConflictError as e:
                    # Check if ConflictError from _get_current_db_version was because it's ALREADY soft-deleted.
                    check_status_cursor = conn.execute("SELECT deleted, version FROM character_cards WHERE id = ?",
                                                       (character_id,))
                    record_status = check_status_cursor.fetchone()
                    if record_status and record_status['deleted']:
                        logger.info(
                            f"Character card ID {character_id} already soft-deleted. Soft delete successful (idempotent).")
                        return True
                    # If not found, or some other conflict, re-raise.
                    raise e

                if current_db_version != expected_version:
                    raise ConflictError(
                        f"Soft delete for Character ID {character_id} failed: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity="character_cards", entity_id=character_id
                    )

                cursor = conn.execute(query, params)

                if cursor.rowcount == 0:
                    # Race condition: Record changed between pre-check and UPDATE.
                    check_again_cursor = conn.execute("SELECT version, deleted FROM character_cards WHERE id = ?",
                                                      (character_id,))
                    final_state = check_again_cursor.fetchone()
                    msg = f"Soft delete for Character ID {character_id} (expected v{expected_version}) affected 0 rows."
                    if not final_state:
                        msg = f"Character card ID {character_id} disappeared before soft delete (expected active version {expected_version})."
                    elif final_state['deleted']:
                        # If it got deleted by another process. Consider this success if the state is 'deleted'.
                        logger.info(
                            f"Character card ID {character_id} was soft-deleted concurrently to version {final_state['version']}. Soft delete successful.")
                        return True
                    elif final_state['version'] != expected_version:  # Still active but version changed
                        msg = f"Soft delete for Character ID {character_id} failed: version changed to {final_state['version']} concurrently (expected {expected_version})."
                    else:
                        msg = f"Soft delete for Character ID {character_id} (expected version {expected_version}) affected 0 rows for an unknown reason after passing initial checks."
                    raise ConflictError(msg, entity="character_cards", entity_id=character_id)

                logger.info(
                    f"Soft-deleted character card ID {character_id} (was version {expected_version}), new version {next_version_val}.")
                return True
        except ConflictError:
            raise
        except BackendDatabaseError as e:
            logger.error(
                "Backend error soft-deleting character card ID %s (expected v%s): %s",
                character_id,
                expected_version,
                e,
            )
            raise CharactersRAGDBError(f"Backend error during soft delete: {e}") from e
        except CharactersRAGDBError as e:  # Catches sqlite3.Error from conn.execute
            logger.error(
                f"Database error soft-deleting character card ID {character_id} (expected v{expected_version}): {e}",
                exc_info=True)
            raise

    def restore_character_card(self, character_id: int, expected_version: int) -> bool | None:
        """
        Restores a soft-deleted character card using optimistic locking.

        Sets the `deleted` flag to 0, updates `last_modified`, increments `version`,
        and sets `client_id`. The operation succeeds only if `expected_version` matches
        the current database version and the card is currently deleted.

        If the card is already active (not deleted), the method considers
        this a success and returns True (idempotency).

        Args:
            character_id: The ID of the character card to restore.
            expected_version: The version number the client expects the record to have.

        Returns:
            True if the restore was successful or if the card was already active.

        Raises:
            ConflictError: If the card is not found, or if `expected_version` does
                           not match, or if a concurrent modification prevents the update.
            CharactersRAGDBError: For other database-related errors.
        """
        now = self._get_current_utc_timestamp_iso()
        next_version_val = expected_version + 1

        query = "UPDATE character_cards SET deleted = 0, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ? AND deleted = 1"
        params = (now, next_version_val, self.client_id, character_id, expected_version)

        try:
            with self.transaction() as conn:
                # First check if record exists at all
                check_cursor = conn.execute("SELECT deleted, version FROM character_cards WHERE id = ?",
                                           (character_id,))
                record_status = check_cursor.fetchone()

                if not record_status:
                    raise ConflictError(
                        f"Character card ID {character_id} not found.",
                        entity="character_cards", entity_id=character_id
                    )

                # If already active, return success (idempotent)
                if not record_status['deleted']:
                    logger.info(
                        f"Character card ID {character_id} already active. Restore successful (idempotent).")
                    return True

                # Check version matches
                current_db_version = record_status['version']
                if current_db_version != expected_version:
                    raise ConflictError(
                        f"Restore for Character ID {character_id} failed: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity="character_cards", entity_id=character_id
                    )

                cursor = conn.execute(query, params)

                if cursor.rowcount == 0:
                    # Race condition: Record changed between pre-check and UPDATE.
                    check_again_cursor = conn.execute("SELECT version, deleted FROM character_cards WHERE id = ?",
                                                      (character_id,))
                    final_state = check_again_cursor.fetchone()
                    msg = f"Restore for Character ID {character_id} (expected v{expected_version}) affected 0 rows."
                    if not final_state:
                        msg = f"Character card ID {character_id} disappeared before restore (expected deleted version {expected_version})."
                    elif not final_state['deleted']:
                        # If it got restored by another process. Consider this success.
                        logger.info(
                            f"Character card ID {character_id} was restored concurrently to version {final_state['version']}. Restore successful.")
                        return True
                    elif final_state['version'] != expected_version:
                        msg = f"Restore for Character ID {character_id} failed: version changed to {final_state['version']} concurrently (expected {expected_version})."
                    else:
                        msg = f"Restore for Character ID {character_id} (expected version {expected_version}) affected 0 rows for an unknown reason after passing initial checks."
                    raise ConflictError(msg, entity="character_cards", entity_id=character_id)

                logger.info(
                    f"Restored character card ID {character_id} (was version {expected_version}), new version {next_version_val}.")
                return True
        except ConflictError:
            raise
        except BackendDatabaseError as e:
            logger.error(
                "Backend error restoring character card ID %s (expected v%s): %s",
                character_id,
                expected_version,
                e,
            )
            raise CharactersRAGDBError(f"Backend error during restore: {e}") from e
        except CharactersRAGDBError as e:
            logger.error(
                f"Database error restoring character card ID {character_id} (expected v{expected_version}): {e}",
                exc_info=True)
            raise

    def search_character_cards(self, search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Searches character cards using Full-Text Search (FTS).

        The search is performed on the `character_cards_fts` table, matching against
        'name', 'description', 'personality', 'scenario', and 'system_prompt' fields.
        Returns full card details for matching, non-deleted cards, ordered by relevance (rank).
        JSON fields (see `_CHARACTER_CARD_JSON_FIELDS`) in the results are deserialized.

        Args:
            search_term: The term(s) to search for. Supports FTS query syntax (e.g., "dragon lore").
            limit: The maximum number of results to return. Defaults to 10.

        Returns:
            A list of dictionaries, each representing a matching character card.
            The list can be empty.

        Raises:
            CharactersRAGDBError: For database errors during the search.
        """
        if not search_term.strip():
            logger.warning("Empty character card search term provided; returning no results.")
            return []

        if self.backend_type == BackendType.POSTGRESQL:
            tsquery = FTSQueryTranslator.normalize_query(search_term, 'postgresql')
            if not tsquery:
                logger.debug("FTS normalization produced empty tsquery for input '%s'", search_term)
                return []

            query = """
                SELECT cc.*, ts_rank(cc.character_cards_fts_tsv, to_tsquery('english', ?)) AS rank
                FROM character_cards cc
                WHERE cc.deleted = FALSE
                  AND cc.character_cards_fts_tsv @@ to_tsquery('english', ?)
                ORDER BY rank DESC, cc.last_modified DESC
                LIMIT ?
            """
            try:
                cursor = self.execute_query(query, (tsquery, tsquery, limit))
                rows = cursor.fetchall()
                return [
                    self._deserialize_row_fields(row, self._CHARACTER_CARD_JSON_FIELDS)
                    for row in rows
                    if row
                ]
            except CharactersRAGDBError as exc:
                logger.error("PostgreSQL FTS search failed for character cards term '%s': %s", search_term, exc)
                raise

        # Escape embedded quotes to avoid breaking the literal phrase wrapper
        safe_literal = search_term.replace('"', '""')
        safe_search_term = f'"{safe_literal}"'
        query = """
                SELECT cc.*
                FROM character_cards_fts, character_cards cc
                WHERE character_cards_fts.rowid = cc.id
                  AND character_cards_fts MATCH ?
                  AND cc.deleted = 0
                ORDER BY cc.last_modified DESC
                LIMIT ?
                """
        try:
            cursor = self.execute_query(query, (search_term, limit))
            rows = cursor.fetchall()
            return [self._deserialize_row_fields(row, self._CHARACTER_CARD_JSON_FIELDS) for row in rows if row]
        except CharactersRAGDBError as e:
            logger.error(f"Error searching character cards for '{safe_search_term}': {e}")
            raise

    def _check_json_support(self) -> bool:
        """
        Check if the current SQLite version supports JSON functions.

        Returns:
            True if JSON functions are available, False otherwise.
        """
        if self.backend_type != BackendType.SQLITE:
            return False

        try:
            cursor = self.execute_query("SELECT json('{}') as test")
            cursor.fetchone()
            return True
        except (sqlite3.OperationalError, CharactersRAGDBError):
            return False

    def search_character_cards_by_tags(self, tag_keywords: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search character cards efficiently by their tags using database-level filtering.

        This method provides significant performance improvements over loading all cards
        into memory by using SQLite JSON functions when available, or falling back
        to a normalized tag approach if JSON functions are not supported.

        Args:
            tag_keywords: List of tag strings to search for (case-insensitive).
            limit: Maximum number of results to return. Defaults to 10.

        Returns:
            List of character card dictionaries that contain any of the specified tags.
            Results are ordered by name and limited to non-deleted cards.

        Raises:
            CharactersRAGDBError: For database errors during the search.
            InputError: If tag_keywords is empty or contains invalid values.
        """
        if not tag_keywords:
            raise InputError("tag_keywords cannot be empty")

        # Normalize tag keywords for case-insensitive matching
        normalized_tags = [tag.lower().strip() for tag in tag_keywords if tag.strip()]
        if not normalized_tags:
            raise InputError("No valid tag keywords provided after normalization")

        logger.debug(f"Searching character cards by tags: {normalized_tags}")

        # Check if SQLite supports JSON functions
        if self._check_json_support():
            return self._search_cards_by_tags_json(normalized_tags, limit)
        else:
            # Fallback to loading and filtering in Python (original approach but optimized)
            logger.warning("SQLite JSON functions not available, using fallback tag search method")
            return self._search_cards_by_tags_fallback(normalized_tags, limit)

    def _search_cards_by_tags_json(self, normalized_tags: List[str], limit: int) -> List[Dict[str, Any]]:
        """
        Search character cards by tags using SQLite JSON functions.

        This is the optimal approach for SQLite versions that support JSON functions.
        """
        try:
            # Build query with JSON_EACH to extract and check tags
            placeholders = ','.join('?' for _ in normalized_tags)
            query = f"""
                SELECT DISTINCT cc.*
                FROM character_cards cc,
                     json_each(cc.tags) je
                WHERE cc.deleted = 0
                  AND cc.tags IS NOT NULL
                  AND cc.tags != 'null'
                  AND lower(trim(je.value)) IN ({placeholders})
                ORDER BY cc.name
                LIMIT ?
            """

            params = normalized_tags + [limit]
            cursor = self.execute_query(query, params)
            rows = cursor.fetchall()

            result = [self._deserialize_row_fields(row, self._CHARACTER_CARD_JSON_FIELDS) for row in rows if row]
            logger.debug(f"Found {len(result)} character cards matching tags using JSON functions")
            return result

        except CharactersRAGDBError as e:
            logger.error(f"Database error in JSON-based tag search: {e}")
            raise
        except Exception as e:
            # JSON function might have failed, log and re-raise as database error
            logger.error(f"Unexpected error in JSON-based tag search: {e}")
            raise CharactersRAGDBError(f"JSON tag search failed: {e}") from e

    def _search_cards_by_tags_fallback(self, normalized_tags: List[str], limit: int) -> List[Dict[str, Any]]:
        """
        Fallback tag search that loads cards and filters in Python.

        This is used when SQLite doesn't support JSON functions, but is optimized
        to only load necessary data and exit early when limit is reached.
        """
        try:
            # Use a reasonable batch size to avoid loading everything at once
            batch_size = min(1000, limit * 10)  # Load 10x limit as heuristic
            offset = 0
            results = []
            normalized_tags_set = set(normalized_tags)

            while len(results) < limit:
                # Load cards in batches
                query = "SELECT * FROM character_cards WHERE deleted = 0 ORDER BY name LIMIT ? OFFSET ?"
                cursor = self.execute_query(query, (batch_size, offset))
                batch_rows = cursor.fetchall()

                if not batch_rows:
                    break  # No more cards to process

                # Process this batch
                for row in batch_rows:
                    if len(results) >= limit:
                        break

                    card = self._deserialize_row_fields(row, self._CHARACTER_CARD_JSON_FIELDS)

                    # Check if card has matching tags
                    tags_data = card.get('tags')
                    if tags_data:
                        try:
                            # Handle both cases: already deserialized list or JSON string
                            if isinstance(tags_data, list):
                                tags_list = tags_data  # Already deserialized by _deserialize_row_fields
                            elif isinstance(tags_data, str):
                                tags_list = json.loads(tags_data)  # Parse JSON string
                            else:
                                tags_list = []  # Fallback for unexpected types

                            if isinstance(tags_list, list):
                                card_tags_normalized = {str(tag).lower().strip() for tag in tags_list}
                                # Check for intersection with our target tags
                                if not card_tags_normalized.isdisjoint(normalized_tags_set):
                                    results.append(card)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in tags for character card ID {card.get('id')}: {tags_data}")
                            continue

                offset += batch_size

                # If we got fewer rows than batch_size, we've reached the end
                if len(batch_rows) < batch_size:
                    break

            logger.debug(f"Found {len(results)} character cards matching tags using fallback method")
            return results

        except CharactersRAGDBError as e:
            logger.error(f"Database error in fallback tag search: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in fallback tag search: {e}")
            raise CharactersRAGDBError(f"Fallback tag search failed: {e}") from e

    # --- Conversation Methods ---
    def _normalize_conversation_state(self, state: Optional[str]) -> str:
        """
        Normalize and validate conversation state, applying the default when missing.
        """
        if state is None:
            return self._DEFAULT_CONVERSATION_STATE
        if not isinstance(state, str):
            raise InputError(f"Conversation state must be a string. Got: {state!r}")
        normalized = state.strip().lower()
        if not normalized:
            raise InputError("Conversation state cannot be empty.")
        if normalized not in self._ALLOWED_CONVERSATION_STATES:
            raise InputError(
                f"Invalid conversation state '{state}'. Allowed: {', '.join(self._ALLOWED_CONVERSATION_STATES)}"
            )
        return normalized

    @staticmethod
    def _normalize_nullable_text(value: Any) -> Optional[str]:
        """Normalize optional text fields; returns None for empty/whitespace."""
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return str(value)

    def add_conversation(self, conv_data: Dict[str, Any]) -> Optional[str]:
        """
        Adds a new conversation to the database.

        `id` (UUID string) can be provided; if not, it's auto-generated.
        `root_id` (UUID string) should be provided; if not, `id` is used as `root_id`.
        `character_id` is required in `conv_data`.
        `client_id` defaults to the DB instance's `client_id` if not provided in `conv_data`.
        `version` defaults to 1. `created_at` and `last_modified` are set to current UTC time.

        FTS updates (`conversations_fts` for the title) and `sync_log` entries for creations
        are handled automatically by SQL triggers.

        Args:
            conv_data: A dictionary containing conversation data.
                       Required: 'character_id'.
                       Recommended: 'id' (if providing own UUID), 'root_id'.
                       Optional: 'forked_from_message_id', 'parent_conversation_id',
                                 'title', 'rating' (1-5), 'client_id'.

        Returns:
            The string UUID of the newly created conversation.

        Raises:
            InputError: If required fields like 'character_id' are missing, or if
                        'client_id' is missing and not set on the DB instance.
            ConflictError: If a conversation with the provided 'id' already exists.
            CharactersRAGDBError: For other database-related errors.
        """
        conv_id = conv_data.get('id') or self._generate_uuid()
        root_id = conv_data.get('root_id') or conv_id  # If root_id not given, this is a new root.

        if 'character_id' not in conv_data:
            raise InputError("Required field 'character_id' is missing for conversation.")

        client_id = conv_data.get('client_id') or self.client_id
        if not client_id:
            raise InputError("Client ID is required for conversation (either in conv_data or DB instance).")

        state = self._normalize_conversation_state(conv_data.get('state'))
        topic_label = self._normalize_nullable_text(conv_data.get('topic_label'))
        cluster_id = self._normalize_nullable_text(conv_data.get('cluster_id'))
        source = self._normalize_nullable_text(conv_data.get('source'))
        external_ref = self._normalize_nullable_text(conv_data.get('external_ref'))

        now = self._get_current_utc_timestamp_iso()
        query = """
                INSERT INTO conversations (id, root_id, forked_from_message_id, parent_conversation_id, \
                                           character_id, title, state, topic_label, cluster_id, source, external_ref, rating, \
                                           created_at, last_modified, client_id, version, deleted) \
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) \
                """ # created_at added
        if self.backend_type == BackendType.POSTGRESQL:
            params = (
                conv_id, root_id, conv_data.get('forked_from_message_id'),
                conv_data.get('parent_conversation_id'), conv_data['character_id'],
                conv_data.get('title'), state, topic_label, cluster_id, source, external_ref, conv_data.get('rating'),
                now, now, client_id, 1, False
            )
        else:
            params = (
                conv_id, root_id, conv_data.get('forked_from_message_id'),
                conv_data.get('parent_conversation_id'), conv_data['character_id'],
                conv_data.get('title'), state, topic_label, cluster_id, source, external_ref, conv_data.get('rating'),
                now, now, client_id, 1, 0
            )
        try:
            with self.transaction() as conn:
                conn.execute(query, params)
            logger.info(f"Added conversation ID: {conv_id}.")
            return conv_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: conversations.id" in str(e):
                 raise ConflictError(f"Conversation with ID '{conv_id}' already exists.", entity="conversations", entity_id=conv_id) from e
            # Could also be FK violation for character_id, etc.
            raise CharactersRAGDBError(f"Database integrity error adding conversation: {e}") from e
        except CharactersRAGDBError as e:
            logger.error(f"Database error adding conversation: {e}")
            raise
        return None # Should not be reached

    def get_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific conversation by its UUID.

        Only non-deleted conversations are returned.

        Args:
            conversation_id: The string UUID of the conversation.

        Returns:
            A dictionary containing the conversation's data if found and not deleted,
            otherwise None.

        Raises:
            CharactersRAGDBError: For database errors during fetching.
        """
        query = "SELECT * FROM conversations WHERE id = ? AND deleted = 0"
        try:
            cursor = self.execute_query(query, (conversation_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except CharactersRAGDBError as e:
            logger.error(f"Database error fetching conversation ID {conversation_id}: {e}")
            raise

    def get_conversations_for_character(
        self,
        character_id: int,
        limit: int = 50,
        offset: int = 0,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lists conversations associated with a specific character ID.

        Only non-deleted conversations are returned, ordered by `last_modified` descending.
        Results are automatically scoped to the active client's conversations unless
        `client_id` is explicitly provided. Pass `client_id=None` to disable scoping.

        Args:
            character_id: The integer ID of the character.
            limit: The maximum number of conversations to return. Defaults to 50.
            offset: The number of conversations to skip. Defaults to 0.
            client_id: Optional override for the client scope. Defaults to the
                database instance's `client_id`. Use `None` to query across all
                clients (only for privileged workflows).

        Returns:
            A list of dictionaries, each representing a conversation. Can be empty.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        client_filter = self.client_id if client_id is None else client_id
        query = (
            "SELECT * FROM conversations "
            "WHERE character_id = ? AND deleted = 0"
        )
        params: List[Any] = [character_id]

        if client_filter is not None:
            query += " AND client_id = ?"
            params.append(client_filter)

        query += " ORDER BY last_modified DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        try:
            cursor = self.execute_query(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError as e:
            logger.error(f"Database error fetching conversations for character ID {character_id}: {e}")
            raise

    def count_conversations_for_user(self, client_id: str) -> int:
        """
        Count total non-deleted conversations for a given user (client_id).

        Args:
            client_id: The user/client identifier as string.

        Returns:
            Integer count of conversations.

        Raises:
            CharactersRAGDBError on database failure.
        """
        query = "SELECT COUNT(*) as cnt FROM conversations WHERE client_id = ? AND deleted = 0"
        try:
            cursor = self.execute_query(query, (client_id,))
            row = cursor.fetchone()
            return int(row[0] if row else 0)
        except CharactersRAGDBError as e:
            logger.error(f"Database error counting conversations for client_id {client_id}: {e}")
            raise

    def get_conversations_for_user(self, client_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List non-deleted conversations for a given user (client_id), ordered by last_modified DESC.

        Args:
            client_id: The user/client identifier as string.
            limit: Max number of rows to return.
            offset: Number of rows to skip.

        Returns:
            List of conversation records.

        Raises:
            CharactersRAGDBError on database failure.
        """
        query = (
            "SELECT * FROM conversations "
            "WHERE client_id = ? AND deleted = 0 "
            "ORDER BY last_modified DESC LIMIT ? OFFSET ?"
        )
        try:
            cursor = self.execute_query(query, (client_id, limit, offset))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except CharactersRAGDBError as e:
            logger.error(f"Database error listing conversations for client_id {client_id}: {e}")
            raise

    def count_messages_for_conversation(self, conversation_id: str, include_deleted: bool = False) -> int:
        """
        Count messages for a conversation, ensuring the parent conversation is active.

        Args:
            conversation_id: Conversation UUID
            include_deleted: If True, include soft-deleted messages

        Returns:
            Integer count of messages.

        Raises:
            CharactersRAGDBError on database failure.
        """
        base_query = (
            "SELECT COUNT(1) FROM messages m "
            "JOIN conversations c ON m.conversation_id = c.id "
            "WHERE m.conversation_id = ? AND c.deleted = 0"
        )
        params = [conversation_id]
        if not include_deleted:
            base_query += " AND m.deleted = 0"
        try:
            cursor = self.execute_query(base_query, tuple(params))
            row = cursor.fetchone()
            # row may be tuple or dict depending on connection row factory
            if row is None:
                return 0
            try:
                return int(row[0])
            except Exception:
                return int(row.get("COUNT(1)") or row.get("count") or 0)
        except CharactersRAGDBError as e:
            logger.error(f"Database error counting messages for conversation {conversation_id}: {e}")
            raise

    def count_messages_for_conversations(
        self,
        conversation_ids: List[str],
        include_deleted: bool = False,
    ) -> Dict[str, int]:
        """
        Count messages for multiple conversations in a single query.

        Args:
            conversation_ids: List of conversation UUIDs.
            include_deleted: If True, include soft-deleted messages.

        Returns:
            Mapping of conversation_id -> message count.
        """
        if not conversation_ids:
            return {}
        placeholders = ",".join(["?"] * len(conversation_ids))
        base_query = (
            f"SELECT m.conversation_id, COUNT(1) as cnt "
            f"FROM messages m "
            f"JOIN conversations c ON m.conversation_id = c.id "
            f"WHERE m.conversation_id IN ({placeholders}) AND c.deleted = 0"
        )
        if not include_deleted:
            base_query += " AND m.deleted = 0"
        base_query += " GROUP BY m.conversation_id"
        try:
            cursor = self.execute_query(base_query, tuple(conversation_ids))
            rows = cursor.fetchall()
            result: Dict[str, int] = {cid: 0 for cid in conversation_ids}
            for row in rows:
                if isinstance(row, dict):
                    conv_id = row.get("conversation_id")
                    cnt = row.get("cnt") or row.get("COUNT(1)") or 0
                else:
                    conv_id = row[0]
                    cnt = row[1]
                if conv_id is not None:
                    result[str(conv_id)] = int(cnt or 0)
            return result
        except CharactersRAGDBError as e:
            logger.error("Database error counting messages for conversations: %s", e)
            raise

    def get_latest_message_for_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the most recent non-deleted message for a conversation."""
        query = (
            "SELECT m.id, m.timestamp, m.content, m.sender "
            "FROM messages m JOIN conversations c ON m.conversation_id = c.id "
            "WHERE m.conversation_id = ? AND m.deleted = 0 AND c.deleted = 0 "
            "ORDER BY m.timestamp DESC LIMIT 1"
        )
        try:
            cursor = self.execute_query(query, (conversation_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row) if isinstance(row, dict) else {
                "id": row[0],
                "timestamp": row[1],
                "content": row[2],
                "sender": row[3],
            }
        except CharactersRAGDBError as exc:
            logger.error("Database error fetching latest message for conversation %s: %s", conversation_id, exc)
            raise

    def count_messages_since(
        self,
        conversation_id: str,
        since_message_id: Optional[str],
    ) -> int:
        """Count messages after the given message_id within a conversation."""
        if not since_message_id:
            return self.count_messages_for_conversation(conversation_id)

        try:
            since_message = self.get_message_by_id(since_message_id)
        except CharactersRAGDBError:
            return self.count_messages_for_conversation(conversation_id)

        if not since_message:
            return self.count_messages_for_conversation(conversation_id)

        since_timestamp = since_message.get("timestamp")
        if not since_timestamp:
            return self.count_messages_for_conversation(conversation_id)

        query = (
            "SELECT COUNT(1) FROM messages m "
            "JOIN conversations c ON m.conversation_id = c.id "
            "WHERE m.conversation_id = ? AND m.deleted = 0 AND c.deleted = 0 "
            "AND m.timestamp > ?"
        )
        try:
            cursor = self.execute_query(query, (conversation_id, since_timestamp))
            row = cursor.fetchone()
            if row is None:
                return 0
            try:
                return int(row[0])
            except Exception:
                return int(row.get("COUNT(1)") or row.get("count") or 0)
        except CharactersRAGDBError as exc:
            logger.error("Database error counting messages after %s: %s", since_message_id, exc)
            raise

    def upsert_conversation_cluster(
        self,
        cluster_id: str,
        *,
        title: Optional[str] = None,
        centroid: Optional[str] = None,
        size: int = 0,
    ) -> bool:
        """Insert or update a conversation cluster metadata row."""
        now = self._get_current_utc_timestamp_iso()
        try:
            if self.backend_type == BackendType.SQLITE:
                query = (
                    "INSERT INTO conversation_clusters "
                    "(cluster_id, title, centroid, size, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(cluster_id) DO UPDATE SET "
                    "title = excluded.title, centroid = excluded.centroid, size = excluded.size, "
                    "updated_at = excluded.updated_at"
                )
                self.execute_query(query, (cluster_id, title, centroid, int(size), now, now), commit=True)
                return True

            query = (
                "INSERT INTO conversation_clusters "
                "(cluster_id, title, centroid, size, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, NOW(), NOW()) "
                "ON CONFLICT (cluster_id) DO UPDATE SET "
                "title = EXCLUDED.title, centroid = EXCLUDED.centroid, size = EXCLUDED.size, "
                "updated_at = NOW()"
            )
            self.backend.execute(query, (cluster_id, title, centroid, int(size)))
            return True
        except Exception as exc:
            logger.error("Failed to upsert conversation cluster %s: %s", cluster_id, exc)
            return False

    def get_conversation_cluster(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a conversation cluster metadata row by ID."""
        query = "SELECT * FROM conversation_clusters WHERE cluster_id = ?"
        try:
            cursor = self.execute_query(query, (cluster_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row) if isinstance(row, dict) else {
                "cluster_id": row[0],
                "title": row[1],
                "centroid": row[2],
                "size": row[3],
                "created_at": row[4],
                "updated_at": row[5],
            }
        except CharactersRAGDBError as exc:
            logger.error("Failed to fetch conversation cluster %s: %s", cluster_id, exc)
            raise

    def count_conversations_for_user_by_character(self, client_id: str, character_id: int) -> int:
        """
        Count non-deleted conversations for a given user scoped to a specific character.

        Args:
            client_id: The user/client identifier as string.
            character_id: Character ID to scope the count.

        Returns:
            Integer count of conversations.

        Raises:
            CharactersRAGDBError on database failure.
        """
        query = (
            "SELECT COUNT(1) FROM conversations WHERE client_id = ? AND character_id = ? AND deleted = 0"
        )
        try:
            cursor = self.execute_query(query, (client_id, character_id))
            row = cursor.fetchone()
            if row is None:
                return 0
            try:
                return int(row[0])
            except Exception:
                return int(row.get("COUNT(1)") or row.get("count") or 0)
        except CharactersRAGDBError as e:
            logger.error(
                f"Database error counting conversations for client_id {client_id} and character_id {character_id}: {e}"
            )
            raise

    def get_conversations_for_user_and_character(self, client_id: str, character_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List non-deleted conversations for a given user scoped to a specific character.

        Args:
            client_id: The user/client identifier as string.
            character_id: Character ID to scope the list.
            limit: Max number of rows to return.
            offset: Number of rows to skip.

        Returns:
            List of conversation records.

        Raises:
            CharactersRAGDBError on database failure.
        """
        query = (
            "SELECT * FROM conversations "
            "WHERE client_id = ? AND character_id = ? AND deleted = 0 "
            "ORDER BY last_modified DESC LIMIT ? OFFSET ?"
        )
        try:
            cursor = self.execute_query(query, (client_id, character_id, limit, offset))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except CharactersRAGDBError as e:
            logger.error(
                f"Database error listing conversations for client_id {client_id} and character_id {character_id}: {e}"
            )
            raise

    def update_conversation(self, conversation_id: str, update_data: Dict[str, Any], expected_version: int) -> bool | None:
        """
        Updates an existing conversation using optimistic locking.

        The update succeeds if `expected_version` matches the current database version.
        `version` is incremented and `last_modified` updated to current UTC time.
        Note: this method does not change ownership; the `client_id` field is preserved
        unless explicitly provided in `update_data` by a privileged caller.

        Updatable fields from `update_data`: 'title', 'rating', 'state', 'topic_label',
        'topic_label_source', 'topic_last_tagged_at', 'topic_last_tagged_message_id',
        'cluster_id', 'source', 'external_ref'. Other fields are ignored.
        If `update_data` is empty or contains no updatable fields, metadata (version,
        last_modified, client_id) is still updated if the version check passes.

        FTS updates (`conversations_fts` for title changes) and `sync_log` entries
        are handled by SQL triggers.

        Args:
            conversation_id: The UUID of the conversation to update.
            update_data: Dictionary with fields to update (e.g., 'title', 'rating').
            expected_version: The client's expected version of the record.

        Returns:
            True if the update was successful.

        Raises:
            ConflictError: If the conversation is not found, is soft-deleted,
                           or if `expected_version` does not match the current database version.
            CharactersRAGDBError: For other database-related errors (e.g., rating out of range
                                  if not caught by this method but by DB constraint).
        """
        logger.debug(
            f"Starting update_conversation for ID {conversation_id}, expected_version {expected_version} (FTS handled by DB triggers)")

        if 'rating' in update_data and update_data['rating'] is not None:
             # Basic check, DB has CHECK constraint too
            if not (1 <= update_data['rating'] <= 5):
                raise InputError(f"Rating must be between 1 and 5. Got: {update_data['rating']}")

        if 'state' in update_data:
            state_val = update_data.get('state')
            if state_val is None:
                raise InputError("Conversation state cannot be empty.")
            update_data['state'] = self._normalize_conversation_state(state_val)

        if 'topic_label_source' in update_data:
            source_val = update_data.get('topic_label_source')
            if source_val is None:
                update_data['topic_label_source'] = None
            else:
                normalized_source = str(source_val).strip().lower()
                if normalized_source not in {"manual", "auto"}:
                    raise InputError("topic_label_source must be 'manual' or 'auto'.")
                update_data['topic_label_source'] = normalized_source

        if 'topic_last_tagged_at' in update_data:
            tag_val = update_data.get('topic_last_tagged_at')
            if isinstance(tag_val, datetime):
                if tag_val.tzinfo is None:
                    tag_val = tag_val.replace(tzinfo=timezone.utc)
                tag_val = tag_val.astimezone(timezone.utc).isoformat()
            update_data['topic_last_tagged_at'] = tag_val

        now = self._get_current_utc_timestamp_iso()

        try:
            with self.transaction() as conn:
                logger.debug(f"Conversation update transaction started. Connection object: {id(conn)}")

                # Fetch current state, including rowid (though not used for manual FTS, it's good practice to fetch if available)
                # and current title for potential non-FTS related "title_changed" logic.
                cursor_check = conn.execute("SELECT rowid, title, version, deleted FROM conversations WHERE id = ?",
                                            (conversation_id,))
                current_state = cursor_check.fetchone()

                if not current_state:
                    raise ConflictError(f"Conversation ID {conversation_id} not found for update.",
                                        entity="conversations", entity_id=conversation_id)
                if current_state['deleted']:
                    raise ConflictError(f"Conversation ID {conversation_id} is deleted, cannot update.",
                                        entity="conversations", entity_id=conversation_id)

                current_db_version = current_state['version']
                current_title = current_state['title']  # For logging or other conditional logic if title changed

                logger.debug(
                    f"Conversation current DB version: {current_db_version}, Expected by client: {expected_version}, Current title: {current_title}")

                if current_db_version != expected_version:
                    raise ConflictError(
                        f"Conversation ID {conversation_id} update failed: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity="conversations", entity_id=conversation_id
                    )

                fields_to_update_sql = []
                params_for_set_clause = []
                title_changed_flag = False  # Flag to indicate if title was among the updated fields and changed value

                # Process 'title' if present in update_data
                if 'title' in update_data:
                    fields_to_update_sql.append("title = ?")
                    params_for_set_clause.append(update_data['title'])
                    if update_data['title'] != current_title:
                        title_changed_flag = True

                # Process 'rating' if present in update_data
                if 'rating' in update_data:
                    fields_to_update_sql.append("rating = ?")
                    params_for_set_clause.append(update_data['rating'])

                if 'state' in update_data:
                    fields_to_update_sql.append("state = ?")
                    params_for_set_clause.append(update_data['state'])

                if 'topic_label' in update_data:
                    fields_to_update_sql.append("topic_label = ?")
                    params_for_set_clause.append(self._normalize_nullable_text(update_data.get('topic_label')))

                if 'topic_label_source' in update_data:
                    fields_to_update_sql.append("topic_label_source = ?")
                    params_for_set_clause.append(update_data.get('topic_label_source'))

                if 'topic_last_tagged_at' in update_data:
                    fields_to_update_sql.append("topic_last_tagged_at = ?")
                    params_for_set_clause.append(update_data.get('topic_last_tagged_at'))

                if 'topic_last_tagged_message_id' in update_data:
                    fields_to_update_sql.append("topic_last_tagged_message_id = ?")
                    params_for_set_clause.append(
                        self._normalize_nullable_text(update_data.get('topic_last_tagged_message_id'))
                    )

                if 'cluster_id' in update_data:
                    fields_to_update_sql.append("cluster_id = ?")
                    params_for_set_clause.append(self._normalize_nullable_text(update_data.get('cluster_id')))

                if 'source' in update_data:
                    fields_to_update_sql.append("source = ?")
                    params_for_set_clause.append(self._normalize_nullable_text(update_data.get('source')))

                if 'external_ref' in update_data:
                    fields_to_update_sql.append("external_ref = ?")
                    params_for_set_clause.append(self._normalize_nullable_text(update_data.get('external_ref')))

                next_version_val = expected_version + 1  # Version always increments on successful update

                if not fields_to_update_sql:
                    # This block executes if update_data was empty or contained no recognized updatable fields.
                    # We still need to update last_modified and version due to the successful version check.
                    logger.info(
                        f"No specific updatable fields (e.g. title, rating) found for conversation {conversation_id}. Updating metadata only.")
                    main_update_query = "UPDATE conversations SET last_modified = ?, version = ? WHERE id = ? AND version = ? AND deleted = 0"
                    main_update_params = (now, next_version_val, conversation_id, expected_version)
                else:
                    # If specific fields were found, add metadata fields to the update
                    fields_to_update_sql.extend(["last_modified = ?", "version = ?"])

                    final_set_values = params_for_set_clause[:]  # Copy of values for specific fields
                    final_set_values.extend([now, next_version_val])  # Add values for metadata fields

                    main_update_query = f"UPDATE conversations SET {', '.join(fields_to_update_sql)} WHERE id = ? AND version = ? AND deleted = 0"
                    main_update_params = tuple(final_set_values + [conversation_id, expected_version])

                logger.debug(f"Executing MAIN conversation update query: {main_update_query}")
                logger.debug(f"Params: {main_update_params}")

                cursor_main = conn.execute(main_update_query, main_update_params)
                logger.debug(f"Main Conversation Update executed, rowcount: {cursor_main.rowcount}")

                if cursor_main.rowcount == 0:
                    # This could happen if a concurrent modification occurred between the version check and this UPDATE.
                    # Or if the record was deleted concurrently.
                    # Re-check the state to provide a more accurate error.
                    check_again_cursor = conn.execute("SELECT version, deleted FROM conversations WHERE id = ?",
                                                      (conversation_id,))
                    final_state = check_again_cursor.fetchone()
                    msg = f"Main update for conversation ID {conversation_id} (expected v{expected_version}) affected 0 rows."
                    if not final_state:
                        msg = f"Conversation ID {conversation_id} disappeared before update completion (expected v{expected_version})."
                    elif final_state['deleted']:
                        msg = f"Conversation ID {conversation_id} was soft-deleted concurrently (expected v{expected_version} for update)."
                    elif final_state['version'] != expected_version:
                        msg = f"Conversation ID {conversation_id} version changed to {final_state['version']} concurrently (expected v{expected_version} for update)."
                    else:  # Should not happen if rowcount is 0 and version check was successful.
                        msg = f"Main update for conversation ID {conversation_id} (expected v{expected_version}) affected 0 rows for an unknown reason after passing initial checks."
                    raise ConflictError(msg, entity="conversations", entity_id=conversation_id)

                # FTS synchronization is handled by database triggers.
                # No manual FTS DML (DELETE/INSERT on conversations_fts) is performed here.

                logger.info(
                    f"Updated conversation ID {conversation_id} from version {expected_version} to version {next_version_val} (FTS handled by DB triggers). Title changed: {title_changed_flag}")
                return True

        except sqlite3.IntegrityError as e: # e.g. rating check constraint
            raise CharactersRAGDBError(f"Database integrity error during update_conversation: {e}") from e
        except sqlite3.DatabaseError as e:
            # This broad catch is for unexpected SQLite errors, including potential "malformed" if it still occurs.
            logger.critical(f"DATABASE ERROR during update_conversation (FTS handled by DB triggers): {e}")
            logger.critical(f"Error details: {str(e)}")
            # Specific handling for "malformed" can be added if needed, but the goal is to prevent it.
            raise CharactersRAGDBError(f"Database error during update_conversation: {e}") from e
        except ConflictError:  # Re-raise ConflictErrors for tests or callers to handle
            raise
        except InputError:
            raise
        except CharactersRAGDBError as e:
            logger.error(f"Application-level database error in update_conversation for ID {conversation_id}: {e}",
                         exc_info=True)
            raise
        except Exception as e:  # Catch-all for any other unexpected Python errors
            logger.error(f"Unexpected Python error in update_conversation for ID {conversation_id}: {e}", exc_info=True)
            raise CharactersRAGDBError(f"Unexpected error during update_conversation: {e}") from e

    def soft_delete_conversation(self, conversation_id: str, expected_version: int) -> bool | None:
        """
        Soft-deletes a conversation using optimistic locking.

        Sets the `deleted` flag to 1, updates `last_modified`, increments `version`,
        and sets `client_id`. Succeeds if `expected_version` matches the current
        DB version and the record is active.
        If already soft-deleted, returns True (idempotent).

        FTS updates (removal from `conversations_fts`) and `sync_log` entries
        are handled by SQL triggers.

        Args:
            conversation_id: The UUID of the conversation to soft-delete.
            expected_version: The client's expected version of the record.

        Returns:
            True if the soft-delete was successful or if the conversation was already soft-deleted.

        Raises:
            ConflictError: If not found (and not already deleted), or if active with a version mismatch.
            CharactersRAGDBError: For other database errors.
        """
        now = self._get_current_utc_timestamp_iso()
        next_version_val = expected_version + 1

        query = "UPDATE conversations SET deleted = 1, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ? AND deleted = 0"
        params = (now, next_version_val, self.client_id, conversation_id, expected_version)

        try:
            with self.transaction() as conn:
                try:
                    current_db_version = self._get_current_db_version(conn, "conversations", "id", conversation_id)
                except ConflictError as e:
                    check_status_cursor = conn.execute("SELECT deleted, version FROM conversations WHERE id = ?",
                                                       (conversation_id,))
                    record_status = check_status_cursor.fetchone()
                    if record_status and record_status['deleted']:
                        logger.info(f"Conversation ID {conversation_id} already soft-deleted. Success (idempotent).")
                        return True
                    raise e # Re-raise if not found or other conflict

                if current_db_version != expected_version:
                    raise ConflictError(
                        f"Soft delete for Conversation ID {conversation_id} failed: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity="conversations", entity_id=conversation_id
                    )

                cursor = conn.execute(query, params)

                if cursor.rowcount == 0:
                    check_again_cursor = conn.execute("SELECT version, deleted FROM conversations WHERE id = ?",
                                                      (conversation_id,))
                    final_state = check_again_cursor.fetchone()
                    msg = f"Soft delete for conversation ID {conversation_id} (expected v{expected_version}) affected 0 rows."
                    if not final_state:
                        msg = f"Conversation ID {conversation_id} disappeared."
                    elif final_state['deleted']:
                        logger.info(f"Conversation ID {conversation_id} was soft-deleted concurrently. Success.")
                        return True
                    elif final_state['version'] != expected_version:
                        msg = f"Conversation ID {conversation_id} version changed to {final_state['version']} concurrently."
                    else:
                        msg = f"Soft delete for conversation ID {conversation_id} (expected v{expected_version}) affected 0 rows."
                    raise ConflictError(msg, entity="conversations", entity_id=conversation_id)

                logger.info(
                    f"Soft-deleted conversation ID {conversation_id} (was v{expected_version}), new version {next_version_val}.")
                return True
        except ConflictError:
            raise
        except CharactersRAGDBError as e:
            logger.error(
                f"Database error soft-deleting conversation ID {conversation_id} (expected v{expected_version}): {e}",
                exc_info=True)
            raise

    def search_conversations_by_title(
        self,
        title_query: str,
        character_id: Optional[int] = None,
        limit: int = 10,
        offset: int = 0,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches conversations by title using FTS.

        Matches against the 'title' field in `conversations_fts`.
        Optionally filters by `character_id`. Returns non-deleted conversations,
        ordered by relevance (rank).

        Args:
            title_query: The search term for the title. Supports FTS query syntax.
            character_id: Optional character ID to filter results.
            limit: Maximum number of results. Defaults to 10.
            client_id: Optional override for client scoping. Defaults to the
                database instance's `client_id`. Pass `None` to search across all
                clients (reserved for privileged workflows).

        Returns:
            A list of matching conversation dictionaries. Can be empty.

        Raises:
            CharactersRAGDBError: For database search errors.
        """
        if not title_query.strip():
            logger.warning("Empty title_query provided for conversation search. Returning empty list.")
            return []

        client_filter = self.client_id if client_id is None else client_id

        if self.backend_type == BackendType.POSTGRESQL:
            tsquery = FTSQueryTranslator.normalize_query(title_query, 'postgresql')
            if not tsquery:
                logger.debug("Conversation title query normalized to empty tsquery for input '%s'", title_query)
                return []

            base_query = """
                SELECT c.*, ts_rank(c.conversations_fts_tsv, to_tsquery('english', ?)) AS bm25_raw
                FROM conversations c
                WHERE c.deleted = FALSE
                  AND c.conversations_fts_tsv @@ to_tsquery('english', ?)
            """
            params_list: List[Any] = [tsquery, tsquery]
            filters: List[str] = []
            if character_id is not None:
                filters.append("c.character_id = ?")
                params_list.append(character_id)
            if client_filter is not None:
                filters.append("c.client_id = ?")
                params_list.append(client_filter)
            if filters:
                base_query += " AND " + " AND ".join(filters)

            try:
                cursor = self.execute_query(base_query, tuple(params_list))
                rows = [dict(row) for row in cursor.fetchall()]
            except CharactersRAGDBError as exc:
                logger.error("PostgreSQL FTS search failed for conversations term '%s': %s", title_query, exc)
                raise

            if not rows:
                return []
            max_score = max([row.get("bm25_raw", 0) or 0 for row in rows]) or 0
            for row in rows:
                raw = row.get("bm25_raw", 0) or 0
                row["bm25_norm"] = (raw / max_score) if max_score else 0
            rows.sort(
                key=lambda r: (
                    -(r.get("bm25_norm") or 0),
                    str(r.get("last_modified") or ""),
                    r.get("id") or "",
                ),
                reverse=False,
            )
            return rows[offset: offset + limit]

        safe_search_term = f'"{title_query}"'
        filters: List[str] = ["conversations_fts MATCH ?", "c.deleted = 0"]
        params_filters: List[Any] = [title_query]
        if character_id is not None:
            filters.append("c.character_id = ?")
            params_filters.append(character_id)
        if client_filter is not None:
            filters.append("c.client_id = ?")
            params_filters.append(client_filter)

        where_clause = " AND ".join(filters)

        select_query = f"""
            SELECT c.*, bm25(conversations_fts) AS bm25_raw
            FROM conversations_fts
            JOIN conversations c ON conversations_fts.rowid = c.rowid
            WHERE {where_clause}
        """

        try:
            cursor = self.execute_query(select_query, tuple(params_filters))
            rows = [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError as e:
            logger.error(f"Error searching conversations for title '{safe_search_term}': {e}")
            raise

        if not rows:
            return []
        max_bm25 = max([-1 * (row.get("bm25_raw", 0) or 0) for row in rows]) or 0
        for row in rows:
            raw = -1 * (row.get("bm25_raw", 0) or 0)
            row["bm25_norm"] = (raw / max_bm25) if max_bm25 else 0

        rows.sort(
            key=lambda r: (
                -(r.get("bm25_norm") or 0),
                str(r.get("last_modified") or ""),
                r.get("id") or "",
            ),
            reverse=False,
        )
        return rows[offset: offset + limit]

    def search_conversations(
        self,
        query: Optional[str],
        *,
        client_id: Optional[str] = None,
        character_id: Optional[int] = None,
        state: Optional[str] = None,
        topic_label: Optional[str] = None,
        topic_prefix: bool = False,
        cluster_id: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        date_field: str = "last_modified",
    ) -> List[Dict[str, Any]]:
        """
        Search/filter conversations with optional FTS query and metadata filters.

        Returns conversation rows including `bm25_raw` when query is provided.
        """
        client_filter = self.client_id if client_id is None else client_id
        safe_query = (query or "").strip()
        if safe_query == "":
            safe_query = None

        if date_field not in {"last_modified", "created_at"}:
            raise InputError("date_field must be 'last_modified' or 'created_at'")

        filters: List[str] = []
        params: List[Any] = []
        keyword_table = self._map_table_for_backend("keywords")

        if self.backend_type == BackendType.POSTGRESQL:
            date_expr = "c.created_at" if date_field == "created_at" else "COALESCE(c.last_modified, c.created_at)"
            base_query = "SELECT c.*, 0.0 AS bm25_raw FROM conversations c WHERE c.deleted = FALSE"
            if safe_query:
                tsquery = FTSQueryTranslator.normalize_query(safe_query, 'postgresql')
                if not tsquery:
                    return []
                base_query = (
                    "SELECT c.*, ts_rank(c.conversations_fts_tsv, to_tsquery('english', ?)) AS bm25_raw "
                    "FROM conversations c "
                    "WHERE c.deleted = FALSE AND c.conversations_fts_tsv @@ to_tsquery('english', ?)"
                )
                params.extend([tsquery, tsquery])

            if character_id is not None:
                filters.append("c.character_id = ?")
                params.append(character_id)
            if client_filter is not None:
                filters.append("c.client_id = ?")
                params.append(client_filter)
            if state is not None:
                filters.append("c.state = ?")
                params.append(self._normalize_conversation_state(state))
            if topic_label:
                label = topic_label.rstrip("*")
                if label:
                    if topic_prefix:
                        filters.append("LOWER(c.topic_label) LIKE ?")
                        params.append(f"{label.lower()}%")
                    else:
                        filters.append("LOWER(c.topic_label) = ?")
                        params.append(label.lower())
            if cluster_id:
                filters.append("c.cluster_id = ?")
                params.append(cluster_id)
            if start_date:
                filters.append(f"{date_expr} >= ?")
                params.append(start_date)
            if end_date:
                filters.append(f"{date_expr} <= ?")
                params.append(end_date)
            if keywords:
                for kw in keywords:
                    filters.append(
                        f"EXISTS (SELECT 1 FROM conversation_keywords ck "
                        f"JOIN {keyword_table} k ON k.id = ck.keyword_id "
                        f"WHERE ck.conversation_id = c.id AND k.deleted = FALSE AND LOWER(k.keyword) = ?)"
                    )
                    params.append(kw.lower())

            if filters:
                base_query += " AND " + " AND ".join(filters)

            try:
                cursor = self.execute_query(base_query, tuple(params))
                return [dict(row) for row in cursor.fetchall()]
            except CharactersRAGDBError as exc:
                logger.error("PostgreSQL conversation search failed: %s", exc)
                raise

        date_expr = "c.created_at" if date_field == "created_at" else "COALESCE(NULLIF(c.last_modified,''), c.created_at)"

        if safe_query:
            filters.append("conversations_fts MATCH ?")
            params.append(safe_query)
            base_query = (
                "SELECT c.*, (bm25(conversations_fts) * -1) AS bm25_raw "
                "FROM conversations_fts JOIN conversations c ON conversations_fts.rowid = c.rowid "
                "WHERE c.deleted = 0"
            )
        else:
            base_query = "SELECT c.*, 0.0 AS bm25_raw FROM conversations c WHERE c.deleted = 0"

        if character_id is not None:
            filters.append("c.character_id = ?")
            params.append(character_id)
        if client_filter is not None:
            filters.append("c.client_id = ?")
            params.append(client_filter)
        if state is not None:
            filters.append("c.state = ?")
            params.append(self._normalize_conversation_state(state))
        if topic_label:
            label = topic_label.rstrip("*")
            if label:
                if topic_prefix:
                    filters.append("LOWER(c.topic_label) LIKE ?")
                    params.append(f"{label.lower()}%")
                else:
                    filters.append("LOWER(c.topic_label) = ?")
                    params.append(label.lower())
        if cluster_id:
            filters.append("c.cluster_id = ?")
            params.append(cluster_id)
        if start_date:
            filters.append(f"{date_expr} >= ?")
            params.append(start_date)
        if end_date:
            filters.append(f"{date_expr} <= ?")
            params.append(end_date)
        if keywords:
            for kw in keywords:
                filters.append(
                    "EXISTS (SELECT 1 FROM conversation_keywords ck "
                    f"JOIN {keyword_table} k ON k.id = ck.keyword_id "
                    "WHERE ck.conversation_id = c.id AND k.deleted = 0 AND LOWER(k.keyword) = ?)"
                )
                params.append(kw.lower())

        if filters:
            base_query += " AND " + " AND ".join(filters)

        try:
            cursor = self.execute_query(base_query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError as e:
            logger.error(f"Error searching conversations: {e}")
            raise

    # --- Message Methods ---
    def add_message(self, msg_data: Dict[str, Any]) -> Optional[str]:
        """
        Adds a new message to a conversation, optionally with image data.

        `id` (UUID string) is auto-generated if not provided in `msg_data`.
        Requires 'conversation_id', 'sender'. Message must have 'content' (text) or image attachments.
        `client_id` defaults to DB instance's `client_id`. `version` is set to 1.
        `timestamp` defaults to current UTC time if not provided; `last_modified` is set to current UTC time.

        Verifies that the parent conversation (given by `conversation_id`) exists and is not deleted.
        FTS updates (`messages_fts` for content) and `sync_log` entries are handled by SQL triggers.

        Args:
            msg_data: Dictionary with message data.
                      Required: 'conversation_id', 'sender'. At least one of 'content' or images.
                      Optional: 'id', 'parent_message_id', 'content' (str),
                                'image_data' (bytes), 'image_mime_type' (str, required if image_data present),
                                'images' (iterable of {'data','mime'}), 'timestamp', 'ranking', 'client_id'.

        Returns:
            The string UUID of the newly added message.

        Raises:
            InputError: If required fields are missing, if both 'content' and attachments are absent,
                        or if the parent conversation is not found or is deleted.
            ConflictError: If a message with the provided 'id' (if any) already exists.
            CharactersRAGDBError: For other database errors (e.g., FK violation for conversation_id).
        """
        images_payload_raw = msg_data.pop('images', None)
        normalized_images: List[Tuple[bytes, str]] = []
        if images_payload_raw:
            for entry in images_payload_raw:
                img_bytes: Optional[bytes] = None
                img_mime: Optional[str] = None
                if isinstance(entry, dict):
                    img_bytes = entry.get("data") or entry.get("image_data")
                    img_mime = entry.get("mime") or entry.get("image_mime_type")
                elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    img_bytes, img_mime = entry[0], entry[1]
                if img_bytes is None or img_mime is None:
                    continue
                if isinstance(img_bytes, memoryview):
                    img_bytes = img_bytes.tobytes()
                normalized_images.append((img_bytes, str(img_mime)))

        # Enforce maximum image sizes (single and multi-image) using settings override
        try:
            _max_img_bytes = int(settings.get("MAX_MESSAGE_IMAGE_BYTES", 5 * 1024 * 1024))
        except Exception:
            _max_img_bytes = 5 * 1024 * 1024  # 5MB default

        # Validate primary image size if present
        primary_img = msg_data.get('image_data')
        if isinstance(primary_img, memoryview):
            primary_img = primary_img.tobytes()
        if isinstance(primary_img, (bytes, bytearray)):
            if len(primary_img) > _max_img_bytes:
                raise InputError(
                    f"Primary image attachment exceeds maximum size of {_max_img_bytes} bytes"
                )

        # Validate any additional images provided via 'images'
        if normalized_images:
            for b, _m in normalized_images:
                if b is None:
                    continue
                if isinstance(b, memoryview):
                    b = b.tobytes()
                if isinstance(b, (bytes, bytearray)) and len(b) > _max_img_bytes:
                    raise InputError(
                        f"Message image attachment exceeds maximum size of {_max_img_bytes} bytes"
                    )

        msg_id = msg_data.get('id') or self._generate_uuid()

        required_fields = ['conversation_id', 'sender', 'content']
        for field in required_fields:
            if field not in msg_data:
                raise InputError(f"Required field '{field}' is missing for message.")
        if not msg_data.get('content') and not msg_data.get('image_data') and not normalized_images:
            raise InputError("Message must have text content or image data.")
        if msg_data.get('image_data') and not msg_data.get('image_mime_type'):
            raise InputError("image_mime_type is required if image_data is provided.")

        if normalized_images and not msg_data.get('image_data'):
            first_bytes, first_mime = normalized_images[0]
            msg_data['image_data'] = first_bytes
            msg_data['image_mime_type'] = first_mime

        client_id = msg_data.get('client_id') or self.client_id
        if not client_id:
            raise InputError("Client ID is required for message.")

        now = self._get_current_utc_timestamp_iso()
        timestamp = msg_data.get('timestamp') or now

        query = """
                INSERT INTO messages (id, conversation_id, parent_message_id, sender, content,
                                      image_data, image_mime_type,
                                      timestamp, ranking, last_modified, client_id, version, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
        if self.backend_type == BackendType.POSTGRESQL:
            params = (
                msg_id, msg_data['conversation_id'], msg_data.get('parent_message_id'),
                msg_data['sender'], msg_data.get('content', ''),
                msg_data.get('image_data'), msg_data.get('image_mime_type'),
                timestamp, msg_data.get('ranking'), now, client_id, 1, False
            )
        else:
            params = (
                msg_id, msg_data['conversation_id'], msg_data.get('parent_message_id'),
                msg_data['sender'], msg_data.get('content', ''),
                msg_data.get('image_data'), msg_data.get('image_mime_type'),
                timestamp, msg_data.get('ranking'), now, client_id, 1, 0
            )
        try:
            with self.transaction():
                conv_cursor = self.execute_query(
                    "SELECT 1 FROM conversations WHERE id = ? AND deleted = 0",
                    (msg_data['conversation_id'],),
                )
                if not conv_cursor.fetchone():
                    raise InputError(
                        f"Cannot add message: Conversation ID '{msg_data['conversation_id']}' not found or deleted."
                    )
                self.execute_query(query, params)
                if normalized_images:
                    self._insert_message_images(msg_id, normalized_images)
            logger.info(
                "Added message ID: %s to conversation %s (Images stored: %s).",
                msg_id,
                msg_data['conversation_id'],
                len(normalized_images) if normalized_images else ("Yes" if msg_data.get('image_data') else "No"),
            )
            return msg_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: messages.id" in str(e):
                raise ConflictError(
                    f"Message with ID '{msg_id}' already exists.",
                    entity="messages",
                    entity_id=msg_id,
                ) from e
            raise CharactersRAGDBError(f"Database integrity error adding message: {e}") from e
        except InputError:
            raise
        except CharactersRAGDBError as e:
            logger.error(f"Database error adding message: {e}")
            raise
    def _insert_message_images(self, message_id: str, images: List[Tuple[bytes, str]]) -> None:
        """Insert or replace message images for the given message."""
        if not images:
            return
        params: List[Tuple[str, int, bytes, str]] = []
        for idx, (img_bytes, img_mime) in enumerate(images):
            if img_bytes is None or img_mime is None:
                continue
            if isinstance(img_bytes, memoryview):
                img_bytes = img_bytes.tobytes()
            params.append((message_id, idx, img_bytes, img_mime))
        if not params:
            return
        query = (
            "INSERT INTO message_images (message_id, position, image_data, image_mime_type) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(message_id, position) DO UPDATE SET "
            "image_data=excluded.image_data, image_mime_type=excluded.image_mime_type, "
            "created_at=CURRENT_TIMESTAMP"
        )
        self.execute_many(query, params, commit=False)

    def get_message_images(self, message_id: str) -> List[Dict[str, Any]]:
        """Fetch all images associated with a message, ordered by position."""
        try:
            cursor = self.execute_query(
                "SELECT message_id, position, image_data, image_mime_type FROM message_images "
                "WHERE message_id = ? ORDER BY position ASC",
                (message_id,),
            )
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description] if cursor.description else []
            images: List[Dict[str, Any]] = []
            for row in rows:
                if isinstance(row, dict):
                    record = dict(row)
                else:
                    record = {columns[idx]: row[idx] for idx in range(len(columns))}
                img_bytes = record.get("image_data")
                if isinstance(img_bytes, memoryview):
                    record["image_data"] = img_bytes.tobytes()
                images.append(record)
            return images
        except CharactersRAGDBError as e:
            logger.error(f"Failed to fetch images for message {message_id}: {e}")
            return []

    def get_message_conversation_id(self, message_id: str) -> Optional[str]:
        """Return the conversation_id for a message if it exists and is not deleted."""
        query = "SELECT conversation_id FROM messages WHERE id = ? AND deleted = 0"
        try:
            cursor = self.execute_query(query, (message_id,))
            row = cursor.fetchone()
            if not row:
                return None
            if isinstance(row, dict):
                return row.get("conversation_id")
            return row[0] if row else None
        except CharactersRAGDBError as e:
            logger.error(f"Database error fetching conversation_id for message {message_id}: {e}")
            raise

    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific message by its UUID.

        Only non-deleted messages are returned. Includes all fields, such as
        `image_data` (BLOB) and `image_mime_type` if present.

        Args:
            message_id: The string UUID of the message.

        Returns:
            A dictionary with message data if found and not deleted, else None.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        query = "SELECT id, conversation_id, parent_message_id, sender, content, image_data, image_mime_type, timestamp, ranking, last_modified, version, client_id, deleted FROM messages WHERE id = ? AND deleted = 0"
        try:
            cursor = self.execute_query(query, (message_id,))
            row = cursor.fetchone()
            if not row:
                return None
            if isinstance(row, dict):
                record = dict(row)
            else:
                columns = [col[0] for col in cursor.description] if cursor.description else []
                record = {columns[idx]: row[idx] for idx in range(len(columns))}
            img_blob = record.get("image_data")
            if isinstance(img_blob, memoryview):
                record["image_data"] = img_blob.tobytes()
            record["images"] = self.get_message_images(message_id)
            return record
        except CharactersRAGDBError as e:
            logger.error(f"Database error fetching message ID {message_id}: {e}")
            raise

    def get_messages_for_conversation(self, conversation_id: str, limit: int = 100, offset: int = 0,
                                      order_by_timestamp: str = "ASC", include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        Lists messages for a specific conversation.
        Returns non-deleted messages, ordered by `timestamp` according to `order_by_timestamp`.
        Crucially, it also ensures the parent conversation is not soft-deleted.
        """
        if order_by_timestamp.upper() not in ["ASC", "DESC"]:
            raise InputError("order_by_timestamp must be 'ASC' or 'DESC'.")

        # The new query joins with conversations to check its 'deleted' status.
        if include_deleted:
            delete_clause = ""
        else:
            delete_clause = "AND m.deleted = 0"

        query = f"""
            SELECT m.id, m.conversation_id, m.parent_message_id, m.sender, m.content,
                   m.image_data, m.image_mime_type, m.timestamp, m.ranking,
                   m.last_modified, m.version, m.client_id, m.deleted
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.conversation_id = ?
              {delete_clause}
              AND c.deleted = 0
            ORDER BY m.timestamp {order_by_timestamp}
            LIMIT ? OFFSET ?
        """
        try:
            cursor = self.execute_query(query, (conversation_id, limit, offset))
            raw_rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description] if cursor.description else []
            results: List[Dict[str, Any]] = []
            for row in raw_rows:
                if isinstance(row, dict):
                    record = dict(row)
                else:
                    record = {columns[idx]: row[idx] for idx in range(len(columns))}
                image_blob = record.get("image_data")
                if isinstance(image_blob, memoryview):
                    record["image_data"] = image_blob.tobytes()
                record["images"] = self.get_message_images(record["id"])
                results.append(record)
            return results
        except CharactersRAGDBError as e:
            logger.error(f"Database error fetching messages for conversation ID {conversation_id}: {e}")
            raise

    def count_root_messages_for_conversation(self, conversation_id: str) -> int:
        """Count root (parentless) messages for a conversation."""
        query = (
            "SELECT COUNT(1) FROM messages m "
            "JOIN conversations c ON m.conversation_id = c.id "
            "WHERE m.conversation_id = ? AND m.parent_message_id IS NULL "
            "AND m.deleted = 0 AND c.deleted = 0"
        )
        try:
            cursor = self.execute_query(query, (conversation_id,))
            row = cursor.fetchone()
            if row is None:
                return 0
            try:
                return int(row[0])
            except Exception:
                return int(row.get("COUNT(1)") or row.get("count") or 0)
        except CharactersRAGDBError as e:
            logger.error("Database error counting root messages for conversation %s: %s", conversation_id, e)
            raise

    def get_root_messages_for_conversation(
        self,
        conversation_id: str,
        *,
        limit: int,
        offset: int,
        order_by_timestamp: str = "ASC",
    ) -> List[Dict[str, Any]]:
        """Fetch root (parentless) messages with minimal columns for tree building."""
        if order_by_timestamp.upper() not in ["ASC", "DESC"]:
            raise InputError("order_by_timestamp must be 'ASC' or 'DESC'.")
        query = f"""
            SELECT m.id, m.parent_message_id, m.sender, m.content, m.timestamp
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.conversation_id = ?
              AND m.parent_message_id IS NULL
              AND m.deleted = 0
              AND c.deleted = 0
            ORDER BY m.timestamp {order_by_timestamp}
            LIMIT ? OFFSET ?
        """
        try:
            cursor = self.execute_query(query, (conversation_id, limit, offset))
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description] if cursor.description else []
            results: List[Dict[str, Any]] = []
            for row in rows:
                if isinstance(row, dict):
                    record = dict(row)
                else:
                    record = {columns[idx]: row[idx] for idx in range(len(columns))}
                results.append(record)
            return results
        except CharactersRAGDBError as e:
            logger.error("Database error fetching root messages for conversation %s: %s", conversation_id, e)
            raise

    def get_messages_for_conversation_by_parent_ids(
        self,
        conversation_id: str,
        parent_ids: List[str],
        *,
        order_by_timestamp: str = "ASC",
    ) -> List[Dict[str, Any]]:
        """Fetch child messages for the given parent IDs with minimal columns."""
        if not parent_ids:
            return []
        if order_by_timestamp.upper() not in ["ASC", "DESC"]:
            raise InputError("order_by_timestamp must be 'ASC' or 'DESC'.")
        placeholders = ",".join(["?"] * len(parent_ids))
        query = f"""
            SELECT m.id, m.parent_message_id, m.sender, m.content, m.timestamp
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.conversation_id = ?
              AND m.parent_message_id IN ({placeholders})
              AND m.deleted = 0
              AND c.deleted = 0
            ORDER BY m.timestamp {order_by_timestamp}
        """
        params = [conversation_id, *parent_ids]
        try:
            cursor = self.execute_query(query, tuple(params))
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description] if cursor.description else []
            results: List[Dict[str, Any]] = []
            for row in rows:
                if isinstance(row, dict):
                    record = dict(row)
                else:
                    record = {columns[idx]: row[idx] for idx in range(len(columns))}
                results.append(record)
            return results
        except CharactersRAGDBError as e:
            logger.error(
                "Database error fetching child messages for conversation %s: %s",
                conversation_id,
                e,
            )
            raise

    def has_system_message_for_conversation(
        self,
        conversation_id: str,
        include_deleted: bool = False,
    ) -> bool:
        """Check whether a conversation has at least one system message."""
        if include_deleted:
            query = """
                SELECT 1
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE m.conversation_id = ?
                  AND lower(m.sender) = 'system'
                  AND c.deleted = ?
                LIMIT 1
            """
            params = (conversation_id, False)
        else:
            query = """
                SELECT 1
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE m.conversation_id = ?
                  AND lower(m.sender) = 'system'
                  AND m.deleted = ?
                  AND c.deleted = ?
                LIMIT 1
            """
            params = (conversation_id, False, False)
        try:
            cursor = self.execute_query(query, params)
            return cursor.fetchone() is not None
        except CharactersRAGDBError as e:
            logger.error(
                "Database error checking system messages for conversation ID %s: %s",
                conversation_id,
                e,
            )
            raise

    def update_message(self, message_id: str, update_data: Dict[str, Any], expected_version: int) -> bool | None:
        """
        Updates an existing message using optimistic locking.

        Succeeds if `expected_version` matches the current database version.
        `version` is incremented, `last_modified` updated, and `client_id` set.
        Updatable fields from `update_data`: 'content', 'ranking', 'parent_message_id'.
        Image data can also be updated: 'image_data' and 'image_mime_type'.
        If 'image_data' is set to `None` in `update_data`, both 'image_data' and
        'image_mime_type' columns will be set to NULL in the database.
        Other fields in `update_data` are ignored. `update_data` must not be empty.

        FTS updates (`messages_fts` for content changes) and `sync_log` entries
        are handled by SQL triggers.

        Args:
            message_id: The UUID of the message to update.
            update_data: Dictionary with fields to update. Must not be empty.
                         If 'image_data' is updated, 'image_mime_type' should also be
                         provided, unless 'image_data' is set to None.
            expected_version: The client's expected version of the record.

        Returns:
            True if the update was successful.

        Raises:
            InputError: If `update_data` is empty.
            ConflictError: If the message is not found, is soft-deleted, or if `expected_version`
                           does not match the current database version.
            CharactersRAGDBError: For database integrity errors (e.g., invalid `parent_message_id`)
                                  or other database issues.
        """
        if not update_data:
            raise InputError("No data provided for message update.")

        now = self._get_current_utc_timestamp_iso()
        fields_to_update_sql = []
        params_for_set_clause = []

        allowed_to_update = ['content', 'ranking', 'parent_message_id', 'image_data', 'image_mime_type']

        # Special handling for clearing image
        if 'image_data' in update_data and update_data['image_data'] is None:
            fields_to_update_sql.append("image_data = NULL")
            fields_to_update_sql.append("image_mime_type = NULL")
            # Remove these keys from update_data to avoid processing them again
            # in the loop if they were explicitly set to None
            # This isn't strictly necessary with current loop logic but good for clarity
            update_data.pop('image_data', None)
            update_data.pop('image_mime_type', None)

        for key, value in update_data.items():
            if key in allowed_to_update:
                fields_to_update_sql.append(f"{key} = ?")
                params_for_set_clause.append(value)
            elif key not in ['id', 'conversation_id', 'sender', 'timestamp', 'last_modified', 'version', 'client_id', 'deleted']:
                logger.warning(
                    f"Attempted to update immutable or unknown field '{key}' in message ID {message_id}, skipping.")

        if not fields_to_update_sql: # If only image was cleared, this list might be empty now if no other fields
            logger.info(f"No updatable content fields provided for message ID {message_id}, but metadata will be updated if version matches.")
            # Proceed to metadata update; SQL query will be constructed accordingly

        next_version_val = expected_version + 1

        current_fields_to_update_sql = list(fields_to_update_sql)
        current_params_for_set_clause = list(params_for_set_clause)

        current_fields_to_update_sql.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        current_params_for_set_clause.extend([now, next_version_val, self.client_id])

        where_values = [message_id, expected_version]
        final_params_for_execute = tuple(current_params_for_set_clause + where_values)

        query = f"UPDATE messages SET {', '.join(current_fields_to_update_sql)} WHERE id = ? AND version = ? AND deleted = 0"

        try:
            with self.transaction() as conn:
                current_db_version = self._get_current_db_version(conn, "messages", "id", message_id)

                if current_db_version != expected_version:
                    raise ConflictError(
                        f"Message ID {message_id} update failed: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity="messages", entity_id=message_id
                    )

                cursor = conn.execute(query, final_params_for_execute)

                if cursor.rowcount == 0:
                    check_again_cursor = conn.execute("SELECT version, deleted FROM messages WHERE id = ?",
                                                      (message_id,))
                    final_state = check_again_cursor.fetchone()
                    msg = f"Update for message ID {message_id} (expected v{expected_version}) affected 0 rows."
                    if not final_state:
                        msg = f"Message ID {message_id} disappeared."
                    elif final_state['deleted']:
                        msg = f"Message ID {message_id} was soft-deleted concurrently."
                    elif final_state['version'] != expected_version:
                        msg = f"Message ID {message_id} version changed to {final_state['version']} concurrently."
                    raise ConflictError(msg, entity="messages", entity_id=message_id)

                logger.info(
                    f"Updated message ID {message_id} from version {expected_version} to version {next_version_val}. Fields updated: {fields_to_update_sql if fields_to_update_sql else 'None'}")
                return True
        except sqlite3.IntegrityError as e:
            logger.error(f"SQLite integrity error updating message ID {message_id} (expected v{expected_version}): {e}",
                         exc_info=True)
            raise CharactersRAGDBError(f"Database integrity error updating message: {e}") from e
        except ConflictError:
            raise
        except InputError: # Should not be raised from here directly, but for completeness
            raise
        except CharactersRAGDBError as e:
            logger.error(f"Database error updating message ID {message_id} (expected v{expected_version}): {e}",
                         exc_info=True)
            raise

    def soft_delete_message(self, message_id: str, expected_version: int) -> bool | None:
        """
        Soft-deletes a message using optimistic locking.

        Sets `deleted` to 1, updates `last_modified`, increments `version`, and sets `client_id`.
        Succeeds if `expected_version` matches the current DB version and the record is active.
        If already soft-deleted, returns True (idempotent).

        FTS updates (removal from `messages_fts`) and `sync_log` entries are handled by SQL triggers.

        Args:
            message_id: The UUID of the message to soft-delete.
            expected_version: The client's expected version of the record.

        Returns:
            True if the soft-delete was successful or if the message was already soft-deleted.

        Raises:
            ConflictError: If not found (and not already deleted), or if active with a version mismatch.
            CharactersRAGDBError: For other database errors.
        """
        now = self._get_current_utc_timestamp_iso()
        next_version_val = expected_version + 1

        query = "UPDATE messages SET deleted = 1, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ? AND deleted = 0"
        params = (now, next_version_val, self.client_id, message_id, expected_version)

        try:
            with self.transaction() as conn:
                try:
                    current_db_version = self._get_current_db_version(conn, "messages", "id", message_id)
                except ConflictError as e:
                    check_status_cursor = conn.execute("SELECT deleted, version FROM messages WHERE id = ?",
                                                       (message_id,))
                    record_status = check_status_cursor.fetchone()
                    if record_status and record_status['deleted']:
                        logger.info(f"Message ID {message_id} already soft-deleted. Success (idempotent).")
                        return True
                    raise e # Re-raise if not found or other conflict

                if current_db_version != expected_version:
                    raise ConflictError(
                        f"Soft delete for Message ID {message_id} failed: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity="messages", entity_id=message_id
                    )

                cursor = conn.execute(query, params)

                if cursor.rowcount == 0:
                    check_again_cursor = conn.execute("SELECT version, deleted FROM messages WHERE id = ?",
                                                      (message_id,))
                    final_state = check_again_cursor.fetchone()
                    msg = f"Soft delete for message ID {message_id} (expected v{expected_version}) affected 0 rows."
                    if not final_state:
                        msg = f"Message ID {message_id} disappeared."
                    elif final_state['deleted']:
                        logger.info(f"Message ID {message_id} was soft-deleted concurrently. Success.")
                        return True
                    elif final_state['version'] != expected_version:
                        msg = f"Message ID {message_id} version changed to {final_state['version']} concurrently."
                    else:
                        msg = f"Soft delete for message ID {message_id} (expected v{expected_version}) affected 0 rows."
                    raise ConflictError(msg, entity="messages", entity_id=message_id)

                logger.info(
                    f"Soft-deleted message ID {message_id} (was v{expected_version}), new version {next_version_val}.")
                return True
        except ConflictError:
            raise
        except CharactersRAGDBError as e:
            logger.error(f"Database error soft-deleting message ID {message_id} (expected v{expected_version}): {e}",
                         exc_info=True)
            raise

    def search_messages_by_content(self, content_query: str, conversation_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Searches messages by content using FTS.

        Matches against the 'content' field in `messages_fts`.
        Optionally filters by `conversation_id`. Returns non-deleted messages,
        ordered by relevance (rank).

        Args:
            content_query: The search term for content. Supports FTS query syntax.
            conversation_id: Optional conversation UUID to filter results.
            limit: Maximum number of results. Defaults to 10.

        Returns:
            A list of matching message dictionaries. Can be empty.

        Raises:
            CharactersRAGDBError: For database search errors.
        """
        if self.backend_type == BackendType.POSTGRESQL:
            tsquery = FTSQueryTranslator.normalize_query(content_query, 'postgresql')
            if not tsquery:
                logger.debug("Message content query normalized to empty tsquery for input '%s'", content_query)
                return []

            base_query = [
                "SELECT m.*, ts_rank(m.messages_fts_tsv, to_tsquery('english', ?)) AS rank",
                "FROM messages m",
                "WHERE m.deleted = FALSE",
                "AND m.messages_fts_tsv @@ to_tsquery('english', ?)",
            ]
            params_list: List[Any] = [tsquery, tsquery]

            if conversation_id:
                base_query.append("AND m.conversation_id = ?")
                params_list.append(conversation_id)

            base_query.append("ORDER BY rank DESC, m.last_modified DESC")
            base_query.append("LIMIT ?")
            params_list.append(limit)

            try:
                cursor = self.execute_query("\n".join(base_query), tuple(params_list))
                return [dict(row) for row in cursor.fetchall()]
            except CharactersRAGDBError as exc:
                logger.error("PostgreSQL FTS search failed for messages term '%s': %s", content_query, exc)
                raise

        safe_search_term = f'"{content_query}"'
        base_query = """
                     SELECT m.*
                     FROM messages_fts, messages m
                     WHERE messages_fts.rowid = m.rowid \
                       AND messages_fts MATCH ? \
                       AND m.deleted = 0 \
                     """
        params_list = [content_query]
        if conversation_id:
            base_query += " AND m.conversation_id = ?"
            params_list.append(conversation_id)

        base_query += " ORDER BY bm25(messages_fts) ASC, m.last_modified DESC LIMIT ?"
        params_list.append(limit)

        try:
            cursor = self.execute_query(base_query, tuple(params_list))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError as e:
            logger.error(f"Error searching messages for content '{safe_search_term}': {e}")
            raise

    # --- Keyword, KeywordCollection, Note Methods (CRUD + Search) ---
    # These follow similar patterns to CharacterCard, Conversation, Message methods:
    # - add: INSERT with default version 1, set last_modified, client_id.
    # - get_by_id/name: SELECT WHERE deleted = 0.
    # - list: SELECT WHERE deleted = 0.
    # - update: UPDATE SET fields, last_modified, version, client_id WHERE id/name = ? AND version = ? AND deleted = 0.
    # - soft_delete: UPDATE SET deleted = 1, last_modified, version, client_id WHERE id/name = ? AND version = ? AND deleted = 0.
    # - search: Use respective FTS table.

    def _add_generic_item(self, table_name: str, unique_col_name: str, item_data: Dict[str, Any], main_col_value: str,
                          other_fields_map: Dict[str, str]) -> Optional[int]:
        """
        Internal helper to add items to tables with an auto-increment ID and a unique text column.

        Handles creation or undeletion if an item with the `main_col_value` exists
        but is soft-deleted. `version` is set to 1 on new creation or incremented on undelete.
        `last_modified` and `client_id` (from `item_data` or instance) are set.
        `created_at` is set on new creation or remains from original on undelete (implicitly).

        FTS and sync_log entries are expected to be handled by SQL triggers for these tables.

        Args:
            table_name: Name of the database table (e.g., "keywords").
            unique_col_name: Name of the column that must be unique (e.g., "keyword").
                             This column usually has `COLLATE NOCASE` in schema.
            item_data: Dictionary possibly containing 'client_id' or other values
                       mapped by `other_fields_map`.
            main_col_value: The value for the `unique_col_name` (e.g., the keyword text).
                            This value is typically stripped of whitespace before use.
            other_fields_map: A map of DB column names to keys in `item_data` for additional fields.
                              Example: {"parent_id_db_col": "parent_id_item_data_key"}.

        Returns:
            The integer ID of the added or undeleted item.

        Raises:
            ConflictError: If an active item with `main_col_value` already exists,
                           or if undelete fails due to version mismatch or concurrent activation.
            CharactersRAGDBError: For other database errors.
        """
        now = self._get_current_utc_timestamp_iso()
        client_id_to_use = item_data.get('client_id', self.client_id)

        other_cols = list(other_fields_map.keys())
        other_placeholders_list = ['?'] * len(other_cols)
        other_values = [item_data.get(other_fields_map[col_db]) for col_db in other_cols]

        cols_str_list = [unique_col_name]
        placeholders_str_list = ["?"]
        if other_cols:
            cols_str_list.extend(other_cols)
            placeholders_str_list.extend(other_placeholders_list)

        # Add created_at for new inserts
        cols_str_list_insert = cols_str_list + ['created_at', 'last_modified', 'client_id', 'version', 'deleted']
        if self.backend_type == BackendType.POSTGRESQL:
            placeholders_str_list_insert = placeholders_str_list + ['?', '?', '?', '?', '?']
            version_value = 1
            deleted_value = False
        else:
            placeholders_str_list_insert = placeholders_str_list + ['?', '?', '?', '1', '0']
            version_value = 1
            deleted_value = 0

        table_name = self._map_table_for_backend(table_name)
        query = f"""
            INSERT INTO {table_name} (
                {', '.join(cols_str_list_insert)}
            ) VALUES ({', '.join(placeholders_str_list_insert)})
        """
        # Params for INSERT: main_value, other_values..., created_at, last_modified, client_id
        if self.backend_type == BackendType.POSTGRESQL:
            params_tuple_insert = tuple([main_col_value] + other_values + [now, now, client_id_to_use, version_value, deleted_value])
        else:
            params_tuple_insert = tuple([main_col_value] + other_values + [now, now, client_id_to_use])


        try:
            with self.transaction() as conn:
                # Check if a soft-deleted item exists and undelete it
                undelete_cursor = conn.execute(
                    f"SELECT id, version FROM {table_name} WHERE {unique_col_name} = ? AND deleted = 1",
                    (main_col_value,))
                existing_deleted = undelete_cursor.fetchone()
                if existing_deleted:
                    item_id, current_version = existing_deleted['id'], existing_deleted['version']
                    next_version = current_version + 1

                    update_set_parts = [f"{unique_col_name} = ?"]
                    update_params_list = [main_col_value]
                    for i, col_db in enumerate(other_cols):
                        update_set_parts.append(f"{col_db} = ?")
                        update_params_list.append(other_values[i])
                    update_set_parts.extend(["deleted = 0", "last_modified = ?", "version = ?", "client_id = ?"])
                    # WHERE clause params for undelete
                    undelete_where_params = [item_id, current_version]
                    full_undelete_params = tuple(update_params_list + [now, next_version, client_id_to_use] + undelete_where_params)

                    undelete_query = f"UPDATE {table_name} SET {', '.join(update_set_parts)} WHERE id = ? AND version = ?"

                    row_count_undelete = conn.execute(undelete_query, full_undelete_params).rowcount
                    if row_count_undelete == 0:
                        raise ConflictError(
                            f"Failed to undelete {table_name} '{main_col_value}' due to version mismatch or it became active/disappeared.",
                            entity=table_name, entity_id=main_col_value)
                    logger.info(
                        f"Undeleted and updated {table_name} '{main_col_value}' with ID: {item_id}, new version {next_version}.")
                    return item_id

                # If not undeleting, proceed with insert
                cursor_insert = conn.execute(query, params_tuple_insert)
                item_id_insert = cursor_insert.lastrowid if hasattr(cursor_insert, 'lastrowid') else None
                if item_id_insert is None and self.backend_type == BackendType.POSTGRESQL:
                    sel = conn.execute(
                        f"SELECT id FROM {table_name} WHERE {unique_col_name} = ?",
                        (main_col_value,)
                    )
                    row = sel.fetchone()
                    if row is not None:
                        item_id_insert = int(row['id'] if isinstance(row, dict) else row[0])
                logger.info(f"Added {table_name} '{main_col_value}' with ID: {item_id_insert}.")
                return item_id_insert
        except sqlite3.IntegrityError as e:
             if f"unique constraint failed: {table_name}.{unique_col_name}" in str(e).lower(): # Use lower for robustness
                logger.warning(f"{table_name} with {unique_col_name} '{main_col_value}' already exists and is active.")
                raise ConflictError(f"{table_name} '{main_col_value}' already exists and is active.", entity=table_name,
                                    entity_id=main_col_value) from e
             raise CharactersRAGDBError(f"Database integrity error adding {table_name}: {e}") from e
        except ConflictError: # From undelete path
            raise
        except CharactersRAGDBError as e:
            logger.error(f"Database error adding {table_name} '{main_col_value}': {e}")
            raise
        return None  # Should not be reached if exceptions are raised properly

    def _get_generic_item_by_id(self, table_name: str, item_id: int) -> Optional[Dict[str, Any]]:
        """
        Internal helper: Retrieves a non-deleted item by its auto-increment integer ID.

        Args:
            table_name: The database table name.
            item_id: The integer ID of the item.

        Returns:
            A dictionary of the item's data if found and active, else None.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        table_name = self._map_table_for_backend(table_name)
        query = f"SELECT * FROM {table_name} WHERE id = ? AND deleted = 0"
        try:
            cursor = self.execute_query(query, (item_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except CharactersRAGDBError as e:
            logger.error(f"Database error fetching {table_name} ID {item_id}: {e}")
            raise

    def _get_generic_item_by_unique_text(self, table_name: str, unique_col_name: str, value: str) -> Optional[Dict[str, Any]]:
        """
        Internal helper: Retrieves a non-deleted item by a unique text column value.
        Assumes the column has `COLLATE NOCASE` if case-insensitive search is desired.

        Args:
            table_name: The database table name.
            unique_col_name: The name of the unique text column.
            value: The text value to search for.

        Returns:
            A dictionary of the item's data if found and active, else None.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        table_name = self._map_table_for_backend(table_name)
        query = f"SELECT * FROM {table_name} WHERE {unique_col_name} = ? AND deleted = 0"
        try:
            cursor = self.execute_query(query, (value,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except CharactersRAGDBError as e:
            logger.error(f"Database error fetching {table_name} by {unique_col_name} '{value}': {e}")
            raise

    def _case_insensitive_order_expression(self, column: str, direction: Optional[str] = None) -> str:
        column_clean = (column or '').strip()
        if not _ORDER_BY_COLUMN_RE.match(column_clean):
            raise InputError(f"Invalid order-by column: {column!r}")
        direction_clean = (direction or '').strip()
        direction_clause = f" {direction_clean}" if direction_clean else ""
        if self.backend_type == BackendType.POSTGRESQL:
            return f"LOWER({column_clean}){direction_clause}"
        return f"{column_clean} COLLATE NOCASE{direction_clause}"

    def _case_insensitive_order_clause(self, column: str, direction: Optional[str] = None) -> str:
        return f"ORDER BY {self._case_insensitive_order_expression(column, direction)}"

    def _list_generic_items(self, table_name: str, order_by_col: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Internal helper: Lists non-deleted items from a table, with specified ordering.

        Args:
            table_name: The database table name.
            order_by_col: The column (and direction) to order by (e.g., "name ASC", "keyword COLLATE NOCASE DESC").
            limit: Maximum number of items.
            offset: Number of items to skip.

        Returns:
            A list of item dictionaries.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        order_by_clean = (order_by_col or "").strip()
        if not _ORDER_BY_EXPR_RE.match(order_by_clean):
            raise InputError(f"Invalid order-by expression: {order_by_col!r}")
        order_expression = order_by_clean
        collate_match = re.search(r"\s+COLLATE\s+NOCASE", order_by_clean, flags=re.IGNORECASE)
        if collate_match:
            base = order_by_clean[:collate_match.start()]
            direction = order_by_clean[collate_match.end():]
            order_expression = self._case_insensitive_order_expression(base.strip(), direction.strip() or None)

        table_name = self._map_table_for_backend(table_name)
        query = f"SELECT * FROM {table_name} WHERE deleted = 0 ORDER BY {order_expression} LIMIT ? OFFSET ?"
        try:
            cursor = self.execute_query(query, (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError as e:
            logger.error(f"Database error listing {table_name}: {e}")
            raise

    def _update_generic_item(self, table_name: str, item_id: Union[int, str],
                             update_data: Dict[str, Any], expected_version: int,
                             allowed_fields: List[str], pk_col_name: str = "id",
                             unique_col_name_in_data: Optional[str] = None) -> bool | None:
        """
        Internal helper: Updates an item in a table using optimistic locking.

        Args:
            table_name: The table to update.
            item_id: The ID (PK) of the item to update (int or str for UUIDs).
            update_data: Dictionary containing data to update. Must not be empty.
            expected_version: Client's expected version for optimistic locking.
            allowed_fields: List of field names that are permitted to be updated from `update_data`.
            pk_col_name: Name of the primary key column. Defaults to "id".
            unique_col_name_in_data: If an updatable field has a unique constraint
                                     (e.g., 'name' for collections), specify its data key name
                                     here for targeted ConflictError on unique violation.

        Returns:
            True if the update was successful.

        Raises:
            InputError: If `update_data` is empty or contains no allowed fields to update.
            ConflictError: For version mismatch, record not found/deleted, or unique constraint violation
                           if `unique_col_name_in_data` is specified and violated.
            CharactersRAGDBError: For other database errors.
        """
        if not update_data:
            raise InputError(f"No data provided for update of {table_name} ID {item_id}.")

        now = self._get_current_utc_timestamp_iso()
        fields_to_update_sql = []
        params_for_set_clause = []

        for key, value in update_data.items():
            if key in allowed_fields:
                fields_to_update_sql.append(f"{key} = ?")
                # Special handling for specific field types if necessary, e.g., stripping title
                if table_name == "notes" and key == "title" and isinstance(value, str):
                    params_for_set_clause.append(value.strip())
                else:
                    params_for_set_clause.append(value)
            elif key not in [pk_col_name, 'created_at', 'last_modified', 'version', 'client_id', 'deleted']:
                logger.warning(
                    f"Attempted to update immutable or unknown field '{key}' in {table_name} ID {item_id}, skipping.")

        if not fields_to_update_sql:
            # This means update_data either was empty (caught above) or contained only non-allowed fields.
            # Depending on desired behavior, this could be an error or a "no fields to update" success.
            # Current behavior implies if allowed_fields are updated, it proceeds. If not, it may not update anything.
            # For safety, ensure metadata is only updated if there are actual field changes or if it's an explicit "touch".
            # The calling methods (e.g., update_note) handle this: "if not fields_to_update_sql: return True"
            # This helper should proceed if there's anything to set.
            logger.info(f"No recognized updatable fields provided in update_data for {table_name} ID {item_id}. Will only update metadata if version matches.")
            # If we must update metadata anyway if version matches:
            # Fall through to add metadata updates. The query will work fine.


        next_version_val = expected_version + 1
        current_fields_to_update_sql = list(fields_to_update_sql) # clone
        current_params_for_set_clause = list(params_for_set_clause) # clone

        current_fields_to_update_sql.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        current_params_for_set_clause.extend([now, next_version_val, self.client_id])

        # Values for the WHERE clause
        where_clause_values = [item_id, expected_version]
        final_query_params = tuple(current_params_for_set_clause + where_clause_values)

        query = f"UPDATE {table_name} SET {', '.join(current_fields_to_update_sql)} WHERE {pk_col_name} = ? AND version = ? AND deleted = 0"

        try:
            with self.transaction() as conn:
                # Explicit pre-check. _get_current_db_version raises ConflictError if not found or soft-deleted.
                current_db_version = self._get_current_db_version(conn, table_name, pk_col_name, item_id)

                if current_db_version != expected_version:
                    raise ConflictError(
                        f"{table_name} ID {item_id} was modified: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity=table_name, entity_id=item_id
                    )

                # If current_db_version == expected_version, proceed with the update.
                cursor = conn.execute(query, final_query_params)

                if cursor.rowcount == 0:
                    # This state implies the record was active with expected_version during the _get_current_db_version check,
                    # but was either deleted or its version changed *just before* the UPDATE SQL executed.
                    check_again_cursor = conn.execute(
                        f"SELECT version, deleted FROM {table_name} WHERE {pk_col_name} = ?", (item_id,))
                    final_state = check_again_cursor.fetchone()
                    msg = f"Update for {table_name} ID {item_id} (expected version {expected_version}) affected 0 rows."
                    if not final_state:
                        msg = f"{table_name} ID {item_id} disappeared before update completion (was version {expected_version})."
                    elif final_state['deleted']:
                        msg = f"{table_name} ID {item_id} was soft-deleted concurrently (expected version {expected_version} for update)."
                    elif final_state['version'] != expected_version:
                        msg = f"{table_name} ID {item_id} version changed to {final_state['version']} concurrently (expected {expected_version} for update)."
                    raise ConflictError(msg, entity=table_name, entity_id=item_id)

                logger.info(
                    f"Updated {table_name} ID {item_id} from version {expected_version} to version {next_version_val}.")
                return True
        except sqlite3.IntegrityError as e:
            if unique_col_name_in_data and unique_col_name_in_data in update_data:
                # More specific check for the unique column mentioned
                db_unique_col_name = unique_col_name_in_data # Assuming it matches DB col name for this check
                if f"UNIQUE constraint failed: {table_name}.{db_unique_col_name}".lower() in str(e).lower():
                    val = update_data[unique_col_name_in_data]
                    logger.warning(
                        f"Update failed for {table_name} ID {item_id}: {db_unique_col_name} '{val}' already exists.")
                    raise ConflictError(
                        f"Cannot update {table_name} ID {item_id}: {db_unique_col_name} '{val}' already exists.",
                        entity=table_name, entity_id=val) from e
            logger.error(
                f"SQLite integrity error during update of {table_name} ID {item_id} (expected version {expected_version}): {e}",
                exc_info=True)
            raise CharactersRAGDBError(f"Database integrity error updating {table_name} ({item_id}): {e}") from e
        except ConflictError:
            raise
        except InputError: # Should be caught by callers if they check 'update_data' emptiness first
            raise
        except CharactersRAGDBError as e:
            logger.error(
                f"Database error updating {table_name} ID {item_id} (expected version {expected_version}): {e}",
                exc_info=True)
            raise
        # No implicit return None, function should return True or raise.

    def _soft_delete_generic_item(self, table_name: str, item_id: Union[int, str],
                                  expected_version: int, pk_col_name: str = "id") -> bool | None:
        """
        Internal helper: Soft-deletes an item in a table using optimistic locking.

        Sets `deleted = 1`, updates `last_modified`, `version`, `client_id`.

        Args:
            table_name: The table to update.
            item_id: The ID (PK) of the item to soft-delete (int or str).
            expected_version: Client's expected version for optimistic locking.
            pk_col_name: Name of the primary key column. Defaults to "id".

        Returns:
            True if successful or if the item was already soft-deleted.

        Raises:
            ConflictError: For version mismatch if active, or if record not found (and not already deleted),
                           or if a concurrent modification prevents the update.
            CharactersRAGDBError: For other database errors.
        """
        logical_table_name = table_name
        table_name = self._map_table_for_backend(table_name)
        now = self._get_current_utc_timestamp_iso()
        next_version_val = expected_version + 1

        query = f"UPDATE {table_name} SET deleted = 1, last_modified = ?, version = ?, client_id = ? WHERE {pk_col_name} = ? AND version = ? AND deleted = 0"
        params = (now, next_version_val, self.client_id, item_id, expected_version)

        try:
            with self.transaction() as conn:
                try:
                    current_db_version = self._get_current_db_version(conn, table_name, pk_col_name, item_id)
                    # If we are here, record is active and current_db_version is its version.
                except ConflictError as e:
                    # Check if the ConflictError is because it's already soft-deleted.
                    # Query again to be absolutely sure of the 'deleted' status.
                    check_deleted_cursor = conn.execute(
                        f"SELECT deleted, version FROM {table_name} WHERE {pk_col_name} = ?", (item_id,))
                    record_status = check_deleted_cursor.fetchone()

                    if record_status and record_status['deleted']:
                        logger.info(
                            f"{logical_table_name} ID {item_id} already soft-deleted. Operation considered successful (idempotent).")
                        return True
                    raise e # Re-raise if not found or other conflict

                if current_db_version != expected_version:
                    raise ConflictError(
                        f"Soft delete failed for {logical_table_name} ID {item_id}: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity=logical_table_name, entity_id=item_id
                    )

                cursor = conn.execute(query, params)

                if cursor.rowcount == 0:
                    # This means the record (which was active with expected_version) changed state
                    # between the _get_current_db_version check and the UPDATE execution.
                    check_again_cursor = conn.execute(
                        f"SELECT deleted, version FROM {table_name} WHERE {pk_col_name} = ?", (item_id,))
                    changed_record = check_again_cursor.fetchone()
                    msg = f"Soft delete for {logical_table_name} ID {item_id} (expected version {expected_version}) affected 0 rows."
                    if not changed_record:
                        raise ConflictError(
                            f"{logical_table_name} ID {item_id} disappeared before soft-delete completion (expected version {expected_version}).",
                            entity=logical_table_name, entity_id=item_id)

                    if changed_record['deleted']:
                        # If it got deleted by another process, and the new version matches what we intended, it's fine.
                        if changed_record['version'] == next_version_val:
                            logger.info(
                                f"{logical_table_name} ID {item_id} was soft-deleted concurrently to version {next_version_val}. Operation successful.")
                            return True
                        else:
                            raise ConflictError(
                                f"{logical_table_name} ID {item_id} was soft-deleted concurrently to an unexpected version {changed_record['version']} (expected to set to {next_version_val}).",
                                entity=logical_table_name, entity_id=item_id)

                    if changed_record['version'] != expected_version:  # Still active, but version changed
                        raise ConflictError(
                            f"Soft delete failed for {logical_table_name} ID {item_id}: version changed to {changed_record['version']} concurrently (expected {expected_version}).",
                            entity=logical_table_name, entity_id=item_id)

                    raise ConflictError(
                        f"Soft delete for {logical_table_name} ID {item_id} (expected version {expected_version}) affected 0 rows for an unknown reason after passing initial checks.",
                        entity=logical_table_name, entity_id=item_id)

                logger.info(
                    f"Soft-deleted {logical_table_name} ID {item_id} (was version {expected_version}), new version {next_version_val}.")
                return True
        except ConflictError:
            raise
        except CharactersRAGDBError as e:  # Catches sqlite3.Error from conn.execute
            logger.error(
                f"Database error soft-deleting {logical_table_name} ID {item_id} (expected version {expected_version}): {e}",
                exc_info=True)
            raise
        # No implicit return None.

    def _search_generic_items_fts(self, fts_table_name: str, main_table_name: str, fts_match_cols_or_table: str,
                                  search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Internal helper: Performs FTS search on tables like keywords, notes, collections.

        Assumes the main table's PK is `id` (for keywords, collections) or `rowid` maps
        correctly (for notes via `content_rowid='rowid'`).
        The join condition is `fts.rowid = main.id` or `fts.rowid = main.rowid` depending on FTS setup.
        Schema shows `content_rowid='id'` for keywords/collections and `content_rowid='rowid'` for notes.
        This helper uses `fts.rowid = main.id` which is fine for keywords/collections.
        For notes, `search_notes` uses `fts.rowid = main.rowid` which is correct.
        This helper is mainly for tables where PK `id` is the FTS `rowid`.

        Args:
            fts_table_name: Name of the FTS virtual table.
            main_table_name: Name of the main content table.
            fts_match_cols_or_table: The column(s) in FTS table to match against (e.g., "keyword"),
                                     or the FTS table name if using table-name matching
                                     (e.g., "notes_fts MATCH ?").
            search_term: The FTS search query string.
            limit: Max number of results.

        Returns:
            List of matching item dictionaries from the main table. Can be empty.

        Raises:
            CharactersRAGDBError: For database search errors.
        """
        # The join condition ON fts.rowid = main.id is generally for tables where 'id' is an alias for rowid
        # or FTS is configured with content_rowid='id'.
        # For tables like 'notes' where 'id' is TEXT UUID and FTS uses 'rowid', the join is different.
        # This helper as written is best for keywords and keyword_collections.
        if self.backend_type == BackendType.POSTGRESQL:
            tsquery = FTSQueryTranslator.normalize_query(search_term, 'postgresql')
            if not tsquery:
                logger.debug(
                    "Generic FTS query normalized to empty tsquery for table '%s' with input '%s'",
                    main_table_name,
                    search_term,
                )
                return []

            fts_column = f"{fts_table_name}_tsv"
            query = f"""
                SELECT main.*, ts_rank(main.{fts_column}, to_tsquery('english', ?)) AS rank
                FROM {main_table_name} main
                WHERE main.deleted = FALSE
                  AND main.{fts_column} @@ to_tsquery('english', ?)
                ORDER BY rank DESC, main.last_modified DESC
                LIMIT ?
            """
            try:
                cursor = self.execute_query(query, (tsquery, tsquery, limit))
                return [dict(row) for row in cursor.fetchall()]
            except CharactersRAGDBError as exc:
                logger.error("PostgreSQL FTS search failed for table '%s': %s", main_table_name, exc)
                raise

        # Use explicit table-name for MATCH and bm25() for SQLite FTS5 compatibility
        query = f"""
            SELECT main.*
            FROM {fts_table_name}, {main_table_name} main
            WHERE {fts_table_name}.rowid = main.id
              AND {fts_table_name} MATCH ? AND main.deleted = 0
            ORDER BY bm25({fts_table_name})
            LIMIT ?
        """
        try:
            cursor = self.execute_query(query, (search_term, limit))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError as e:
            logger.error(f"Error searching {main_table_name} for '{search_term}': {e}")
            raise

    # Keywords
    def add_keyword(self, keyword_text: str) -> Optional[int]:
        """
        Adds a new keyword or undeletes an existing soft-deleted one.

        Keyword text is stripped of leading/trailing whitespace.
        Uniqueness is case-insensitive due to `COLLATE NOCASE` on the `keyword` column (schema).
        FTS and sync_log entries are handled by SQL triggers.

        Args:
            keyword_text: The text of the keyword. Cannot be empty or whitespace only.

        Returns:
            The integer ID of the keyword.

        Raises:
            InputError: If `keyword_text` is empty or effectively empty after stripping.
            ConflictError: If an active keyword with the same text already exists, or if undelete fails.
            CharactersRAGDBError: For other database errors.
        """
        if not keyword_text or not keyword_text.strip():
            raise InputError("Keyword text cannot be empty.")
        return self._add_generic_item("keywords", "keyword", {}, keyword_text.strip(), {})  # No other_fields_map

    def get_keyword_by_id(self, keyword_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a keyword by its integer ID. Returns active (non-deleted) keywords only.

        Args:
            keyword_id: The ID of the keyword.

        Returns:
            Keyword data as a dictionary, or None if not found/deleted.
        """
        return self._get_generic_item_by_id("keywords", keyword_id)

    def get_keyword_by_text(self, keyword_text: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a keyword by its text (case-insensitive due to schema).
        Returns active (non-deleted) keywords only.

        Args:
            keyword_text: The text of the keyword (stripped before query).

        Returns:
            Keyword data as a dictionary, or None if not found/deleted.
        """
        return self._get_generic_item_by_unique_text("keywords", "keyword", keyword_text.strip())

    def list_keywords(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Lists active keywords, ordered by text (case-insensitively).

        Args:
            limit: Max number of keywords.
            offset: Number to skip.

        Returns:
            A list of keyword dictionaries.
        """
        return self._list_generic_items("keywords", "keyword COLLATE NOCASE", limit, offset)

    def count_keywords(self) -> int:
        """Return count of active (non-deleted) keywords."""
        keyword_table = self._map_table_for_backend("keywords")
        query = f"SELECT COUNT(*) AS cnt FROM {keyword_table} WHERE deleted = 0"
        try:
            cursor = self.execute_query(query)
            row = cursor.fetchone()
            return int(row["cnt"]) if row else 0
        except CharactersRAGDBError as exc:
            logger.error(f"Error counting keywords: {exc}")
            raise

    def soft_delete_keyword(self, keyword_id: int, expected_version: int) -> bool:
        """
        Soft-deletes a keyword using optimistic locking.

        Sets `deleted = 1`, updates metadata. Succeeds if `expected_version` matches
        and record is active. Idempotent if already deleted.
        FTS and sync_log handled by triggers.

        Args:
            keyword_id: The ID of the keyword to soft-delete.
            expected_version: The version number the client expects the record to have.

        Returns:
            True if successful or already deleted.

        Raises:
            ConflictError: If not found (not deleted), or active with version mismatch.
            CharactersRAGDBError: For other database errors.
        """
        return self._soft_delete_generic_item(
            table_name="keywords",
            item_id=keyword_id,
            expected_version=expected_version,
            pk_col_name="id" # Explicitly pass, though "id" is default
        )

    def search_keywords(self, search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Searches keywords by text using FTS.

        Matches against the 'keyword' field in `keywords_fts`.
        Returns active keywords, ordered by relevance.

        Args:
            search_term: FTS query string for keyword text.
            limit: Max number of results.

        Returns:
            A list of matching keyword dictionaries.
        """
        if search_term is None:
            raise InputError("Search term cannot be empty.")
        search_term = search_term.strip()
        if not search_term:
            raise InputError("Search term cannot be empty.")
        if '"' in search_term or "'" in search_term:
            raise InputError("Search term contains unsupported characters.")
        is_simple_token = re.fullmatch(r"[\w-]+", search_term) is not None
        if self.backend_type == BackendType.POSTGRESQL:
            if is_simple_token:
                tsquery = FTSQueryTranslator.normalize_query(search_term, 'postgresql')
                if tsquery:
                    source_table = self._map_table_for_backend("keywords")
                    fts_column = "keywords_fts_tsv"
                    query = f"""
                        SELECT k.*, ts_rank(k.{fts_column}, to_tsquery('english', ?)) AS rank
                        FROM {source_table} k
                        WHERE k.deleted = FALSE
                          AND k.{fts_column} @@ to_tsquery('english', ?)
                        ORDER BY rank DESC, k.last_modified DESC
                        LIMIT ?
                    """
                    try:
                        cursor = self.execute_query(query, (tsquery, tsquery, limit))
                        return [dict(row) for row in cursor.fetchall()]
                    except CharactersRAGDBError as exc:
                        logger.error("PostgreSQL FTS search failed for keywords term '%s': %s", search_term, exc)
                        raise
                logger.debug("Keyword search term normalized to empty tsquery for input '%s'", search_term)
                return []

            # Non-simple tokens (e.g., "C++") skip FTS and fall back to ILIKE.
            source_table = self._map_table_for_backend("keywords")
            escaped = search_term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = f"""
                SELECT k.*
                FROM {source_table} k
                WHERE k.deleted = FALSE
                  AND k.keyword ILIKE ? ESCAPE '\\'
                ORDER BY k.last_modified DESC
                LIMIT ?
            """
            cursor = self.execute_query(query, (f"%{escaped}%", limit))
            return [dict(row) for row in cursor.fetchall()]

        # SQLite: use FTS prefix for simple tokens.
        if is_simple_token:
            # Support prefix/substring search expectations in tests by using prefix match
            # e.g., 'fru' should match 'fruit'. FTS5 uses '*' for prefix queries.
            fts_query = f"{search_term}*"
            try:
                return self._search_generic_items_fts("keywords_fts", "keywords", "keyword", fts_query, limit)
            except CharactersRAGDBError as exc:
                msg = str(exc).lower()
                if "fts" in msg or "match" in msg or "syntax" in msg:
                    raise InputError("Search term contains unsupported characters.") from exc
                raise

        keyword_table = self._map_table_for_backend("keywords")
        escaped = search_term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = f"""
            SELECT k.*
            FROM {keyword_table} k
            WHERE k.deleted = 0
              AND k.keyword LIKE ? ESCAPE '\\'
            ORDER BY k.last_modified DESC
            LIMIT ?
        """
        cursor = self.execute_query(query, (f"%{escaped}%", limit))
        return [dict(row) for row in cursor.fetchall()]

    # Keyword Collections
    def add_keyword_collection(self, name: str, parent_id: Optional[int] = None) -> Optional[int]:
        """
        Adds a new keyword collection or undeletes an existing one.

        Collection name is stripped. Uniqueness is case-insensitive (`COLLATE NOCASE` in schema).
        FTS and sync_log handled by triggers.

        Args:
            name: The name of the collection. Cannot be empty or whitespace only.
            parent_id: Optional integer ID of a parent collection for hierarchy.

        Returns:
            The integer ID of the collection.

        Raises:
            InputError: If `name` is empty.
            ConflictError: If an active collection with the same name exists, or undelete fails.
            CharactersRAGDBError: For other DB errors.
        """
        if not name or not name.strip():
            raise InputError("Collection name cannot be empty.")
        return self._add_generic_item("keyword_collections", "name", {"parent_id": parent_id}, name.strip(),
                                      {"parent_id": "parent_id"}) # Maps DB 'parent_id' to item_data['parent_id']

    def get_keyword_collection_by_id(self, collection_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a keyword collection by ID. Active collections only.

        Args:
            collection_id: ID of the collection.

        Returns:
            Collection data as dictionary, or None.
        """
        return self._get_generic_item_by_id("keyword_collections", collection_id)

    def get_keyword_collection_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a keyword collection by name (case-insensitive). Active collections only.

        Args:
            name: Name of the collection (stripped).

        Returns:
            Collection data as dictionary, or None.
        """
        return self._get_generic_item_by_unique_text("keyword_collections", "name", name.strip())

    def list_keyword_collections(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Lists active keyword collections, ordered by name (case-insensitively).

        Args:
            limit: Max number of collections.
            offset: Number to skip.

        Returns:
            A list of collection dictionaries.
        """
        return self._list_generic_items("keyword_collections", "name COLLATE NOCASE", limit, offset)

    def update_keyword_collection(self, collection_id: int, update_data: Dict[str, Any], expected_version: int) -> bool:
        """
        Updates a keyword collection with optimistic locking.

        Args:
            collection_id: The ID of the keyword collection to update.
            update_data: A dictionary containing the fields to update (e.g., 'name', 'parent_id').
            expected_version: The version number the client expects the record to have.

        Returns:
            True if the update was successful.

        Raises:
            InputError: If no update data is provided.
            ConflictError: If the record is not found, already soft-deleted,
                           or if the expected_version does not match the current database version.
            CharactersRAGDBError: For other database-related errors.
        """
        # pk_col_name for 'keyword_collections' is 'id' (default in _update_generic_item)
        # item_id is int.
        return self._update_generic_item(
            table_name="keyword_collections",
            item_id=collection_id,
            update_data=update_data,
            expected_version=expected_version,
            allowed_fields=['name', 'parent_id'],
            pk_col_name="id", # Explicitly pass, though "id" is default
            unique_col_name_in_data='name' # For handling unique constraint on name if it's updated
        )

    def soft_delete_keyword_collection(self, collection_id: int, expected_version: int) -> bool:
        """
        Soft-deletes a keyword collection with optimistic locking.

        Args:
            collection_id: The ID of the keyword collection to soft-delete.
            expected_version: The version number the client expects the record to have.

        Returns:
            True if the soft-delete was successful or if the collection was already soft-deleted.

        Raises:
            ConflictError: If the record is not found, or if (it's active and)
                           the expected_version does not match the current database version.
            CharactersRAGDBError: For other database-related errors.
        """
        # pk_col_name for 'keyword_collections' is 'id' (default in _soft_delete_generic_item)
        # item_id is int.
        return self._soft_delete_generic_item(
            table_name="keyword_collections",
            item_id=collection_id,
            expected_version=expected_version,
            pk_col_name="id" # Explicitly pass, though "id" is default
        )

    def search_keyword_collections(self, search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        safe_literal = search_term.replace('"', '""')
        safe_search_term = f'"{safe_literal}"'
        return self._search_generic_items_fts("keyword_collections_fts", "keyword_collections", "name", safe_search_term,
                                              limit)

    # Notes (Now with UUID and specific methods)
    def add_note(
        self,
        title: str,
        content: str,
        note_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> str | None:
        if not title or not title.strip():
            raise InputError("Note title cannot be empty.")
        if content is None: # Allow empty string for content
            raise InputError("Note content cannot be None.")

        final_note_id = note_id or self._generate_uuid()
        now = self._get_current_utc_timestamp_iso()
        client_id_to_use = self.client_id # Notes use the instance's client_id directly
        normalized_conversation_id = self._normalize_nullable_text(conversation_id)
        normalized_message_id = self._normalize_nullable_text(message_id)

        query = """
            INSERT INTO notes (id, title, content, last_modified, client_id, version, deleted, created_at, conversation_id, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if self.backend_type == BackendType.POSTGRESQL:
            params = (
                final_note_id, title.strip(), content, now, client_id_to_use, 1, False, now,
                normalized_conversation_id, normalized_message_id
            )
        else:
            params = (
                final_note_id, title.strip(), content, now, client_id_to_use, 1, 0, now,
                normalized_conversation_id, normalized_message_id
            )

        try:
            with self.transaction() as conn:
                conn.execute(query, params)
                logger.info(f"Added note '{title.strip()}' with ID: {final_note_id}.")
                return final_note_id
        except sqlite3.IntegrityError as e:
            msg = str(e).lower()
            if "foreign key constraint failed" in msg:
                raise ConflictError("Conversation or message not found.", entity="notes", entity_id=final_note_id) from e
            if "unique constraint failed: notes.id" in msg:
                raise ConflictError(f"Note with ID '{final_note_id}' already exists.", entity="notes", entity_id=final_note_id) from e
            raise CharactersRAGDBError(f"Database integrity error adding note: {e}") from e
        except BackendDatabaseError as e:
            msg = str(e).lower()
            if "foreign key" in msg:
                raise ConflictError("Conversation or message not found.", entity="notes", entity_id=final_note_id) from e
            if "duplicate key" in msg or "unique constraint" in msg:
                raise ConflictError(f"Note with ID '{final_note_id}' already exists.", entity="notes", entity_id=final_note_id) from e
            raise CharactersRAGDBError(f"Backend error adding note: {e}") from e
        except CharactersRAGDBError as e:
            logger.error(f"Database error adding note '{title.strip()}': {e}")
            raise

    def get_note_by_id(self, note_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM notes WHERE id = ? AND deleted = 0"
        cursor = self.execute_query(query, (note_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_notes(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        # Using _list_generic_items but ensuring table name and order_by_col are correct for notes
        return self._list_generic_items("notes", "last_modified DESC", limit, offset)

    def count_notes(self) -> int:
        """Return count of active (non-deleted) notes."""
        query = "SELECT COUNT(*) AS cnt FROM notes WHERE deleted = 0"
        try:
            cursor = self.execute_query(query)
            row = cursor.fetchone()
            return int(row["cnt"]) if row else 0
        except CharactersRAGDBError as exc:
            logger.error(f"Error counting notes: {exc}")
            raise

    def update_note(self, note_id: str, update_data: Dict[str, Any], expected_version: int) -> bool | None:
        if not update_data:
            raise InputError("No data provided for note update.")

        now = self._get_current_utc_timestamp_iso()
        fields_to_update_sql = []
        params_for_set_clause = []

        allowed_to_update = ['title', 'content', 'conversation_id', 'message_id']
        for key, value in update_data.items():
            if key in allowed_to_update:
                if key == 'title' and isinstance(value, str):
                    fields_to_update_sql.append(f"{key} = ?")
                    params_for_set_clause.append(value.strip())
                elif key in ('conversation_id', 'message_id'):
                    fields_to_update_sql.append(f"{key} = ?")
                    params_for_set_clause.append(self._normalize_nullable_text(value))
                else:
                    fields_to_update_sql.append(f"{key} = ?")
                    params_for_set_clause.append(value)
            elif key not in ['id', 'created_at', 'last_modified', 'version', 'client_id', 'deleted']:
                logger.warning(
                    f"Attempted to update immutable or unknown field '{key}' in note ID {note_id}, skipping.")

        if not fields_to_update_sql:
            logger.info(f"No updatable fields provided for note ID {note_id}.")
            return True

        next_version_val = expected_version + 1
        fields_to_update_sql.extend(["last_modified = ?", "version = ?", "client_id = ?"])

        all_set_values = params_for_set_clause[:]
        all_set_values.extend([now, next_version_val, self.client_id])

        where_values = [note_id, expected_version]
        final_params_for_execute = tuple(all_set_values + where_values)

        query = f"UPDATE notes SET {', '.join(fields_to_update_sql)} WHERE id = ? AND version = ? AND deleted = 0"

        try:
            with self.transaction() as conn:
                current_db_version = self._get_current_db_version(conn, "notes", "id", note_id)

                if current_db_version != expected_version:
                    raise ConflictError(
                        f"Note ID {note_id} update failed: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity="notes", entity_id=note_id
                    )

                cursor = conn.execute(query, final_params_for_execute)

                if cursor.rowcount == 0:
                    check_again_cursor = conn.execute("SELECT version, deleted FROM notes WHERE id = ?", (note_id,))
                    final_state = check_again_cursor.fetchone()
                    if not final_state:
                        msg = f"Note ID {note_id} disappeared."
                    elif final_state['deleted']:
                        msg = f"Note ID {note_id} was soft-deleted concurrently."
                    elif final_state['version'] != expected_version:
                        msg = f"Note ID {note_id} version changed to {final_state['version']} concurrently."
                    else:
                        msg = f"Update for note ID {note_id} (expected v{expected_version}) affected 0 rows."
                    raise ConflictError(msg, entity="notes", entity_id=note_id)

                logger.info(f"Updated note ID {note_id} from version {expected_version} to version {next_version_val}.")
                return True
        # No specific UNIQUE constraint on notes.title or notes.content in the schema, so sqlite3.IntegrityError less likely for these fields.
        except ConflictError:
            raise
        except sqlite3.IntegrityError as e:
            msg = str(e).lower()
            if "foreign key constraint failed" in msg:
                raise ConflictError("Conversation or message not found.", entity="notes", entity_id=note_id) from e
            raise CharactersRAGDBError(f"Database integrity error updating note: {e}") from e
        except BackendDatabaseError as e:
            msg = str(e).lower()
            if "foreign key" in msg:
                raise ConflictError("Conversation or message not found.", entity="notes", entity_id=note_id) from e
            raise CharactersRAGDBError(f"Backend error updating note: {e}") from e
        except CharactersRAGDBError as e:  # Catches sqlite3.Error
            logger.error(f"Database error updating note ID {note_id} (expected v{expected_version}): {e}",
                         exc_info=True)
            raise

    def soft_delete_note(self, note_id: str, expected_version: int) -> bool | None:
        now = self._get_current_utc_timestamp_iso()
        next_version_val = expected_version + 1

        query = "UPDATE notes SET deleted = 1, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ? AND deleted = 0"
        params = (now, next_version_val, self.client_id, note_id, expected_version)

        try:
            with self.transaction() as conn:
                try:
                    current_db_version = self._get_current_db_version(conn, "notes", "id", note_id)
                except ConflictError as e:
                    check_status_cursor = conn.execute("SELECT deleted, version FROM notes WHERE id = ?", (note_id,))
                    record_status = check_status_cursor.fetchone()
                    if record_status and record_status['deleted']:
                        logger.info(f"Note ID {note_id} already soft-deleted. Success (idempotent).")
                        return True
                    raise e

                if current_db_version != expected_version:
                    raise ConflictError(
                        f"Soft delete for Note ID {note_id} failed: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity="notes", entity_id=note_id
                    )

                cursor = conn.execute(query, params)

                if cursor.rowcount == 0:
                    check_again_cursor = conn.execute("SELECT version, deleted FROM notes WHERE id = ?", (note_id,))
                    final_state = check_again_cursor.fetchone()
                    if not final_state:
                        msg = f"Note ID {note_id} disappeared."
                    elif final_state['deleted']:
                        logger.info(f"Note ID {note_id} was soft-deleted concurrently. Success.")
                        return True
                    elif final_state['version'] != expected_version:
                        msg = f"Note ID {note_id} version changed to {final_state['version']} concurrently."
                    else:
                        msg = f"Soft delete for note ID {note_id} (expected v{expected_version}) affected 0 rows."
                    raise ConflictError(msg, entity="notes", entity_id=note_id)

                logger.info(
                    f"Soft-deleted note ID {note_id} (was v{expected_version}), new version {next_version_val}.")
                return True
        except ConflictError:
            raise
        except CharactersRAGDBError as e:
            logger.error(f"Database error soft-deleting note ID {note_id} (expected v{expected_version}): {e}",
                         exc_info=True)
            raise

    def delete_note(self, note_id: str, expected_version: Optional[int] = None, hard_delete: bool = False) -> bool:
        """Soft or hard delete a note."""
        now = self._get_current_utc_timestamp_iso()
        try:
            with self.transaction() as conn:
                row = conn.execute("SELECT id, version, deleted FROM notes WHERE id = ?", (note_id,)).fetchone()
                if not row:
                    return False
                cur_ver = int(row["version"])
                deleted = bool(row["deleted"])
                if hard_delete:
                    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                    return True
                if deleted:
                    return True
                if expected_version is not None and cur_ver != expected_version:
                    raise ConflictError("Version mismatch deleting note", entity="notes", identifier=note_id)
                deleted_val = True if self.backend_type == BackendType.POSTGRESQL else 1
                rc = conn.execute(
                    "UPDATE notes SET deleted = ?, last_modified = ?, version = ?, client_id = ? "
                    "WHERE id = ? AND deleted = 0",
                    (deleted_val, now, cur_ver + 1, self.client_id, note_id),
                ).rowcount
                return rc > 0
        except BackendDatabaseError as e:
            raise CharactersRAGDBError(f"Failed to delete note: {e}") from e
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to delete note: {e}") from e

    def restore_note(self, note_id: str, expected_version: int) -> bool | None:
        """
        Restores a soft-deleted note using optimistic locking.

        Sets the `deleted` flag to 0, updates `last_modified`, increments `version`,
        and sets `client_id`. The operation succeeds only if `expected_version` matches
        the current database version and the note is currently deleted.

        If the note is already active (not deleted), the method considers
        this a success and returns True (idempotency).

        Args:
            note_id: The ID of the note to restore.
            expected_version: The version number the client expects the record to have.

        Returns:
            True if the restore was successful or if the note was already active.

        Raises:
            ConflictError: If the note is not found, or if `expected_version` does
                           not match, or if a concurrent modification prevents the update.
            CharactersRAGDBError: For other database-related errors.
        """
        now = self._get_current_utc_timestamp_iso()
        next_version_val = expected_version + 1

        query = "UPDATE notes SET deleted = 0, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ? AND deleted = 1"
        params = (now, next_version_val, self.client_id, note_id, expected_version)

        try:
            with self.transaction() as conn:
                # First check if record exists at all
                check_cursor = conn.execute("SELECT deleted, version FROM notes WHERE id = ?", (note_id,))
                record_status = check_cursor.fetchone()

                if not record_status:
                    raise ConflictError(
                        f"Note ID {note_id} not found.",
                        entity="notes", entity_id=note_id
                    )

                # If already active, return success (idempotent)
                if not record_status['deleted']:
                    logger.info(f"Note ID {note_id} already active. Restore successful (idempotent).")
                    return True

                # Check version matches
                current_db_version = record_status['version']
                if current_db_version != expected_version:
                    raise ConflictError(
                        f"Restore for Note ID {note_id} failed: version mismatch (db has {current_db_version}, client expected {expected_version}).",
                        entity="notes", entity_id=note_id
                    )

                cursor = conn.execute(query, params)

                if cursor.rowcount == 0:
                    # Race condition: Record changed between pre-check and UPDATE.
                    check_again_cursor = conn.execute("SELECT version, deleted FROM notes WHERE id = ?", (note_id,))
                    final_state = check_again_cursor.fetchone()
                    msg = f"Restore for Note ID {note_id} (expected v{expected_version}) affected 0 rows."
                    if not final_state:
                        msg = f"Note ID {note_id} disappeared before restore (expected deleted version {expected_version})."
                    elif not final_state['deleted']:
                        # If it got restored by another process. Consider this success.
                        logger.info(
                            f"Note ID {note_id} was restored concurrently to version {final_state['version']}. Restore successful.")
                        return True
                    elif final_state['version'] != expected_version:
                        msg = f"Restore for Note ID {note_id} failed: version changed to {final_state['version']} concurrently (expected {expected_version})."
                    else:
                        msg = f"Restore for Note ID {note_id} (expected version {expected_version}) affected 0 rows for an unknown reason after passing initial checks."
                    raise ConflictError(msg, entity="notes", entity_id=note_id)

                logger.info(
                    f"Restored note ID {note_id} (was version {expected_version}), new version {next_version_val}.")
                return True
        except ConflictError:
            raise
        except BackendDatabaseError as e:
            logger.error(
                "Backend error restoring note ID %s (expected v%s): %s",
                note_id,
                expected_version,
                e,
            )
            raise CharactersRAGDBError(f"Backend error during restore: {e}") from e
        except CharactersRAGDBError as e:
            logger.error(
                f"Database error restoring note ID {note_id} (expected v{expected_version}): {e}",
                exc_info=True)
            raise

    def search_notes(self, search_term: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Searches notes_fts (title and content) with optional pagination."""
        # FTS5 requires wrapping terms with special characters in double quotes
        # to be treated as a literal phrase.

        # Debug: Log FTS table state to help diagnose E2E test failures
        try:
            fts_count = self.execute_query("SELECT COUNT(*) as cnt FROM notes_fts").fetchone()
            notes_count = self.execute_query("SELECT COUNT(*) as cnt FROM notes WHERE deleted = 0").fetchone()
            logger.debug(
                f"search_notes: term='{search_term[:50] if search_term else ''}' notes_fts_count={fts_count['cnt'] if fts_count else 0} "
                f"notes_count={notes_count['cnt'] if notes_count else 0}"
            )
        except Exception as diag_err:
            logger.debug(f"search_notes diagnostic query failed: {diag_err}")

        if self.backend_type == BackendType.POSTGRESQL:
            tsquery = FTSQueryTranslator.normalize_query(search_term, 'postgresql')
            if not tsquery:
                logger.debug("Notes search term normalized to empty tsquery for input '%s'", search_term)
                return []

            query = """
                SELECT n.*, ts_rank(n.notes_fts_tsv, to_tsquery('english', ?)) AS rank
                FROM notes n
                WHERE n.deleted = FALSE
                  AND n.notes_fts_tsv @@ to_tsquery('english', ?)
                ORDER BY rank DESC, n.last_modified DESC
                LIMIT ? OFFSET ?
            """
            try:
                cursor = self.execute_query(query, (tsquery, tsquery, limit, offset))
                return [dict(row) for row in cursor.fetchall()]
            except CharactersRAGDBError as exc:
                logger.error("PostgreSQL FTS search failed for notes term '%s': %s", search_term, exc)
                raise

        safe_literal = search_term.replace('"', '""')
        safe_search_term = f'"{safe_literal}"'

        query = """
                SELECT main.*, bm25(notes_fts) AS bm25_score
                FROM notes_fts
                JOIN notes AS main ON notes_fts.rowid = main.rowid
                WHERE notes_fts MATCH ?
                  AND main.deleted = 0
                ORDER BY bm25_score, main.last_modified DESC
                LIMIT ? OFFSET ?
                """
        try:
            cursor = self.execute_query(query, (safe_search_term, limit, offset))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError as e:
            logger.error(f"Error searching notes for '{search_term}': {e}")
            raise


    def search_notes_with_keywords(
        self,
        search_term: Optional[str],
        keyword_tokens: List[str],
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search notes with an optional FTS query and keyword-token filter."""
        tokens = [t.strip().lower() for t in keyword_tokens if isinstance(t, str) and t.strip()]
        if not tokens:
            if not search_term or not str(search_term).strip():
                return []
            return self.search_notes(search_term=str(search_term), limit=limit, offset=offset)

        keyword_table = self._map_table_for_backend("keywords")
        like_clause = " OR ".join(["LOWER(k.keyword) LIKE ?"] * len(tokens))
        like_params = [f"%{t}%" for t in tokens]

        if self.backend_type == BackendType.POSTGRESQL:
            if search_term and str(search_term).strip():
                tsquery = FTSQueryTranslator.normalize_query(str(search_term), 'postgresql')
                if not tsquery:
                    logger.debug("Notes search term normalized to empty tsquery for input '%s'", search_term)
                    return []
                query = f"""
                    SELECT DISTINCT n.*, ts_rank(n.notes_fts_tsv, to_tsquery('english', ?)) AS rank
                    FROM notes n
                    JOIN note_keywords nk ON n.id = nk.note_id
                    JOIN {keyword_table} k ON k.id = nk.keyword_id
                    WHERE n.deleted = FALSE
                      AND k.deleted = FALSE
                      AND n.notes_fts_tsv @@ to_tsquery('english', ?)
                      AND ({like_clause})
                    ORDER BY rank DESC, n.last_modified DESC
                    LIMIT ? OFFSET ?
                """
                params = (tsquery, tsquery, *like_params, limit, offset)
            else:
                query = f"""
                    SELECT DISTINCT n.*
                    FROM notes n
                    JOIN note_keywords nk ON n.id = nk.note_id
                    JOIN {keyword_table} k ON k.id = nk.keyword_id
                    WHERE n.deleted = FALSE
                      AND k.deleted = FALSE
                      AND ({like_clause})
                    ORDER BY n.last_modified DESC
                    LIMIT ? OFFSET ?
                """
                params = (*like_params, limit, offset)
            cursor = self.execute_query(query, params)
            return [dict(row) for row in cursor.fetchall()]

        if search_term and str(search_term).strip():
            safe_literal = str(search_term).replace('"', '""')
            safe_search_term = f'"{safe_literal}"'
            query = f"""
                    SELECT DISTINCT n.*
                    FROM notes_fts
                    JOIN notes AS n ON notes_fts.rowid = n.rowid
                    JOIN note_keywords nk ON n.id = nk.note_id
                    JOIN {keyword_table} k ON k.id = nk.keyword_id
                    WHERE notes_fts MATCH ?
                      AND n.deleted = 0
                      AND k.deleted = 0
                      AND ({like_clause})
                    ORDER BY bm25(notes_fts), n.last_modified DESC
                    LIMIT ? OFFSET ?
                    """
            params = (safe_search_term, *like_params, limit, offset)
        else:
            query = f"""
                    SELECT DISTINCT n.*
                    FROM notes n
                    JOIN note_keywords nk ON n.id = nk.note_id
                    JOIN {keyword_table} k ON k.id = nk.keyword_id
                    WHERE n.deleted = 0
                      AND k.deleted = 0
                      AND ({like_clause})
                    ORDER BY n.last_modified DESC
                    LIMIT ? OFFSET ?
                    """
            params = (*like_params, limit, offset)

        cursor = self.execute_query(query, params)
        return [dict(row) for row in cursor.fetchall()]


    def count_notes_matching(self, search_term: str) -> int:
        """Returns the total number of active notes matching the FTS query."""
        if self.backend_type == BackendType.POSTGRESQL:
            tsquery = FTSQueryTranslator.normalize_query(search_term, 'postgresql')
            if not tsquery:
                return 0
            query = """
                SELECT COUNT(*) AS cnt
                FROM notes n
                WHERE n.deleted = FALSE
                  AND n.notes_fts_tsv @@ to_tsquery('english', ?)
            """
            try:
                cursor = self.execute_query(query, (tsquery,))
                row = cursor.fetchone()
                return int(row["cnt"]) if row else 0
            except CharactersRAGDBError as exc:
                logger.error("PostgreSQL FTS count failed for notes term '%s': %s", search_term, exc)
                raise

        safe_literal = search_term.replace('"', '""')
        safe_search_term = f'"{safe_literal}"'
        query = """
                SELECT COUNT(*) AS cnt
                FROM notes_fts
                JOIN notes AS main ON notes_fts.rowid = main.rowid
                WHERE notes_fts MATCH ?
                  AND main.deleted = 0
        """
        try:
            cursor = self.execute_query(query, (safe_search_term,))
            row = cursor.fetchone()
            return int(row["cnt"]) if row else 0
        except CharactersRAGDBError as exc:
            logger.error("SQLite FTS count failed for notes term '%s': %s", search_term, exc)
            raise


    # --- Linking Table Methods (with manual sync_log entries) ---
    def _manage_link(self, link_table: str, col1_name: str, col1_val: Any, col2_name: str, col2_val: Any,
                     operation: str) -> bool:
        """Helper to add ('link') or remove ('unlink') entries from a linking table."""
        now_iso = self._get_current_utc_timestamp_iso()
        sync_payload_dict: Dict[str, Any] = {}
        log_sync_entry = False
        rows_affected = 0

        try:
            with self.transaction() as conn:
                if operation == "link":
                    if self.backend_type == BackendType.POSTGRESQL:
                        query = (
                            f"INSERT INTO {link_table} ({col1_name}, {col2_name}, created_at) "
                            f"VALUES (?, ?, ?) ON CONFLICT ({col1_name}, {col2_name}) DO NOTHING"
                        )
                    else:
                        query = (
                            f"INSERT OR IGNORE INTO {link_table} ({col1_name}, {col2_name}, created_at) "
                            "VALUES (?, ?, ?)"
                        )
                    params = (col1_val, col2_val, now_iso)
                    cursor = conn.execute(query, params)
                    rows_affected = cursor.rowcount
                    if rows_affected > 0:  # Link was actually created
                        log_sync_entry = True
                        sync_payload_dict = {col1_name: col1_val, col2_name: col2_val, 'created_at': now_iso}
                elif operation == "unlink":
                    query = f"DELETE FROM {link_table} WHERE {col1_name} = ? AND {col2_name} = ?"
                    params = (col1_val, col2_val)
                    cursor = conn.execute(query, params)
                    rows_affected = cursor.rowcount
                    if rows_affected > 0:  # Link was actually deleted
                        log_sync_entry = True
                        sync_payload_dict = {col1_name: col1_val, col2_name: col2_val}
                else:
                    raise InputError("Invalid operation for link management.")

                if log_sync_entry:
                    sync_entity_id = f"{col1_val}_{col2_val}"
                    sync_op = 'create' if operation == 'link' else 'delete'
                    sync_timestamp = now_iso # Use now_iso for create, and also for delete event time

                    entity_col = 'entity_id'
                    if self.backend_type == BackendType.POSTGRESQL:
                        try:
                            cols = {c.get('name') for c in self.backend.get_table_info('sync_log', connection=conn)}
                            if 'entity_uuid' in cols and 'entity_id' not in cols:
                                entity_col = 'entity_uuid'
                        except Exception as e:
                            logger.debug("sync_log column introspection failed on {}: {}", self.backend_type.value, e)
                    assert entity_col in ('entity_id', 'entity_uuid'), f"Unexpected sync_log id column: {entity_col}"

                    sync_log_query = (
                        f"INSERT INTO sync_log (entity, {entity_col}, operation, timestamp, client_id, version, payload) "
                        f"VALUES (?, ?, ?, ?, ?, ?, ?)"
                    )
                    sync_log_params = (
                        link_table, sync_entity_id, sync_op, sync_timestamp,
                        self.client_id, 1, # Link table entries don't have their own version, use 1 for sync log
                        json.dumps(sync_payload_dict)
                    )
                    conn.execute(sync_log_query, sync_log_params)
                    logger.debug(f"Logged sync event for {link_table}: {sync_op} on {sync_entity_id}")

            logger.info(
                f"{operation.capitalize()}ed {link_table}: {col1_name}={col1_val}, {col2_name}={col2_val}. Rows affected: {rows_affected}")
            return rows_affected > 0
        except sqlite3.Error as e:  # Catch SQLite specific errors from conn.execute
            logger.error(
                f"SQLite error during {operation} for {link_table} ({col1_name}={col1_val}, {col2_name}={col2_val}): {e}",
                exc_info=True,
            )
            raise CharactersRAGDBError(f"Database error during {operation} for {link_table}: {e}") from e
        except BackendDatabaseError as exc:
            logger.error(
                "Backend error during %s for %s (%s=%s, %s=%s): %s",
                operation,
                link_table,
                col1_name,
                col1_val,
                col2_name,
                col2_val,
                exc,
                exc_info=True,
            )
            raise CharactersRAGDBError(f"Database error during {operation} for {link_table}: {exc}") from exc
        except CharactersRAGDBError as e:  # Catch custom errors like InputError
            logger.error(f"Application error during {operation} for {link_table}: {e}", exc_info=True)
            raise


    # Conversation <-> Keyword
    def link_conversation_to_keyword(self, conversation_id: str, keyword_id: int) -> bool:
        return self._manage_link("conversation_keywords", "conversation_id", conversation_id, "keyword_id", keyword_id,
                                 "link")

    def unlink_conversation_from_keyword(self, conversation_id: str, keyword_id: int) -> bool:
        return self._manage_link("conversation_keywords", "conversation_id", conversation_id, "keyword_id", keyword_id,
                                 "unlink")

    def get_keywords_for_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        keyword_table = self._map_table_for_backend("keywords")
        order_clause = self._case_insensitive_order_clause("k.keyword")
        query = f"""
                SELECT k.* \
                FROM {keyword_table} k \
                         JOIN conversation_keywords ck ON k.id = ck.keyword_id
                WHERE ck.conversation_id = ? \
                  AND k.deleted = 0 \
                {order_clause}
                """
        cursor = self.execute_query(query, (conversation_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_keywords_for_conversations(self, conversation_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch keywords for multiple conversations in a single query."""
        if not conversation_ids:
            return {}
        keyword_table = self._map_table_for_backend("keywords")
        placeholders = ",".join(["?"] * len(conversation_ids))
        order_expr = self._case_insensitive_order_expression("k.keyword")
        query = f"""
                SELECT ck.conversation_id as conversation_id, k.* \
                FROM {keyword_table} k \
                         JOIN conversation_keywords ck ON k.id = ck.keyword_id
                WHERE ck.conversation_id IN ({placeholders}) \
                  AND k.deleted = 0 \
                ORDER BY ck.conversation_id, {order_expr}
                """
        cursor = self.execute_query(query, tuple(conversation_ids))
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description] if cursor.description else []
        result: Dict[str, List[Dict[str, Any]]] = {cid: [] for cid in conversation_ids}
        for row in rows:
            if isinstance(row, dict):
                record = dict(row)
            else:
                record = {columns[idx]: row[idx] for idx in range(len(columns))}
            conv_id = record.pop("conversation_id", None)
            if conv_id is None:
                continue
            result.setdefault(str(conv_id), []).append(record)
        return result

    def get_conversations_for_keyword(self, keyword_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        query = """
                SELECT c.* \
                FROM conversations c \
                         JOIN conversation_keywords ck ON c.id = ck.conversation_id
                WHERE ck.keyword_id = ? \
                  AND c.deleted = 0
                ORDER BY c.last_modified DESC LIMIT ? \
                OFFSET ? \
                """
        cursor = self.execute_query(query, (keyword_id, limit, offset))
        return [dict(row) for row in cursor.fetchall()]

    # Collection <-> Keyword
    def link_collection_to_keyword(self, collection_id: int, keyword_id: int) -> bool:
        return self._manage_link("collection_keywords", "collection_id", collection_id, "keyword_id", keyword_id,
                                 "link")

    def unlink_collection_from_keyword(self, collection_id: int, keyword_id: int) -> bool:
        return self._manage_link("collection_keywords", "collection_id", collection_id, "keyword_id", keyword_id,
                                 "unlink")

    def get_keywords_for_collection(self, collection_id: int) -> List[Dict[str, Any]]:
        keyword_table = self._map_table_for_backend("keywords")
        order_clause = self._case_insensitive_order_clause("k.keyword")
        query = f"""
                SELECT k.* \
                FROM {keyword_table} k \
                         JOIN collection_keywords ck ON k.id = ck.keyword_id
                WHERE ck.collection_id = ? \
                  AND k.deleted = 0 \
                {order_clause}
                """
        cursor = self.execute_query(query, (collection_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_collections_for_keyword(self, keyword_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        order_clause = self._case_insensitive_order_clause("kc.name")
        query = f"""
                SELECT kc.* \
                FROM keyword_collections kc \
                         JOIN collection_keywords ck ON kc.id = ck.collection_id
                WHERE ck.keyword_id = ? \
                  AND kc.deleted = 0
                {order_clause} LIMIT ? \
                OFFSET ? \
                """
        cursor = self.execute_query(query, (keyword_id, limit, offset))
        return [dict(row) for row in cursor.fetchall()]

    # Note <-> Keyword
    def link_note_to_keyword(self, note_id: str, keyword_id: int) -> bool: # note_id is str
        return self._manage_link("note_keywords", "note_id", note_id, "keyword_id", keyword_id, "link")

    def unlink_note_from_keyword(self, note_id: str, keyword_id: int) -> bool: # note_id is str
        return self._manage_link("note_keywords", "note_id", note_id, "keyword_id", keyword_id, "unlink")

    def get_keywords_for_note(self, note_id: str) -> List[Dict[str, Any]]: # note_id is str
        keyword_table = self._map_table_for_backend("keywords")
        order_clause = self._case_insensitive_order_clause("k.keyword")
        query = f"""
                SELECT k.* \
                FROM {keyword_table} k \
                         JOIN note_keywords nk ON k.id = nk.keyword_id
                WHERE nk.note_id = ? \
                  AND k.deleted = 0 \
                {order_clause}
                """
        cursor = self.execute_query(query, (note_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_keywords_for_notes(self, note_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Return keywords for multiple notes as a map of note_id -> keywords list."""
        if not note_ids:
            return {}
        keyword_table = self._map_table_for_backend("keywords")
        order_clause = self._case_insensitive_order_clause("k.keyword")
        out: Dict[str, List[Dict[str, Any]]] = {nid: [] for nid in note_ids}
        # SQLite has a default variable cap of 999; keep a buffer to be safe.
        max_vars = 900
        for start in range(0, len(note_ids), max_vars):
            batch = note_ids[start:start + max_vars]
            placeholders = ",".join(["?"] * len(batch))
            query = f"""
                    SELECT nk.note_id AS note_id, k.* \
                    FROM {keyword_table} k \
                             JOIN note_keywords nk ON k.id = nk.keyword_id
                    WHERE nk.note_id IN ({placeholders}) \
                      AND k.deleted = 0 \
                    {order_clause}
                    """
            cursor = self.execute_query(query, tuple(batch))
            rows = cursor.fetchall()
            for row in rows:
                record = dict(row)
                note_id = record.pop("note_id", None)
                if not note_id:
                    continue
                out.setdefault(note_id, []).append(record)
        return out

    def get_notes_for_keyword(self, keyword_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        query = """
                SELECT n.* \
                FROM notes n \
                         JOIN note_keywords nk ON n.id = nk.note_id
                WHERE nk.keyword_id = ? \
                  AND n.deleted = 0
                ORDER BY n.last_modified DESC LIMIT ? \
                OFFSET ? \
                """
        cursor = self.execute_query(query, (keyword_id, limit, offset))
        return [dict(row) for row in cursor.fetchall()]

    # ==========================
    # Flashcards & Decks (V5)
    # ==========================
    def add_deck(self, name: str, description: Optional[str] = None) -> int:
        """Create a deck and return its id."""
        now = self._get_current_utc_timestamp_iso()
        try:
            with self.transaction() as conn:
                # Undelete if a deck with the same name exists but is deleted
                deleted_row = conn.execute(
                    "SELECT id, version FROM decks WHERE name = ? AND deleted = 1",
                    (name,),
                ).fetchone()
                if deleted_row:
                    deck_id, current_version = int(deleted_row[0]), int(deleted_row[1])
                    next_version = current_version + 1
                    deleted_value = False if self.backend_type == BackendType.POSTGRESQL else 0
                    rc = conn.execute(
                        (
                            "UPDATE decks SET deleted = ?, last_modified = ?, version = ?, client_id = ?, "
                            "description = COALESCE(?, description) WHERE id = ? AND version = ?"
                        ),
                        (deleted_value, now, next_version, self.client_id, description, deck_id, current_version),
                    ).rowcount
                    if rc == 0:
                        raise ConflictError(
                            "Failed to undelete deck due to version mismatch",
                            entity="decks",
                            identifier=name,
                        )
                    return deck_id
                insert_sql = (
                    "INSERT INTO decks(name, description, created_at, last_modified, client_id, version, deleted)"
                    " VALUES(?, ?, ?, ?, ?, ?, ?)"
                )
                params = (
                    name,
                    description,
                    now,
                    now,
                    self.client_id,
                    1,
                    False,
                )

                if self.backend_type == BackendType.POSTGRESQL:
                    cursor = conn.execute(insert_sql + " RETURNING id", params)
                    row = cursor.fetchone()
                    deck_id = int(row["id"]) if row else None
                else:
                    cursor = conn.execute(insert_sql, params)
                    deck_id = int(cursor.lastrowid)

                if deck_id is None:
                    raise CharactersRAGDBError("Failed to determine deck ID after insert")
                return deck_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: decks.name" in str(e):
                raise ConflictError("Deck name already exists", entity="decks", identifier=name)
            raise CharactersRAGDBError(f"Failed to create deck: {e}") from e
        except BackendDatabaseError as e:
            if self._is_unique_violation(e):
                raise ConflictError("Deck name already exists", entity="decks", identifier=name) from e
            raise CharactersRAGDBError(f"Failed to create deck: {e}") from e
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to create deck: {e}") from e

    def list_decks(self, limit: int = 100, offset: int = 0, include_deleted: bool = False) -> List[Dict[str, Any]]:
        cond = "" if include_deleted else "WHERE deleted = 0"
        query = f"SELECT id, name, description, created_at, last_modified, deleted, client_id, version FROM decks {cond} ORDER BY name LIMIT ? OFFSET ?"
        try:
            cursor = self.execute_query(query, (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError:
            raise

    def get_deck(self, deck_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single deck row by id."""
        query = (
            "SELECT id, name, description, created_at, last_modified, deleted, client_id, version "
            "FROM decks WHERE id = ?"
        )
        try:
            cursor = self.execute_query(query, (deck_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except CharactersRAGDBError:
            raise

    def _get_flashcard_id_from_uuid(self, conn: sqlite3.Connection, card_uuid: str) -> Optional[int]:
        row = conn.execute("SELECT id FROM flashcards WHERE uuid = ? AND deleted = 0", (card_uuid,)).fetchone()
        return int(row[0]) if row else None

    def add_flashcard(self, card_data: Dict[str, Any]) -> str:
        """
        Create a flashcard. card_data keys: deck_id (optional), front, back, notes?, is_cloze?, tags_json?,
        source_ref_type?, source_ref_id?
        Returns uuid.
        """
        now = self._get_current_utc_timestamp_iso()
        uuid_val = self._generate_uuid()
        deck_id = card_data.get('deck_id')
        front = card_data['front']
        back = card_data['back']
        notes = card_data.get('notes')
        extra = card_data.get('extra')
        is_cloze = 1 if card_data.get('is_cloze') else 0
        tags_json = card_data.get('tags_json')
        source_ref_type = card_data.get('source_ref_type', 'manual')
        source_ref_id = card_data.get('source_ref_id')
        conversation_id = self._normalize_nullable_text(card_data.get('conversation_id'))
        message_id = self._normalize_nullable_text(card_data.get('message_id'))
        model_type = card_data.get('model_type')
        reverse_flag = card_data.get('reverse')
        if not model_type:
            if is_cloze:
                model_type = 'cloze'
            else:
                model_type = 'basic_reverse' if reverse_flag else 'basic'
        if model_type not in ('basic', 'basic_reverse', 'cloze'):
            raise InputError("Invalid model_type; must be 'basic','basic_reverse','cloze'")
        # If reverse is not explicitly set, derive from model_type
        if reverse_flag is None:
            reverse_flag = 1 if model_type == 'basic_reverse' else 0
        try:
            with self.transaction() as conn:
                insert_sql = (
                    """
                    INSERT INTO flashcards(
                        uuid, deck_id, front, back, notes, extra, is_cloze, tags_json,
                        source_ref_type, source_ref_id, conversation_id, message_id, ef, interval_days, repetitions,
                        lapses, due_at, last_reviewed_at, created_at, last_modified,
                        deleted, client_id, version, model_type, reverse
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                )

                params = (
                    uuid_val,
                    deck_id,
                    front,
                    back,
                    notes,
                    extra,
                    bool(is_cloze),
                    tags_json,
                    source_ref_type,
                    source_ref_id,
                    conversation_id,
                    message_id,
                    2.5,
                    0,
                    0,
                    0,
                    None,
                    None,
                    now,
                    now,
                    False,
                    self.client_id,
                    1,
                    model_type,
                    bool(reverse_flag),
                )

                conn.execute(insert_sql, params)
                return uuid_val
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to add flashcard: {e}") from e
        except BackendDatabaseError as exc:
            raise CharactersRAGDBError(f"Failed to add flashcard: {exc}") from exc

    def add_flashcards_bulk(self, cards: List[Dict[str, Any]]) -> List[str]:
        """
        Bulk create flashcards; returns list of uuids in the same order.

        Supports newer fields: extra, model_type, reverse. If model_type is not
        provided, it will be inferred from is_cloze/reverse similar to add_flashcard().
        """
        uuids: List[str] = []
        try:
            with self.transaction() as _:
                insert_sql = (
                    """
                    INSERT INTO flashcards(
                        uuid, deck_id, front, back, notes, extra, is_cloze, tags_json,
                        source_ref_type, source_ref_id, conversation_id, message_id, ef, interval_days, repetitions,
                        lapses, due_at, last_reviewed_at, created_at, last_modified,
                        deleted, client_id, version, model_type, reverse
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                )

                params_list: List[tuple] = []
                for card_data in cards:
                    uuid_val = self._generate_uuid()
                    uuids.append(uuid_val)
                    now = self._get_current_utc_timestamp_iso()

                    deck_id = card_data.get('deck_id')
                    front = card_data['front']
                    back = card_data['back']
                    notes = card_data.get('notes')
                    extra = card_data.get('extra')
                    is_cloze = bool(card_data.get('is_cloze'))
                    tags_json = card_data.get('tags_json')
                    source_ref_type = card_data.get('source_ref_type', 'manual')
                    source_ref_id = card_data.get('source_ref_id')
                    conversation_id = self._normalize_nullable_text(card_data.get('conversation_id'))
                    message_id = self._normalize_nullable_text(card_data.get('message_id'))
                    model_type = card_data.get('model_type')
                    reverse_flag = card_data.get('reverse')
                    if not model_type:
                        if is_cloze:
                            model_type = 'cloze'
                        else:
                            model_type = 'basic_reverse' if reverse_flag else 'basic'
                    if model_type not in ('basic', 'basic_reverse', 'cloze'):
                        raise InputError("Invalid model_type; must be 'basic','basic_reverse','cloze'")
                    if reverse_flag is None:
                        reverse_flag = (model_type == 'basic_reverse')

                    params_list.append(
                        (
                            uuid_val,
                            deck_id,
                            front,
                            back,
                            notes,
                            extra,
                            is_cloze,
                            tags_json,
                            source_ref_type,
                            source_ref_id,
                            conversation_id,
                            message_id,
                            2.5,
                            0,
                            0,
                            0,
                            None,
                            None,
                            now,
                            now,
                            False,
                            self.client_id,
                            1,
                            model_type,
                            bool(reverse_flag),
                        )
                    )

                # Batch insert for efficiency (supports both SQLite and Postgres backends)
                self.execute_many(insert_sql, params_list, commit=False)
            return uuids
        except KeyError as e:
            raise InputError(f"Missing required field in bulk flashcard: {e}") from e
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to add flashcards in bulk: {e}") from e
        except BackendDatabaseError as exc:
            raise CharactersRAGDBError(f"Failed to add flashcards in bulk: {exc}") from exc

    def list_flashcards(self,
                        deck_id: Optional[int] = None,
                        tag: Optional[str] = None,
                        due_status: str = 'all',
                        q: Optional[str] = None,
                        include_deleted: bool = False,
                        limit: int = 100,
                        offset: int = 0,
                        order_by: str = 'due_at') -> List[Dict[str, Any]]:
        """List flashcards with filters. due_status in {'new','learning','due','all'}."""
        where_clauses = ["1=1"]
        params: List[Any] = []
        keyword_table = self._map_table_for_backend("keywords")
        if not include_deleted:
            if self.backend_type == BackendType.POSTGRESQL:
                where_clauses.append("f.deleted = FALSE")
            else:
                where_clauses.append("f.deleted = 0")
        if deck_id is not None:
            where_clauses.append("f.deck_id = ?")
            params.append(deck_id)
        # due filter
        now_iso = self._get_current_utc_timestamp_iso()
        if due_status == 'new':
            where_clauses.append("f.last_reviewed_at IS NULL")
        elif due_status == 'learning':
            where_clauses.append("f.last_reviewed_at IS NOT NULL AND f.repetitions IN (1,2)")
        elif due_status == 'due':
            where_clauses.append("f.due_at IS NOT NULL AND f.due_at <= ?")
            params.append(now_iso)

        # tag filter (single tag)
        join_tag = ""
        if tag:
            join_tag = f"JOIN flashcard_keywords fk ON fk.card_id = f.id JOIN {keyword_table} kw ON kw.id = fk.keyword_id"
            where_clauses.append("kw.keyword = ?")
            params.append(tag)

        # FTS filter
        fts_filter = ""
        if q:
            if self.backend_type == BackendType.POSTGRESQL:
                tsquery = FTSQueryTranslator.normalize_query(q, 'postgresql')
                if not tsquery:
                    logger.debug("Flashcard query normalized to empty tsquery for input '%s'", q)
                    return []
                fts_filter = "AND f.flashcards_fts_tsv @@ to_tsquery('english', ?)"
                params.append(tsquery)
            else:
                # Normalize query for SQLite FTS5 (quotes/operators)
                norm_q = FTSQueryTranslator.normalize_query(q, 'sqlite')
                if not norm_q:
                    logger.debug("Flashcard query normalized to empty sqlite tsquery for input '%s'", q)
                    return []
                fts_filter = "AND f.rowid IN (SELECT rowid FROM flashcards_fts WHERE flashcards_fts MATCH ?)"
                params.append(norm_q)

        # order by
        order_sql = "ORDER BY f.due_at, f.created_at DESC" if order_by == 'due_at' else "ORDER BY f.created_at DESC"

        where_sql = " AND ".join(where_clauses)
        query = f"""
            SELECT f.uuid, f.deck_id, d.name AS deck_name, f.front, f.back, f.notes, f.extra, f.is_cloze, f.tags_json,
                   f.ef, f.interval_days, f.repetitions, f.lapses, f.due_at, f.last_reviewed_at,
                   f.created_at, f.last_modified, f.deleted, f.client_id, f.version, f.model_type, f.reverse
            FROM flashcards f
            LEFT JOIN decks d ON d.id = f.deck_id
            {join_tag}
            WHERE {where_sql} {fts_filter}
            {order_sql}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        try:
            cursor = self.execute_query(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError:
            raise

    def count_flashcards(self,
                         deck_id: Optional[int] = None,
                         tag: Optional[str] = None,
                         due_status: str = 'all',
                         q: Optional[str] = None,
                         include_deleted: bool = False) -> int:
        """Count flashcards matching filters. Mirrors list_flashcards filters."""
        where_clauses = ["1=1"]
        params: List[Any] = []
        keyword_table = self._map_table_for_backend("keywords")
        if not include_deleted:
            if self.backend_type == BackendType.POSTGRESQL:
                where_clauses.append("f.deleted = FALSE")
            else:
                where_clauses.append("f.deleted = 0")
        if deck_id is not None:
            where_clauses.append("f.deck_id = ?")
            params.append(deck_id)

        now_iso = self._get_current_utc_timestamp_iso()
        if due_status == 'new':
            where_clauses.append("f.last_reviewed_at IS NULL")
        elif due_status == 'learning':
            where_clauses.append("f.last_reviewed_at IS NOT NULL AND f.repetitions IN (1,2)")
        elif due_status == 'due':
            where_clauses.append("f.due_at IS NOT NULL AND f.due_at <= ?")
            params.append(now_iso)

        join_tag = ""
        if tag:
            join_tag = f"JOIN flashcard_keywords fk ON fk.card_id = f.id JOIN {keyword_table} kw ON kw.id = fk.keyword_id"
            where_clauses.append("kw.keyword = ?")
            params.append(tag)

        fts_filter = ""
        if q:
            if self.backend_type == BackendType.POSTGRESQL:
                tsquery = FTSQueryTranslator.normalize_query(q, 'postgresql')
                if not tsquery:
                    return 0
                fts_filter = "AND f.flashcards_fts_tsv @@ to_tsquery('english', ?)"
                params.append(tsquery)
            else:
                norm_q = FTSQueryTranslator.normalize_query(q, 'sqlite')
                if not norm_q:
                    return 0
                fts_filter = "AND f.rowid IN (SELECT rowid FROM flashcards_fts WHERE flashcards_fts MATCH ?)"
                params.append(norm_q)

        where_sql = " AND ".join(where_clauses)
        # DISTINCT avoids double-counting when tag join introduces duplicates
        query = f"""
            SELECT COUNT(DISTINCT f.id) AS cnt
              FROM flashcards f
              {join_tag}
             WHERE {where_sql} {fts_filter}
        """
        try:
            cursor = self.execute_query(query, tuple(params))
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        except CharactersRAGDBError:
            raise

    def get_flashcards_by_uuids(self, uuids: List[str]) -> List[Dict[str, Any]]:
        """Fetch multiple flashcards by UUIDs in one query. Order is not guaranteed; caller can reorder."""
        if not uuids:
            return []
        placeholders = ",".join(["?"] * len(uuids))
        deleted_clause = "f.deleted = FALSE" if self.backend_type == BackendType.POSTGRESQL else "f.deleted = 0"
        query = f"""
            SELECT f.uuid, f.deck_id, d.name AS deck_name, f.front, f.back, f.notes, f.extra, f.is_cloze, f.tags_json,
                   f.ef, f.interval_days, f.repetitions, f.lapses, f.due_at, f.last_reviewed_at,
                   f.created_at, f.last_modified, f.deleted, f.client_id, f.version, f.model_type, f.reverse
              FROM flashcards f
              LEFT JOIN decks d ON d.id = f.deck_id
             WHERE f.uuid IN ({placeholders}) AND {deleted_clause}
        """
        try:
            cursor = self.execute_query(query, tuple(uuids))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError:
            raise

    # --- PostgreSQL helpers for FTS on flashcards ---
    def _ensure_postgres_flashcards_tsvector(self, conn) -> None:
        """Ensure flashcards_fts_tsv column, index, and update trigger exist for PostgreSQL."""
        if self.backend_type != BackendType.POSTGRESQL:
            return
        try:
            # Add tsvector column
            self.backend.execute(
                "ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS flashcards_fts_tsv tsvector",
                connection=conn,
            )
            # Backfill existing rows
            self.backend.execute(
                (
                    "UPDATE flashcards "
                    "SET flashcards_fts_tsv = to_tsvector('english', "
                    "coalesce(front,'') || ' ' || coalesce(back,'') || ' ' || coalesce(notes,''))"
                ),
                connection=conn,
            )
            # Index
            self.backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_flashcards_fts_tsv ON flashcards USING GIN (flashcards_fts_tsv)",
                connection=conn,
            )
            # Trigger to maintain tsvector
            try:
                # Check if trigger already exists for this table in current schema
                exists_res = self.backend.execute(
                    (
                        "SELECT 1 FROM pg_trigger t "
                        "JOIN pg_class c ON t.tgrelid = c.oid "
                        "JOIN pg_namespace n ON c.relnamespace = n.oid "
                        "WHERE t.tgname = 'flashcards_fts_tsv_update' AND c.relname = 'flashcards' "
                        "AND n.nspname = current_schema()"
                    ),
                    connection=conn,
                )
                exists = bool(getattr(exists_res, 'rows', []) )
            except Exception:
                exists = False
            if not exists:
                self.backend.execute(
                    (
                        "CREATE TRIGGER flashcards_fts_tsv_update "
                        "BEFORE INSERT OR UPDATE OF front, back, notes ON flashcards "
                        "FOR EACH ROW EXECUTE FUNCTION tsvector_update_trigger("
                        "flashcards_fts_tsv, 'pg_catalog.english', front, back, notes)"
                    ),
                    connection=conn,
                )
        except Exception as e:
            # If any statement fails due to existing objects, ignore and proceed
            logger.debug(f"_ensure_postgres_flashcards_tsvector: {e}")

    def _srs_sm2_update(self, ef: float, interval_days: int, repetitions: int, lapses: int, rating: int) -> Dict[str, Any]:
        """
        Apply SM-2 style scheduling update and return new values.
        rating: 0-5 (Anki scale). q<3 counts as lapse.
        """
        q = max(0, min(5, int(rating)))
        was_lapse = q < 3
        if was_lapse:
            lapses += 1
            repetitions = 0
            interval_days = 1
            # EF unchanged for lapse (keep, clamp)
        else:
            # Ease factor update
            ef = ef + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
            ef = max(1.3, ef)
            repetitions += 1
            if repetitions == 1:
                interval_days = 1
            elif repetitions == 2:
                interval_days = 6
            else:
                interval_days = int(round(interval_days * ef)) if interval_days > 0 else 6
        return {
            'ef': float(ef),
            'interval_days': int(interval_days),
            'repetitions': int(repetitions),
            'lapses': int(lapses),
            'was_lapse': was_lapse,
        }

    def review_flashcard(self, card_uuid: str, rating: int, answer_time_ms: Optional[int] = None) -> Dict[str, Any]:
        """Submit a review for a flashcard and update scheduling. Returns updated card fields."""
        now = self._get_current_utc_timestamp_iso()
        try:
            with self.transaction() as conn:
                card = conn.execute(
                    "SELECT id, ef, interval_days, repetitions, lapses FROM flashcards WHERE uuid = ? AND deleted = 0",
                    (card_uuid,)
                ).fetchone()
                if not card:
                    raise ConflictError("Flashcard not found", entity="flashcards", identifier=card_uuid)
                card_id = int(card['id'])
                upd = self._srs_sm2_update(card['ef'], card['interval_days'], card['repetitions'], card['lapses'], rating)

                # Compute next due date
                due_at = datetime.now(timezone.utc) + timedelta(days=upd['interval_days'])
                due_at_iso = due_at.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

                conn.execute(
                    """
                    UPDATE flashcards
                       SET ef = ?, interval_days = ?, repetitions = ?, lapses = ?,
                           last_reviewed_at = ?, due_at = ?, last_modified = ?, version = version + 1, client_id = ?
                     WHERE id = ? AND deleted = 0
                    """,
                    (upd['ef'], upd['interval_days'], upd['repetitions'], upd['lapses'], now, due_at_iso, now, self.client_id, card_id)
                )
                conn.execute(
                    """
                    INSERT INTO flashcard_reviews(card_id, reviewed_at, rating, answer_time_ms, scheduled_interval_days, new_ef, new_repetitions, was_lapse, client_id)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (card_id, now, int(rating), answer_time_ms, upd['interval_days'], upd['ef'], upd['repetitions'], 1 if upd['was_lapse'] else 0, self.client_id)
                )
                updated = conn.execute(
                    "SELECT uuid, ef, interval_days, repetitions, lapses, due_at, last_reviewed_at, last_modified, version FROM flashcards WHERE id = ?",
                    (card_id,)
                ).fetchone()
                return dict(updated)
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to review flashcard: {e}") from e

    def export_flashcards_csv(self,
                              deck_id: Optional[int] = None,
                              tag: Optional[str] = None,
                              q: Optional[str] = None,
                              *,
                              delimiter: str = '\t',
                              include_header: bool = False,
                              extended_header: bool = False) -> bytes:
        """Export flashcards to delimited text. Columns: Deck, Front, Back, Tags, Notes.
        Args:
            delimiter: field separator (default tab)
            include_header: include a header row
        """
        rows = self.list_flashcards(deck_id=deck_id, tag=tag, q=q, due_status='all', include_deleted=False, limit=100000, offset=0)
        output_lines: List[str] = []
        if include_header:
            base_cols = ["Deck", "Front", "Back", "Tags", "Notes"]
            if extended_header:
                base_cols += ["Extra", "Reverse"]
            output_lines.append(delimiter.join(base_cols))
        for r in rows:
            deck_name = r.get('deck_name') or ''
            front = r.get('front') or ''
            back = r.get('back') or ''
            tags = ''
            if r.get('tags_json'):
                try:
                    tags_list = json.loads(r['tags_json'])
                    if isinstance(tags_list, list):
                        tags = " ".join(str(t) for t in tags_list)
                except Exception:
                    tags = ''
            notes = r.get('notes') or ''
            extra = r.get('extra') or ''
            reverse = 'true' if bool(r.get('reverse')) else 'false'
            # Escape delimiter/tabs/newlines minimally
            def esc(s: str) -> str:
                return s.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ').replace(delimiter, ' ').strip()
            row = [esc(deck_name), esc(front), esc(back), esc(tags), esc(notes)]
            if extended_header:
                row += [esc(extra), reverse]
            output_lines.append(delimiter.join(row))
        csv_bytes = ("\n".join(output_lines) + ("\n" if output_lines else "")).encode('utf-8')
        return csv_bytes

    def get_flashcard(self, card_uuid: str) -> Optional[Dict[str, Any]]:
        """Fetch a single flashcard by uuid (active only)."""
        query = """
            SELECT f.uuid, f.deck_id, d.name AS deck_name, f.front, f.back, f.notes, f.extra, f.is_cloze, f.tags_json,
                   f.ef, f.interval_days, f.repetitions, f.lapses, f.due_at, f.last_reviewed_at,
                   f.created_at, f.last_modified, f.deleted, f.client_id, f.version, f.model_type, f.reverse
              FROM flashcards f
              LEFT JOIN decks d ON d.id = f.deck_id
             WHERE f.uuid = ? AND f.deleted = 0
        """
        try:
            cur = self.execute_query(query, (card_uuid,))
            row = cur.fetchone()
            return dict(row) if row else None
        except CharactersRAGDBError:
            raise

    def update_flashcard(
        self,
        card_uuid: str,
        updates: Dict[str, Any],
        expected_version: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """
        Update mutable fields: deck_id, front, back, notes, is_cloze, tags_json.
        If expected_version is provided, enforce optimistic locking.
        """
        allowed = {"deck_id", "front", "back", "notes", "extra", "is_cloze", "tags_json", "model_type", "reverse"}
        set_parts = []
        params: List[Any] = []
        for k, v in updates.items():
            if k in allowed:
                set_parts.append(f"{k} = ?")
                params.append(v)
        norm_tags: Optional[List[str]] = None
        if tags is not None:
            norm_tags = [t.strip() for t in tags if t and t.strip()]
            set_parts.append("tags_json = ?")
            params.append(json.dumps(norm_tags))
        if not set_parts:
            if expected_version is None:
                return True
            try:
                with self.transaction() as conn:
                    row = conn.execute(
                        "SELECT version FROM flashcards WHERE uuid = ? AND deleted = 0",
                        (card_uuid,),
                    ).fetchone()
                    if not row:
                        raise CharactersRAGDBError("Flashcard not found or deleted")
                    current_version = int(row[0])
                    if current_version != expected_version:
                        raise ConflictError(
                            "Version mismatch updating flashcard",
                            entity="flashcards",
                            identifier=card_uuid,
                        )
            except sqlite3.Error as e:
                raise CharactersRAGDBError(f"Failed to update flashcard: {e}") from e
            return True
        now = self._get_current_utc_timestamp_iso()
        set_parts.extend(["last_modified = ?", "version = version + 1", "client_id = ?"])
        params.extend([now, self.client_id])

        try:
            with self.transaction() as conn:
                # get id and (optionally) version
                row = conn.execute("SELECT id, version FROM flashcards WHERE uuid = ? AND deleted = 0", (card_uuid,)).fetchone()
                if not row:
                    raise CharactersRAGDBError("Flashcard not found or deleted")
                card_id, current_version = int(row[0]), int(row[1])
                if expected_version is not None and current_version != expected_version:
                    raise ConflictError("Version mismatch updating flashcard", entity="flashcards", identifier=card_uuid)
                if norm_tags is not None:
                    self._sync_flashcard_keyword_links(conn, card_id, norm_tags)
                params_final = params + [card_id]
                query = f"UPDATE flashcards SET {', '.join(set_parts)} WHERE id = ? AND deleted = 0"
                rc = conn.execute(query, tuple(params_final)).rowcount
                return rc > 0
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to update flashcard: {e}") from e

    def soft_delete_flashcard(self, card_uuid: str, expected_version: int) -> bool:
        """Soft delete a flashcard with optimistic locking."""
        now = self._get_current_utc_timestamp_iso()
        try:
            with self.transaction() as conn:
                row = conn.execute("SELECT id, version, deleted FROM flashcards WHERE uuid = ?", (card_uuid,)).fetchone()
                if not row:
                    raise ConflictError("Flashcard not found", entity="flashcards", identifier=card_uuid)
                card_id, cur_ver, deleted = int(row[0]), int(row[1]), int(row[2])
                if deleted:
                    return True
                if cur_ver != expected_version:
                    raise ConflictError("Version mismatch deleting flashcard", entity="flashcards", identifier=card_uuid)
                rc = conn.execute(
                    "UPDATE flashcards SET deleted = 1, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND deleted = 0",
                    (now, expected_version + 1, self.client_id, card_id)
                ).rowcount
                return rc > 0
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to delete flashcard: {e}") from e

    def get_keywords_for_flashcard(self, card_uuid: str) -> List[Dict[str, Any]]:
        """Return keywords linked to a flashcard."""
        keyword_table = self._map_table_for_backend("keywords")
        order_clause = self._case_insensitive_order_clause("kw.keyword")
        query = f"""
            SELECT kw.*
              FROM flashcards f
              JOIN flashcard_keywords fk ON fk.card_id = f.id
              JOIN {keyword_table} kw ON kw.id = fk.keyword_id
             WHERE f.uuid = ? AND f.deleted = 0 AND kw.deleted = 0
             {order_clause}
        """
        try:
            cur = self.execute_query(query, (card_uuid,))
            return [dict(r) for r in cur.fetchall()]
        except CharactersRAGDBError:
            raise

    def set_flashcard_tags(self, card_uuid: str, tags: List[str]) -> bool:
        """
        Replace flashcard tags (keywords) with provided list.
        Ensures keywords exist, links missing, removes extra.
        Also updates flashcards.tags_json accordingly.
        """
        norm_tags = [t.strip() for t in tags if t and t.strip()]
        try:
            with self.transaction() as conn:
                row = conn.execute("SELECT id FROM flashcards WHERE uuid = ? AND deleted = 0", (card_uuid,)).fetchone()
                if not row:
                    raise CharactersRAGDBError("Flashcard not found or deleted")
                card_id = int(row[0])
                self._sync_flashcard_keyword_links(conn, card_id, norm_tags)
                # update tags_json mirror
                conn.execute(
                    "UPDATE flashcards SET tags_json = ?, last_modified = ?, version = version + 1, client_id = ? WHERE id = ?",
                    (json.dumps(norm_tags), self._get_current_utc_timestamp_iso(), self.client_id, card_id),
                )
                return True
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to set flashcard tags: {e}") from e
        except BackendDatabaseError as exc:
            raise CharactersRAGDBError(f"Failed to set flashcard tags: {exc}") from exc

    def _sync_flashcard_keyword_links(self, conn: sqlite3.Connection, card_id: int, tags: List[str]) -> None:
        # current keyword ids
        cur_kw_ids = set(
            r[0] for r in conn.execute(
                "SELECT keyword_id FROM flashcard_keywords WHERE card_id = ?", (card_id,)
            ).fetchall()
        )
        # ensure keywords exist and collect ids
        desired_kw_ids = set()
        for t in tags:
            kw = self.get_keyword_by_text(t)
            if not kw:
                kid = self.add_keyword(t)
            else:
                kid = kw['id']
            if kid is not None:
                desired_kw_ids.add(int(kid))
        # link missing
        insert_ts = self._get_current_utc_timestamp_iso()
        for kid in desired_kw_ids - cur_kw_ids:
            if self.backend_type == BackendType.POSTGRESQL:
                insert_query = (
                    "INSERT INTO flashcard_keywords(card_id, keyword_id, created_at) "
                    "VALUES(?, ?, ?) ON CONFLICT (card_id, keyword_id) DO NOTHING"
                )
            else:
                insert_query = (
                    "INSERT OR IGNORE INTO flashcard_keywords(card_id, keyword_id, created_at) VALUES(?, ?, ?)"
                )
            conn.execute(insert_query, (card_id, int(kid), insert_ts))
        # unlink extras
        for kid in cur_kw_ids - desired_kw_ids:
            conn.execute("DELETE FROM flashcard_keywords WHERE card_id = ? AND keyword_id = ?", (card_id, int(kid)))

    # ==========================
    # Quizzes (V12)
    # ==========================
    def _normalize_quiz_correct_answer(self, question_type: str, correct_answer: Any) -> str:
        """Normalize correct_answer into a consistent stored string."""
        if question_type == "multiple_choice":
            try:
                return str(int(correct_answer))
            except (TypeError, ValueError):
                return "0"
        if question_type == "true_false":
            val = str(correct_answer).strip().lower()
            return "true" if val in {"true", "1", "yes", "y"} else "false"
        return str(correct_answer or "").strip()

    def _deserialize_quiz_question(self, row: Any) -> Optional[Dict[str, Any]]:
        item = self._deserialize_row_fields(row, ["options", "tags_json"])
        if not item:
            return None
        tags = item.pop("tags_json", None)
        if tags is not None:
            item["tags"] = tags
        if item.get("question_type") == "multiple_choice" and item.get("correct_answer") is not None:
            try:
                item["correct_answer"] = int(item["correct_answer"])
            except (TypeError, ValueError):
                pass
        return item

    def _public_quiz_question(self, question: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(question)
        payload.pop("correct_answer", None)
        payload.pop("explanation", None)
        return payload

    def _recount_quiz_questions(self, conn: Any, quiz_id: int) -> int:
        deleted_clause = "deleted = FALSE" if self.backend_type == BackendType.POSTGRESQL else "deleted = 0"
        row = conn.execute(
            f"SELECT COUNT(*) AS count FROM quiz_questions WHERE quiz_id = ? AND {deleted_clause}",
            (quiz_id,),
        ).fetchone()
        total = int(row["count"]) if row else 0
        now = self._get_current_utc_timestamp_iso()
        conn.execute(
            "UPDATE quizzes SET total_questions = ?, last_modified = ?, version = version + 1, client_id = ? WHERE id = ?",
            (total, now, self.client_id, quiz_id),
        )
        return total

    def create_quiz(
        self,
        name: str,
        description: Optional[str] = None,
        workspace_tag: Optional[str] = None,
        media_id: Optional[int] = None,
        time_limit_seconds: Optional[int] = None,
        passing_score: Optional[int] = None,
        client_id: str = "unknown",
    ) -> int:
        """Create a new quiz and return its ID."""
        now = self._get_current_utc_timestamp_iso()
        try:
            with self.transaction() as conn:
                insert_sql = (
                    "INSERT INTO quizzes(name, description, workspace_tag, media_id, total_questions, time_limit_seconds, "
                    "passing_score, deleted, client_id, version, created_at, last_modified) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                )
                params = (
                    name,
                    description,
                    workspace_tag,
                    media_id,
                    0,
                    time_limit_seconds,
                    passing_score,
                    False,
                    client_id or self.client_id,
                    1,
                    now,
                    now,
                )
                if self.backend_type == BackendType.POSTGRESQL:
                    cursor = conn.execute(insert_sql + " RETURNING id", params)
                    row = cursor.fetchone()
                    quiz_id = int(row["id"]) if row else None
                else:
                    cursor = conn.execute(insert_sql, params)
                    quiz_id = int(cursor.lastrowid)
                if quiz_id is None:
                    raise CharactersRAGDBError("Failed to determine quiz ID after insert")
                return quiz_id
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to create quiz: {e}") from e
        except BackendDatabaseError as exc:
            raise CharactersRAGDBError(f"Failed to create quiz: {exc}") from exc

    def get_quiz(self, quiz_id: int, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """Get quiz by ID, returns None if not found or deleted (unless include_deleted)."""
        deleted_clause = "" if include_deleted else "AND deleted = 0"
        query = (
            "SELECT id, name, description, workspace_tag, media_id, total_questions, time_limit_seconds, passing_score, "
            "deleted, client_id, version, created_at, last_modified "
            "FROM quizzes WHERE id = ? " + deleted_clause
        )
        try:
            cursor = self.execute_query(query, (quiz_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except CharactersRAGDBError:
            raise

    def list_quizzes(
        self,
        q: Optional[str] = None,
        media_id: Optional[int] = None,
        workspace_tag: Optional[str] = None,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List quizzes with pagination and optional filters."""
        where_clauses = ["1=1"]
        params: List[Any] = []
        if not include_deleted:
            where_clauses.append("deleted = FALSE" if self.backend_type == BackendType.POSTGRESQL else "deleted = 0")
        if media_id is not None:
            where_clauses.append("media_id = ?")
            params.append(media_id)
        if workspace_tag:
            where_clauses.append("workspace_tag = ?")
            params.append(workspace_tag)
        if q:
            where_clauses.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ?)")
            q_like = f"%{q.lower()}%"
            params.extend([q_like, q_like])

        where_sql = " AND ".join(where_clauses)
        query = (
            "SELECT id, name, description, workspace_tag, media_id, total_questions, time_limit_seconds, passing_score, "
            "deleted, client_id, version, created_at, last_modified "
            f"FROM quizzes WHERE {where_sql} ORDER BY last_modified DESC LIMIT ? OFFSET ?"
        )
        count_query = f"SELECT COUNT(*) AS count FROM quizzes WHERE {where_sql}"
        try:
            cursor = self.execute_query(query, tuple(params + [limit, offset]))
            items = [dict(row) for row in cursor.fetchall()]
            count_cursor = self.execute_query(count_query, tuple(params))
            count_row = count_cursor.fetchone()
            total = int(count_row["count"]) if count_row else 0
            return {"items": items, "count": total}
        except CharactersRAGDBError:
            raise

    def update_quiz(self, quiz_id: int, updates: Dict[str, Any], client_id: str = "unknown") -> bool:
        """Update quiz fields, returns True if successful."""
        expected_version = updates.pop("expected_version", None)
        allowed = {"name", "description", "workspace_tag", "media_id", "time_limit_seconds", "passing_score"}
        set_parts = []
        params: List[Any] = []
        for k, v in updates.items():
            if k in allowed:
                set_parts.append(f"{k} = ?")
                params.append(v)
        if not set_parts:
            if expected_version is None:
                return True
            try:
                with self.transaction() as conn:
                    row = conn.execute("SELECT version FROM quizzes WHERE id = ? AND deleted = 0", (quiz_id,)).fetchone()
                    if not row:
                        return False
                    if int(row["version"]) != expected_version:
                        raise ConflictError("Version mismatch updating quiz", entity="quizzes", identifier=quiz_id)
                return True
            except sqlite3.Error as e:
                raise CharactersRAGDBError(f"Failed to update quiz: {e}") from e
        now = self._get_current_utc_timestamp_iso()
        set_parts.extend(["last_modified = ?", "version = version + 1", "client_id = ?"])
        params.extend([now, client_id or self.client_id])
        try:
            with self.transaction() as conn:
                row = conn.execute("SELECT version FROM quizzes WHERE id = ? AND deleted = 0", (quiz_id,)).fetchone()
                if not row:
                    return False
                current_version = int(row["version"])
                if expected_version is not None and current_version != expected_version:
                    raise ConflictError("Version mismatch updating quiz", entity="quizzes", identifier=quiz_id)
                params_final = params + [quiz_id]
                query = f"UPDATE quizzes SET {', '.join(set_parts)} WHERE id = ? AND deleted = 0"
                rc = conn.execute(query, tuple(params_final)).rowcount
                return rc > 0
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to update quiz: {e}") from e

    def delete_quiz(self, quiz_id: int, expected_version: Optional[int] = None, hard_delete: bool = False) -> bool:
        """Soft or hard delete a quiz."""
        now = self._get_current_utc_timestamp_iso()
        try:
            with self.transaction() as conn:
                row = conn.execute("SELECT id, version, deleted FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
                if not row:
                    return False
                cur_ver = int(row["version"])
                deleted = int(row["deleted"])
                if hard_delete:
                    conn.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
                    return True
                if deleted:
                    return True
                if expected_version is not None and cur_ver != expected_version:
                    raise ConflictError("Version mismatch deleting quiz", entity="quizzes", identifier=quiz_id)
                rc = conn.execute(
                    "UPDATE quizzes SET deleted = 1, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND deleted = 0",
                    (now, cur_ver + 1, self.client_id, quiz_id),
                ).rowcount
                if rc:
                    conn.execute(
                        "UPDATE quiz_questions SET deleted = 1, last_modified = ?, version = version + 1, client_id = ? "
                        "WHERE quiz_id = ? AND deleted = 0",
                        (now, self.client_id, quiz_id),
                    )
                return rc > 0
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to delete quiz: {e}") from e

    def create_question(
        self,
        quiz_id: int,
        question_type: str,
        question_text: str,
        correct_answer: int | str,
        options: Optional[List[str]] = None,
        explanation: Optional[str] = None,
        points: int = 1,
        order_index: int = 0,
        tags: Optional[List[str]] = None,
        client_id: str = "unknown",
    ) -> int:
        """Create a question for a quiz and increment total_questions."""
        now = self._get_current_utc_timestamp_iso()
        norm_correct = self._normalize_quiz_correct_answer(question_type, correct_answer)
        options_json = self._ensure_json_string(options)
        tags_json = self._ensure_json_string(tags)
        try:
            with self.transaction() as conn:
                quiz_row = conn.execute("SELECT id FROM quizzes WHERE id = ? AND deleted = 0", (quiz_id,)).fetchone()
                if not quiz_row:
                    raise ConflictError("Quiz not found", entity="quizzes", identifier=quiz_id)
                insert_sql = (
                    "INSERT INTO quiz_questions(quiz_id, question_type, question_text, options, correct_answer, "
                    "explanation, points, order_index, tags_json, deleted, client_id, version, created_at, last_modified) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                )
                params = (
                    quiz_id,
                    question_type,
                    question_text,
                    options_json,
                    norm_correct,
                    explanation,
                    points,
                    order_index,
                    tags_json,
                    False,
                    client_id or self.client_id,
                    1,
                    now,
                    now,
                )
                if self.backend_type == BackendType.POSTGRESQL:
                    cursor = conn.execute(insert_sql + " RETURNING id", params)
                    row = cursor.fetchone()
                    question_id = int(row["id"]) if row else None
                else:
                    cursor = conn.execute(insert_sql, params)
                    question_id = int(cursor.lastrowid)
                if question_id is None:
                    raise CharactersRAGDBError("Failed to determine question ID after insert")
                self._recount_quiz_questions(conn, quiz_id)
                return question_id
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to create question: {e}") from e
        except BackendDatabaseError as exc:
            raise CharactersRAGDBError(f"Failed to create question: {exc}") from exc

    def get_question(self, question_id: int, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """Get question by ID."""
        deleted_clause = "" if include_deleted else "AND deleted = 0"
        query = (
            "SELECT id, quiz_id, question_type, question_text, options, correct_answer, explanation, points, "
            "order_index, tags_json, deleted, client_id, version, created_at, last_modified "
            "FROM quiz_questions WHERE id = ? " + deleted_clause
        )
        try:
            cursor = self.execute_query(query, (question_id,))
            row = cursor.fetchone()
            return self._deserialize_quiz_question(row) if row else None
        except CharactersRAGDBError:
            raise

    def list_questions(
        self,
        quiz_id: int,
        q: Optional[str] = None,
        include_answers: bool = False,
        limit: Optional[int] = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List questions for a quiz with pagination."""
        where_clauses = ["quiz_id = ?"]
        params: List[Any] = [quiz_id]
        where_clauses.append("deleted = FALSE" if self.backend_type == BackendType.POSTGRESQL else "deleted = 0")

        fts_filter = ""
        if q:
            if self.backend_type == BackendType.POSTGRESQL:
                tsquery = FTSQueryTranslator.normalize_query(q, 'postgresql')
                if not tsquery:
                    return []
                fts_filter = "AND quiz_questions_fts_tsv @@ to_tsquery('english', ?)"
                params.append(tsquery)
            else:
                norm_q = FTSQueryTranslator.normalize_query(q, 'sqlite')
                fts_filter = "AND id IN (SELECT rowid FROM quiz_questions_fts WHERE quiz_questions_fts MATCH ?)"
                params.append(norm_q)

        where_sql = " AND ".join(where_clauses)
        order_clause = "ORDER BY order_index ASC, id ASC"
        limit_clause = ""
        query_params = list(params)
        if limit is not None:
            limit_clause = "LIMIT ? OFFSET ?"
            query_params.extend([int(limit), int(offset)])

        query = (
            "SELECT id, quiz_id, question_type, question_text, options, correct_answer, explanation, points, "
            "order_index, tags_json, deleted, client_id, version, created_at, last_modified "
            f"FROM quiz_questions WHERE {where_sql} {fts_filter} "
            f"{order_clause} {limit_clause}"
        )
        count_query = f"SELECT COUNT(*) AS count FROM quiz_questions WHERE {where_sql} {fts_filter}"
        try:
            cursor = self.execute_query(query, tuple(query_params))
            items: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                question = self._deserialize_quiz_question(row)
                if not question:
                    continue
                if not include_answers:
                    question = self._public_quiz_question(question)
                items.append(question)
            count_cursor = self.execute_query(count_query, tuple(params))
            count_row = count_cursor.fetchone()
            total = int(count_row["count"]) if count_row else 0
            return {"items": items, "count": total}
        except CharactersRAGDBError:
            raise

    def update_question(self, question_id: int, updates: Dict[str, Any], client_id: str = "unknown") -> bool:
        """Update question fields."""
        expected_version = updates.pop("expected_version", None)
        allowed = {"question_type", "question_text", "options", "correct_answer", "explanation", "points", "order_index", "tags"}
        set_parts = []
        params: List[Any] = []
        for k, v in updates.items():
            if k not in allowed:
                continue
            if k == "options":
                set_parts.append("options = ?")
                params.append(self._ensure_json_string(v))
            elif k == "tags":
                set_parts.append("tags_json = ?")
                params.append(self._ensure_json_string(v))
            elif k == "correct_answer":
                question_type = updates.get("question_type")
                if not question_type:
                    row = self.execute_query(
                        "SELECT question_type FROM quiz_questions WHERE id = ? AND deleted = 0",
                        (question_id,),
                    ).fetchone()
                    question_type = row["question_type"] if row else None
                set_parts.append("correct_answer = ?")
                params.append(self._normalize_quiz_correct_answer(str(question_type or "fill_blank"), v))
            else:
                set_parts.append(f"{k} = ?")
                params.append(v)

        if not set_parts:
            if expected_version is None:
                return True
            try:
                with self.transaction() as conn:
                    row = conn.execute("SELECT version FROM quiz_questions WHERE id = ? AND deleted = 0", (question_id,)).fetchone()
                    if not row:
                        return False
                    if int(row["version"]) != expected_version:
                        raise ConflictError("Version mismatch updating question", entity="quiz_questions", identifier=question_id)
                return True
            except sqlite3.Error as e:
                raise CharactersRAGDBError(f"Failed to update question: {e}") from e

        now = self._get_current_utc_timestamp_iso()
        set_parts.extend(["last_modified = ?", "version = version + 1", "client_id = ?"])
        params.extend([now, client_id or self.client_id])

        try:
            with self.transaction() as conn:
                row = conn.execute(
                    "SELECT version FROM quiz_questions WHERE id = ? AND deleted = 0",
                    (question_id,),
                ).fetchone()
                if not row:
                    return False
                current_version = int(row["version"])
                if expected_version is not None and current_version != expected_version:
                    raise ConflictError("Version mismatch updating question", entity="quiz_questions", identifier=question_id)
                params_final = params + [question_id]
                query = f"UPDATE quiz_questions SET {', '.join(set_parts)} WHERE id = ? AND deleted = 0"
                rc = conn.execute(query, tuple(params_final)).rowcount
                return rc > 0
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to update question: {e}") from e

    def delete_question(self, question_id: int, expected_version: Optional[int] = None, hard_delete: bool = False) -> bool:
        """Delete a question and decrement total_questions (or recompute)."""
        now = self._get_current_utc_timestamp_iso()
        try:
            with self.transaction() as conn:
                row = conn.execute(
                    "SELECT id, quiz_id, version, deleted FROM quiz_questions WHERE id = ?",
                    (question_id,),
                ).fetchone()
                if not row:
                    return False
                quiz_id = int(row["quiz_id"])
                cur_ver = int(row["version"])
                deleted = int(row["deleted"])
                if hard_delete:
                    conn.execute("DELETE FROM quiz_questions WHERE id = ?", (question_id,))
                    self._recount_quiz_questions(conn, quiz_id)
                    return True
                if deleted:
                    return True
                if expected_version is not None and cur_ver != expected_version:
                    raise ConflictError("Version mismatch deleting question", entity="quiz_questions", identifier=question_id)
                rc = conn.execute(
                    "UPDATE quiz_questions SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                    "WHERE id = ? AND deleted = 0",
                    (now, cur_ver + 1, self.client_id, question_id),
                ).rowcount
                if rc:
                    self._recount_quiz_questions(conn, quiz_id)
                return rc > 0
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to delete question: {e}") from e

    def start_attempt(self, quiz_id: int, client_id: str = "unknown") -> Dict[str, Any]:
        """Start a new quiz attempt, snapshot questions, returns attempt dict."""
        now = self._get_current_utc_timestamp_iso()
        try:
            with self.transaction() as conn:
                quiz_row = conn.execute("SELECT id FROM quizzes WHERE id = ? AND deleted = 0", (quiz_id,)).fetchone()
                if not quiz_row:
                    raise ConflictError("Quiz not found", entity="quizzes", identifier=quiz_id)
                questions_payload = self.list_questions(quiz_id, include_answers=True, limit=None, offset=0)
                questions = questions_payload.get("items", [])
                total_possible = sum(int(q.get("points") or 0) for q in questions)
                questions_snapshot = json.dumps(questions)
                insert_sql = (
                    "INSERT INTO quiz_attempts(quiz_id, started_at, total_possible, questions_snapshot, answers, client_id) "
                    "VALUES(?, ?, ?, ?, ?, ?)"
                )
                params = (
                    quiz_id,
                    now,
                    total_possible,
                    questions_snapshot,
                    json.dumps([]),
                    client_id or self.client_id,
                )
                if self.backend_type == BackendType.POSTGRESQL:
                    cursor = conn.execute(insert_sql + " RETURNING id", params)
                    row = cursor.fetchone()
                    attempt_id = int(row["id"]) if row else None
                else:
                    cursor = conn.execute(insert_sql, params)
                    attempt_id = int(cursor.lastrowid)
                if attempt_id is None:
                    raise CharactersRAGDBError("Failed to determine attempt ID after insert")
                return {
                    "id": attempt_id,
                    "quiz_id": quiz_id,
                    "started_at": now,
                    "completed_at": None,
                    "score": None,
                    "total_possible": total_possible,
                    "time_spent_seconds": None,
                    "answers": [],
                    "questions": [self._public_quiz_question(q) for q in questions],
                }
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to start attempt: {e}") from e
        except BackendDatabaseError as exc:
            raise CharactersRAGDBError(f"Failed to start attempt: {exc}") from exc

    def submit_attempt(self, attempt_id: int, answers: List[Dict]) -> Dict[str, Any]:
        """Submit answers for an attempt, grade and return results."""
        now = self._get_current_utc_timestamp_iso()
        try:
            with self.transaction() as conn:
                row = conn.execute(
                    "SELECT quiz_id, started_at, total_possible, questions_snapshot, answers FROM quiz_attempts WHERE id = ?",
                    (attempt_id,),
                ).fetchone()
                if not row:
                    raise ConflictError("Attempt not found", entity="quiz_attempts", identifier=attempt_id)
                row_data = dict(row)
                quiz_id = int(row_data["quiz_id"])
                questions_snapshot = row_data.get("questions_snapshot") or "[]"
                try:
                    questions = json.loads(questions_snapshot)
                except json.JSONDecodeError:
                    questions = []
                questions_by_id = {int(q.get("id")): q for q in questions if q.get("id") is not None}

                graded_answers = []
                total_possible = sum(int(q.get("points") or 0) for q in questions)
                score = 0
                total_time_ms = 0
                for ans in answers:
                    qid = ans.get("question_id")
                    question = questions_by_id.get(int(qid)) if qid is not None else None
                    user_answer = ans.get("user_answer")
                    is_correct = False
                    points_awarded = 0
                    correct_answer = None
                    explanation = None
                    if question:
                        is_correct = self._check_answer(question, user_answer)
                        points_val = int(question.get("points") or 0)
                        points_awarded = points_val if is_correct else 0
                        score += points_awarded
                        correct_answer = question.get("correct_answer")
                        explanation = question.get("explanation")
                    time_spent_ms = ans.get("time_spent_ms")
                    if isinstance(time_spent_ms, (int, float)):
                        total_time_ms += int(time_spent_ms)
                    graded_answers.append({
                        "question_id": qid,
                        "user_answer": user_answer,
                        "is_correct": is_correct,
                        "correct_answer": correct_answer,
                        "explanation": explanation,
                        "points_awarded": points_awarded,
                        "time_spent_ms": time_spent_ms,
                    })

                time_spent_seconds = int(total_time_ms / 1000) if total_time_ms else None
                conn.execute(
                    "UPDATE quiz_attempts SET completed_at = ?, score = ?, total_possible = ?, time_spent_seconds = ?, answers = ? "
                    "WHERE id = ?",
                    (now, score, total_possible, time_spent_seconds, json.dumps(graded_answers), attempt_id),
                )

                return {
                    "id": attempt_id,
                    "quiz_id": quiz_id,
                    "started_at": row_data.get("started_at"),
                    "completed_at": now,
                    "score": score,
                    "total_possible": total_possible,
                    "time_spent_seconds": time_spent_seconds,
                    "answers": graded_answers,
                }
        except sqlite3.Error as e:
            raise CharactersRAGDBError(f"Failed to submit attempt: {e}") from e
        except BackendDatabaseError as exc:
            raise CharactersRAGDBError(f"Failed to submit attempt: {exc}") from exc

    def get_attempt(
        self,
        attempt_id: int,
        include_questions: bool = False,
        include_answers: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Get attempt with full answer breakdown."""
        query = (
            "SELECT id, quiz_id, started_at, completed_at, score, total_possible, time_spent_seconds, "
            "questions_snapshot, answers FROM quiz_attempts WHERE id = ?"
        )
        try:
            cursor = self.execute_query(query, (attempt_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = self._deserialize_row_fields(row, ["questions_snapshot", "answers"])
            if not item:
                return None
            questions = item.pop("questions_snapshot", None)
            if include_questions and isinstance(questions, list):
                if include_answers:
                    item["questions"] = questions
                else:
                    item["questions"] = [self._public_quiz_question(q) for q in questions]
            return item
        except CharactersRAGDBError:
            raise

    def list_attempts(
        self,
        quiz_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List attempts with optional quiz filter."""
        where_clauses = ["1=1"]
        params: List[Any] = []
        if quiz_id is not None:
            where_clauses.append("quiz_id = ?")
            params.append(quiz_id)
        where_sql = " AND ".join(where_clauses)
        query = (
            "SELECT id, quiz_id, started_at, completed_at, score, total_possible, time_spent_seconds "
            f"FROM quiz_attempts WHERE {where_sql} ORDER BY started_at DESC LIMIT ? OFFSET ?"
        )
        count_query = f"SELECT COUNT(*) AS count FROM quiz_attempts WHERE {where_sql}"
        try:
            cursor = self.execute_query(query, tuple(params + [limit, offset]))
            items = [dict(row) for row in cursor.fetchall()]
            count_cursor = self.execute_query(count_query, tuple(params))
            count_row = count_cursor.fetchone()
            total = int(count_row["count"]) if count_row else 0
            return {"items": items, "count": total}
        except CharactersRAGDBError:
            raise

    def _check_answer(self, question: Dict[str, Any], user_answer: Any) -> bool:
        """Grade a single answer based on question type."""
        q_type = question.get("question_type")
        correct = question.get("correct_answer")
        if q_type == "multiple_choice":
            try:
                return int(user_answer) == int(correct)
            except (TypeError, ValueError):
                return False
        if q_type == "true_false":
            if user_answer is None or correct is None:
                return False
            return str(user_answer).strip().lower() == str(correct).strip().lower()
        if q_type == "fill_blank":
            if user_answer is None or correct is None:
                return False
            return str(user_answer).strip().lower() == str(correct).strip().lower()
        return False

    # --- Writing Playground Methods ---
    def _normalize_writing_name(self, name: str, entity_label: str) -> str:
        """
        Normalize and validate a writing entity name.

        Args:
            name: Raw name value supplied by the caller.
            entity_label: Label used in error messages (e.g., "Session", "Template").

        Returns:
            The normalized name string.

        Raises:
            InputError: If the name is empty or whitespace-only.
        """
        if not name or not str(name).strip():
            raise InputError(f"{entity_label} name cannot be empty.")
        return str(name).strip()

    def _serialize_writing_payload(self, payload: Dict[str, Any], entity_label: str) -> str:
        """
        Serialize a writing payload to JSON for storage.

        Args:
            payload: Payload dictionary to serialize.
            entity_label: Label used in error messages (e.g., "Session", "Template").

        Returns:
            JSON-serialized payload string.

        Raises:
            InputError: If the payload is None or not JSON-serializable.
        """
        if payload is None:
            raise InputError(f"{entity_label} payload cannot be None.")
        try:
            return json.dumps(payload, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise InputError(f"{entity_label} payload must be JSON-serializable.") from exc

    def _serialize_json_payload(self, payload: Any, entity_label: str) -> str:
        """
        Serialize an arbitrary payload to JSON for storage.

        Args:
            payload: JSON-serializable payload.
            entity_label: Label used in error messages.

        Returns:
            JSON-serialized payload string.

        Raises:
            InputError: If the payload is None or not JSON-serializable.
        """
        if payload is None:
            raise InputError(f"{entity_label} payload cannot be None.")
        try:
            return json.dumps(payload, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise InputError(f"{entity_label} payload must be JSON-serializable.") from exc

    def add_writing_session(
        self,
        name: str,
        payload: Dict[str, Any],
        *,
        schema_version: int = 1,
        session_id: Optional[str] = None,
        version_parent_id: Optional[str] = None,
    ) -> str:
        """
        Create a writing session for the Writing Playground.

        Args:
            name: User-facing session name.
            payload: Session payload to store; will be JSON-serialized.
            schema_version: Payload schema version (must be >= 1).
            session_id: Optional explicit session UUID to store.
            version_parent_id: Optional parent session ID for versioning.

        Returns:
            The session ID for the newly created record.

        Raises:
            InputError: If inputs are invalid or payload cannot be serialized.
            ConflictError: If the session ID already exists.
            CharactersRAGDBError: For database errors.
        """
        if not isinstance(schema_version, int) or schema_version < 1:
            raise InputError("Session schema_version must be an integer >= 1.")
        session_name = self._normalize_writing_name(name, "Session")
        payload_json = self._serialize_writing_payload(payload, "Session")
        final_id = session_id or self._generate_uuid()
        now = self._get_current_utc_timestamp_iso()
        query = (
            "INSERT INTO writing_sessions "
            "(id, name, payload_json, schema_version, version_parent_id, created_at, last_modified, deleted, client_id, version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        version_parent_id = self._normalize_nullable_text(version_parent_id)
        if self.backend_type == BackendType.POSTGRESQL:
            params = (
                final_id,
                session_name,
                payload_json,
                schema_version,
                version_parent_id,
                now,
                now,
                False,
                self.client_id,
                1,
            )
        else:
            params = (
                final_id,
                session_name,
                payload_json,
                schema_version,
                version_parent_id,
                now,
                now,
                0,
                self.client_id,
                1,
            )
        try:
            with self.transaction() as conn:
                conn.execute(query, params)
                logger.info("Added writing session '%s' with ID: %s.", session_name, final_id)
                return final_id
        except sqlite3.IntegrityError as e:
            msg = str(e).lower()
            if "unique constraint failed: writing_sessions.id" in msg:
                raise ConflictError(
                    f"Session with ID '{final_id}' already exists.",
                    entity="writing_sessions",
                    entity_id=final_id,
                ) from e
            raise CharactersRAGDBError(f"Database integrity error adding writing session: {e}") from e
        except BackendDatabaseError as exc:
            msg = str(exc).lower()
            if "duplicate key" in msg or "unique constraint" in msg:
                raise ConflictError(
                    f"Session with ID '{final_id}' already exists.",
                    entity="writing_sessions",
                    entity_id=final_id,
                ) from exc
            raise CharactersRAGDBError(f"Backend error adding writing session: {exc}") from exc

    def get_writing_session(self, session_id: str, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """
        Fetch a writing session by ID.

        Args:
            session_id: The session UUID.
            include_deleted: Whether to include soft-deleted records.

        Returns:
            The session record with a deserialized "payload", or None if not found.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        deleted_clause = "" if include_deleted else "AND deleted = 0"
        query = f"SELECT * FROM writing_sessions WHERE id = ? {deleted_clause}"
        try:
            cursor = self.execute_query(query, (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = self._deserialize_row_fields(row, ["payload_json"])
            if not item:
                return None
            item["payload"] = item.pop("payload_json", None)
            return item
        except CharactersRAGDBError:
            raise

    def list_writing_sessions(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List non-deleted writing sessions with pagination.

        Args:
            limit: Maximum number of sessions to return.
            offset: Number of sessions to skip.

        Returns:
            A list of session summaries (id, name, last_modified, version).

        Raises:
            CharactersRAGDBError: For database errors.
        """
        query = (
            "SELECT id, name, last_modified, version "
            "FROM writing_sessions WHERE deleted = 0 "
            "ORDER BY last_modified DESC LIMIT ? OFFSET ?"
        )
        try:
            cursor = self.execute_query(query, (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError as exc:
            logger.error(f"Database error listing writing sessions: {exc}")
            raise

    def count_writing_sessions(self) -> int:
        """
        Return the count of non-deleted writing sessions.

        Returns:
            The number of active (non-deleted) sessions.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        query = "SELECT COUNT(*) AS cnt FROM writing_sessions WHERE deleted = 0"
        try:
            cursor = self.execute_query(query)
            row = cursor.fetchone()
            return int(row["cnt"]) if row else 0
        except CharactersRAGDBError as exc:
            logger.error(f"Database error counting writing sessions: {exc}")
            raise

    def update_writing_session(
        self,
        session_id: str,
        update_data: Dict[str, Any],
        expected_version: int,
    ) -> bool | None:
        """
        Update a writing session using optimistic locking.

        Args:
            session_id: The session UUID to update.
            update_data: Fields to update; payload can be provided as "payload" (dict)
                or "payload_json" (str-like).
            expected_version: The version the client expects to update.

        Returns:
            True if the update succeeds.

        Raises:
            InputError: If update_data is empty or payload is invalid.
            ConflictError: If the session is missing, deleted, or version-mismatched.
            CharactersRAGDBError: For database errors.
        """
        payload = update_data.get("payload")
        if isinstance(payload, dict):
            update_data = dict(update_data)
            update_data["payload_json"] = self._serialize_writing_payload(
                update_data.pop("payload"),
                "Session",
            )
        else:
            payload_json = update_data.get("payload_json")
            if payload_json is not None and not isinstance(payload_json, str):
                update_data = dict(update_data)
                update_data["payload_json"] = self._serialize_writing_payload(
                    payload_json,
                    "Session",
                )
        allowed_fields = ["name", "payload_json", "schema_version", "version_parent_id"]
        return self._update_generic_item(
            "writing_sessions",
            session_id,
            update_data,
            expected_version,
            allowed_fields,
            pk_col_name="id",
        )

    def soft_delete_writing_session(self, session_id: str, expected_version: int) -> bool | None:
        """
        Soft-delete a writing session using optimistic locking.

        Args:
            session_id: The session UUID to soft-delete.
            expected_version: The version the client expects to delete.

        Returns:
            True if the session was deleted or already deleted.

        Raises:
            ConflictError: If the session is missing or version-mismatched.
            CharactersRAGDBError: For database errors.
        """
        return self._soft_delete_generic_item("writing_sessions", session_id, expected_version, pk_col_name="id")

    def clone_writing_session(self, session_id: str, *, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Clone a writing session, optionally renaming the copy.

        Args:
            session_id: The source session UUID to clone.
            name: Optional name for the cloned session.

        Returns:
            The newly created session record.

        Raises:
            ConflictError: If the source session does not exist.
            CharactersRAGDBError: If the cloned session cannot be retrieved.
        """
        existing = self.get_writing_session(session_id)
        if not existing:
            raise ConflictError("Writing session not found.", entity="writing_sessions", entity_id=session_id)
        clone_name = self._normalize_writing_name(name or f"{existing['name']} (copy)", "Session")
        payload = existing.get("payload") or {}
        schema_version = int(existing.get("schema_version") or 1)
        new_id = self.add_writing_session(
            name=clone_name,
            payload=payload,
            schema_version=schema_version,
            version_parent_id=session_id,
        )
        cloned = self.get_writing_session(new_id)
        if not cloned:
            raise CharactersRAGDBError("Cloned session not found after creation.")
        return cloned

    def add_writing_template(
        self,
        name: str,
        payload: Dict[str, Any],
        *,
        schema_version: int = 1,
        version_parent_id: Optional[str] = None,
        is_default: bool = False,
    ) -> Optional[int]:
        """
        Create a writing template for the Writing Playground.

        Args:
            name: Template name.
            payload: Template payload to store; will be JSON-serialized.
            schema_version: Payload schema version (must be >= 1).
            version_parent_id: Optional parent template ID for versioning.
            is_default: Whether the template should be marked as default.

        Returns:
            The template ID for the newly created record.

        Raises:
            InputError: If inputs are invalid or payload cannot be serialized.
            ConflictError: If a template with the same name already exists.
            CharactersRAGDBError: For database errors.
        """
        if not isinstance(schema_version, int) or schema_version < 1:
            raise InputError("Template schema_version must be an integer >= 1.")
        template_name = self._normalize_writing_name(name, "Template")
        payload_json = self._serialize_writing_payload(payload, "Template")
        item_data = {
            "payload_json": payload_json,
            "schema_version": schema_version,
            "version_parent_id": self._normalize_nullable_text(version_parent_id),
            "is_default": bool(is_default),
        }
        other_fields_map = {
            "payload_json": "payload_json",
            "schema_version": "schema_version",
            "version_parent_id": "version_parent_id",
            "is_default": "is_default",
        }
        return self._add_generic_item("writing_templates", "name", item_data, template_name, other_fields_map)

    def get_writing_template_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a writing template by name.

        Args:
            name: Template name.

        Returns:
            The template record with a deserialized "payload", or None if not found.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        template_name = self._normalize_writing_name(name, "Template")
        row = self._get_generic_item_by_unique_text("writing_templates", "name", template_name)
        if not row:
            return None
        item = dict(row)
        payload_json = item.get("payload_json")
        if isinstance(payload_json, str):
            try:
                item["payload"] = json.loads(payload_json)
            except json.JSONDecodeError:
                item["payload"] = None
        else:
            item["payload"] = None
        item.pop("payload_json", None)
        return item

    def list_writing_templates(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List non-deleted writing templates with pagination.

        Args:
            limit: Maximum number of templates to return.
            offset: Number of templates to skip.

        Returns:
            A list of template records with deserialized "payload".

        Raises:
            CharactersRAGDBError: For database errors.
        """
        query = (
            "SELECT * FROM writing_templates WHERE deleted = 0 "
            "ORDER BY name ASC LIMIT ? OFFSET ?"
        )
        try:
            cursor = self.execute_query(query, (limit, offset))
            items = []
            for row in cursor.fetchall():
                item = dict(row)
                payload_json = item.get("payload_json")
                if isinstance(payload_json, str):
                    try:
                        item["payload"] = json.loads(payload_json)
                    except json.JSONDecodeError:
                        item["payload"] = None
                else:
                    item["payload"] = None
                item.pop("payload_json", None)
                items.append(item)
            return items
        except CharactersRAGDBError as exc:
            logger.error(f"Database error listing writing templates: {exc}")
            raise

    def count_writing_templates(self) -> int:
        """
        Return the count of non-deleted writing templates.

        Returns:
            The number of active (non-deleted) templates.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        query = "SELECT COUNT(*) AS cnt FROM writing_templates WHERE deleted = 0"
        try:
            cursor = self.execute_query(query)
            row = cursor.fetchone()
            return int(row["cnt"]) if row else 0
        except CharactersRAGDBError as exc:
            logger.error(f"Database error counting writing templates: {exc}")
            raise

    def update_writing_template(
        self,
        name: str,
        update_data: Dict[str, Any],
        expected_version: int,
    ) -> bool | None:
        """
        Update a writing template using optimistic locking.

        Args:
            name: Template name to update.
            update_data: Fields to update; payload can be provided as "payload" (dict)
                or "payload_json" (str-like).
            expected_version: The version the client expects to update.

        Returns:
            True if the update succeeds.

        Raises:
            InputError: If update_data is empty or payload is invalid.
            ConflictError: If the template is missing, deleted, or version-mismatched.
            CharactersRAGDBError: For database errors.
        """
        template_name = self._normalize_writing_name(name, "Template")
        payload = update_data.get("payload")
        if isinstance(payload, dict):
            update_data = dict(update_data)
            update_data["payload_json"] = self._serialize_writing_payload(
                update_data.pop("payload"),
                "Template",
            )
        else:
            payload_json = update_data.get("payload_json")
            if payload_json is not None and not isinstance(payload_json, str):
                update_data = dict(update_data)
                update_data["payload_json"] = self._serialize_writing_payload(
                    payload_json,
                    "Template",
                )
        allowed_fields = ["name", "payload_json", "schema_version", "version_parent_id", "is_default"]
        return self._update_generic_item(
            "writing_templates",
            template_name,
            update_data,
            expected_version,
            allowed_fields,
            pk_col_name="name",
            unique_col_name_in_data="name",
        )

    def soft_delete_writing_template(self, name: str, expected_version: int) -> bool | None:
        """
        Soft-delete a writing template using optimistic locking.

        Args:
            name: Template name to delete.
            expected_version: The version the client expects to delete.

        Returns:
            True if the template was deleted or already deleted.

        Raises:
            ConflictError: If the template is missing or version-mismatched.
            CharactersRAGDBError: For database errors.
        """
        template_name = self._normalize_writing_name(name, "Template")
        return self._soft_delete_generic_item("writing_templates", template_name, expected_version, pk_col_name="name")

    def add_writing_theme(
        self,
        name: str,
        *,
        class_name: Optional[str] = None,
        css: Optional[str] = None,
        schema_version: int = 1,
        version_parent_id: Optional[str] = None,
        is_default: bool = False,
        order_index: int = 0,
    ) -> Optional[int]:
        """
        Create a writing theme for the Writing Playground.

        Args:
            name: Theme name.
            class_name: Optional CSS class name for the theme.
            css: Optional raw CSS string.
            schema_version: Theme schema version (must be >= 1).
            version_parent_id: Optional parent theme ID for versioning.
            is_default: Whether the theme should be marked as default.
            order_index: Ordering index for theme lists.

        Returns:
            The theme ID for the newly created record.

        Raises:
            InputError: If inputs are invalid.
            ConflictError: If a theme with the same name already exists.
            CharactersRAGDBError: For database errors.
        """
        if not isinstance(schema_version, int) or schema_version < 1:
            raise InputError("Theme schema_version must be an integer >= 1.")
        theme_name = self._normalize_writing_name(name, "Theme")
        if order_index is None:
            order_index = 0
        item_data = {
            "class_name": self._normalize_nullable_text(class_name),
            "css": css,
            "schema_version": schema_version,
            "version_parent_id": self._normalize_nullable_text(version_parent_id),
            "is_default": bool(is_default),
            "order_index": int(order_index),
        }
        other_fields_map = {
            "class_name": "class_name",
            "css": "css",
            "schema_version": "schema_version",
            "version_parent_id": "version_parent_id",
            "is_default": "is_default",
            "order_index": "order_index",
        }
        return self._add_generic_item("writing_themes", "name", item_data, theme_name, other_fields_map)

    def get_writing_theme_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a writing theme by name.

        Args:
            name: Theme name.

        Returns:
            The theme record, or None if not found.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        theme_name = self._normalize_writing_name(name, "Theme")
        row = self._get_generic_item_by_unique_text("writing_themes", "name", theme_name)
        return dict(row) if row else None

    def list_writing_themes(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List non-deleted writing themes ordered by sort index.

        Args:
            limit: Maximum number of themes to return.
            offset: Number of themes to skip.

        Returns:
            A list of theme records.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        query = (
            "SELECT * FROM writing_themes WHERE deleted = 0 "
            "ORDER BY order_index ASC, name ASC LIMIT ? OFFSET ?"
        )
        try:
            cursor = self.execute_query(query, (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
        except CharactersRAGDBError as exc:
            logger.error(f"Database error listing writing themes: {exc}")
            raise

    def count_writing_themes(self) -> int:
        """
        Return the count of non-deleted writing themes.

        Returns:
            The number of active (non-deleted) themes.

        Raises:
            CharactersRAGDBError: For database errors.
        """
        query = "SELECT COUNT(*) AS cnt FROM writing_themes WHERE deleted = 0"
        try:
            cursor = self.execute_query(query)
            row = cursor.fetchone()
            return int(row["cnt"]) if row else 0
        except CharactersRAGDBError as exc:
            logger.error(f"Database error counting writing themes: {exc}")
            raise

    def update_writing_theme(
        self,
        name: str,
        update_data: Dict[str, Any],
        expected_version: int,
    ) -> bool | None:
        """
        Update a writing theme using optimistic locking.

        Args:
            name: Theme name to update.
            update_data: Fields to update.
            expected_version: The version the client expects to update.

        Returns:
            True if the update succeeds.

        Raises:
            InputError: If update_data is empty.
            ConflictError: If the theme is missing, deleted, or version-mismatched.
            CharactersRAGDBError: For database errors.
        """
        theme_name = self._normalize_writing_name(name, "Theme")
        allowed_fields = [
            "name",
            "class_name",
            "css",
            "schema_version",
            "version_parent_id",
            "is_default",
            "order_index",
        ]
        return self._update_generic_item(
            "writing_themes",
            theme_name,
            update_data,
            expected_version,
            allowed_fields,
            pk_col_name="name",
            unique_col_name_in_data="name",
        )

    def soft_delete_writing_theme(self, name: str, expected_version: int) -> bool | None:
        """
        Soft-delete a writing theme using optimistic locking.

        Args:
            name: Theme name to delete.
            expected_version: The version the client expects to delete.

        Returns:
            True if the theme was deleted or already deleted.

        Raises:
            ConflictError: If the theme is missing or version-mismatched.
            CharactersRAGDBError: For database errors.
        """
        theme_name = self._normalize_writing_name(name, "Theme")
        return self._soft_delete_generic_item("writing_themes", theme_name, expected_version, pk_col_name="name")

    # --- Writing Wordcloud Methods ---
    def _normalize_wordcloud_status(self, status: str) -> str:
        """
        Normalize and validate a wordcloud status value.

        Allowed values: queued, running, ready, failed.
        """
        if not status or not str(status).strip():
            raise InputError("Wordcloud status cannot be empty.")
        normalized = str(status).strip().lower()
        if normalized not in {"queued", "running", "ready", "failed"}:
            raise InputError(f"Invalid wordcloud status: {status}.")
        return normalized

    def add_writing_wordcloud_job(
        self,
        wordcloud_id: str,
        options: Dict[str, Any],
        *,
        input_chars: int,
        status: str = "queued",
    ) -> None:
        """
        Create or reset a writing wordcloud job entry.

        Args:
            wordcloud_id: Deterministic cache key (hash).
            options: Wordcloud options payload.
            input_chars: Character count of input text.
            status: Initial status (queued by default).
        """
        if not wordcloud_id or not str(wordcloud_id).strip():
            raise InputError("Wordcloud ID cannot be empty.")
        normalized_status = self._normalize_wordcloud_status(status)
        options_json = self._serialize_json_payload(options, "Wordcloud options")
        now = self._get_current_utc_timestamp_iso()
        query = (
            "INSERT INTO writing_wordclouds "
            "(id, status, options_json, input_chars, created_at, last_modified, client_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "status=excluded.status, "
            "options_json=excluded.options_json, "
            "input_chars=excluded.input_chars, "
            "words_json=NULL, "
            "meta_json=NULL, "
            "error=NULL, "
            "last_modified=excluded.last_modified, "
            "client_id=excluded.client_id"
        )
        params = (
            str(wordcloud_id),
            normalized_status,
            options_json,
            int(input_chars),
            now,
            now,
            self.client_id,
        )
        try:
            self.execute_query(query, params, commit=True)
        except CharactersRAGDBError:
            raise
        except Exception as exc:
            raise CharactersRAGDBError(f"Failed to create wordcloud job: {exc}") from exc

    def get_writing_wordcloud(self, wordcloud_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a wordcloud job by ID.

        Returns the row with JSON fields deserialized (options, words, meta).
        """
        if not wordcloud_id or not str(wordcloud_id).strip():
            raise InputError("Wordcloud ID cannot be empty.")
        query = "SELECT * FROM writing_wordclouds WHERE id = ?"
        try:
            cursor = self.execute_query(query, (str(wordcloud_id),))
            row = cursor.fetchone()
            if not row:
                return None
            item = self._deserialize_row_fields(row, ["options_json", "words_json", "meta_json"])
            if not item:
                return None
            item["options"] = item.pop("options_json", None)
            item["words"] = item.pop("words_json", None)
            item["meta"] = item.pop("meta_json", None)
            return item
        except CharactersRAGDBError:
            raise
        except Exception as exc:
            raise CharactersRAGDBError(f"Failed to fetch wordcloud job: {exc}") from exc

    def _update_writing_wordcloud_fields(self, wordcloud_id: str, update_data: Dict[str, Any]) -> None:
        if not update_data:
            raise InputError("No data provided for wordcloud update.")
        allowed_fields = {
            "status",
            "options_json",
            "words_json",
            "meta_json",
            "error",
            "input_chars",
        }
        now = self._get_current_utc_timestamp_iso()
        fields_sql: List[str] = []
        params: List[Any] = []
        for key, value in update_data.items():
            if key not in allowed_fields:
                continue
            fields_sql.append(f"{key} = ?")
            params.append(value)
        if not fields_sql:
            raise InputError("No valid fields provided for wordcloud update.")
        fields_sql.extend(["last_modified = ?", "client_id = ?"])
        params.extend([now, self.client_id, str(wordcloud_id)])
        query = f"UPDATE writing_wordclouds SET {', '.join(fields_sql)} WHERE id = ?"
        try:
            cursor = self.execute_query(query, tuple(params), commit=True)
            if getattr(cursor, "rowcount", 0) == 0:
                raise ConflictError("Wordcloud job not found.", entity="writing_wordclouds", entity_id=wordcloud_id)
        except CharactersRAGDBError:
            raise
        except Exception as exc:
            raise CharactersRAGDBError(f"Failed to update wordcloud job: {exc}") from exc

    def set_writing_wordcloud_status(self, wordcloud_id: str, status: str, error: Optional[str] = None) -> None:
        """Update wordcloud job status (and optional error)."""
        normalized_status = self._normalize_wordcloud_status(status)
        update_data: Dict[str, Any] = {"status": normalized_status, "error": error}
        self._update_writing_wordcloud_fields(wordcloud_id, update_data)

    def set_writing_wordcloud_result(
        self,
        wordcloud_id: str,
        *,
        status: str,
        words: Optional[List[Dict[str, Any]]] = None,
        meta: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Persist wordcloud results and status."""
        normalized_status = self._normalize_wordcloud_status(status)
        update_data: Dict[str, Any] = {"status": normalized_status, "error": error}
        if words is not None:
            update_data["words_json"] = self._serialize_json_payload(words, "Wordcloud result")
        if meta is not None:
            update_data["meta_json"] = self._serialize_json_payload(meta, "Wordcloud meta")
        self._update_writing_wordcloud_fields(wordcloud_id, update_data)

    # --- Sync Log Methods ---
    def get_sync_log_entries(self, since_change_id: int = 0, limit: Optional[int] = None,
                             entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves sync log entries newer than a given change_id, optionally filtered by entity type."""
        query_parts = ["SELECT * FROM sync_log WHERE change_id > ?"]
        params_list: List[Any] = [since_change_id]

        if entity_type:
            query_parts.append("AND entity = ?")
            params_list.append(entity_type)

        query_parts.append("ORDER BY change_id ASC")
        if limit is not None:
            query_parts.append("LIMIT ?")
            params_list.append(limit)

        query = " ".join(query_parts)

        try:
            cursor = self.execute_query(query, tuple(params_list))
            results = []
            for row in cursor.fetchall():
                entry = dict(row)
                try:
                    entry['payload'] = json.loads(entry['payload'])
                except json.JSONDecodeError:
                    logger.warning(
                        f"Failed to decode JSON payload for sync_log ID {entry['change_id']}. Payload: {entry['payload'][:100]}")
                    entry['payload'] = None  # Or keep as string, depending on consumer needs
                results.append(entry)
            return results
        except CharactersRAGDBError as e:
            logger.error(f"Error fetching sync log entries: {e}")
            raise

    def get_latest_sync_log_change_id(self) -> int:
        """Returns the highest change_id from the sync_log table."""
        query = "SELECT MAX(change_id) as max_id FROM sync_log"
        try:
            cursor = self.execute_query(query)
            row = cursor.fetchone()
            return row['max_id'] if row and row['max_id'] is not None else 0
        except CharactersRAGDBError as e:
            logger.error(f"Error fetching latest sync log change_id: {e}")
            raise


# --- Transaction Context Manager Class (Helper for `with db.transaction():`) ---
class TransactionContextManager:
    def __init__(self, db_instance: CharactersRAGDB):
        self.db = db_instance
        self.conn: Optional[sqlite3.Connection] = None
        self.is_outermost_transaction = False

    def __enter__(self) -> sqlite3.Connection:
        self.db._ensure_sqlite_backend()
        self.conn = self.db.get_connection()
        if not self.conn.in_transaction:
            # Using deferred transaction by default. Could be "IMMEDIATE" or "EXCLUSIVE" if needed.
            self.conn.execute("BEGIN")
            self.is_outermost_transaction = True
            logger.debug(f"Transaction started (outermost) on thread {threading.get_ident()}.")
        else:
            # SQLite handles nested transactions using savepoints automatically with BEGIN/COMMIT.
            # However, true nested transactions are not supported directly. Python's `in_transaction`
            # might not reflect savepoint depth. We only manage the outermost BEGIN/COMMIT/ROLLBACK.
            logger.debug(
                f"Entering possibly nested transaction block on thread {threading.get_ident()}.")
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db._ensure_sqlite_backend()
        if not self.conn:  # Should not happen if __enter__ succeeded
            logger.error("Transaction context: Connection is None in __exit__.")
            return False # Re-raise exception if any

        if self.is_outermost_transaction:
            if exc_type:
                logger.error(
                    f"Transaction (outermost) failed, rolling back on thread {threading.get_ident()}: {exc_type.__name__} - {exc_val}",
                    exc_info=False) # exc_info=exc_tb if full traceback wanted here
                try:
                    self.conn.rollback()
                    logger.debug(f"Rollback successful on thread {threading.get_ident()}.")
                except sqlite3.Error as rb_err:
                    logger.critical(f"Rollback FAILED on thread {threading.get_ident()}: {rb_err}", exc_info=True)
            else:
                try:
                    self.conn.commit()
                    logger.debug(
                        f"Transaction (outermost) committed successfully on thread {threading.get_ident()}.")
                except sqlite3.Error as commit_err:
                    logger.error(f"Commit FAILED on thread {threading.get_ident()}, attempting rollback: {commit_err}",
                                 exc_info=True)
                    try:
                        self.conn.rollback()
                        logger.debug(f"Rollback after failed commit successful on thread {threading.get_ident()}.")
                    except sqlite3.Error as rb_err_after_commit_fail:
                        logger.critical(
                            f"Rollback after failed commit also FAILED on thread {threading.get_ident()}: {rb_err_after_commit_fail}",
                            exc_info=True)
                    # Re-raise the commit error so the caller knows the transaction failed.
                    # Encapsulate it if it's not already a DB-specific error from our library.
                    if not isinstance(commit_err, CharactersRAGDBError):
                        raise CharactersRAGDBError(f"Commit failed: {commit_err}") from commit_err
                    else:
                        raise commit_err
        elif exc_type:
            # If an exception occurred in a nested block, we don't do anything here.
            # The outermost block will handle the rollback.
            logger.debug(
                f"Exception in nested transaction block on thread {threading.get_ident()}: {exc_type.__name__}. Outermost transaction will handle rollback if this exception propagates.")

        # Return False to re-raise any exceptions that occurred within the `with` block,
        # allowing them to be handled by the caller or to propagate further up.
        # This is standard behavior for context managers.
        return False
#
# End of ChaChaNotes_DB.py
#######################################################################################################################
