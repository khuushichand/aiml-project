# Media_DB_v2.py (Refactored for Multi-DB Instances & Internal Sync Meta)
#########################################
from __future__ import annotations

# Media_DB_v2 Library
# Manages Media_DB_v2 operations for specific instances, handling sync metadata internally.
# Requires a client_id during Database initialization.
# Standalone functions require a Database instance passed as an argument.
#
# Manages SQLite database interactions for media and related metadata.
#
# This library provides a `Database` class to encapsulate operations for a specific
# SQLite database file. It handles connection management (thread-locally),
# schema initialization and versioning, CRUD operations, Full-Text Search (FTS)
# updates, and internal logging of changes for synchronization purposes via a
# `sync_log` table.
#
# Key Features:
# - Instance-based: Each `Database` object connects to a specific DB file.
# - Client ID Tracking: Requires a `client_id` for attributing changes.
# - Internal Sync Logging: Automatically logs creates, updates, deletes, links,
#   and unlinks to the `sync_log` table for external sync processing.
# - Internal FTS Updates: Manages associated FTS5 tables (`media_fts`, `keyword_fts`)
#   within the Python code during relevant operations.
# - Schema Versioning: Checks and applies schema updates upon initialization.
# - Thread-Safety: Uses thread-local storage for database connections.
# - Soft Deletes: Implements soft deletes (`deleted=1`) for most entities,
#   allowing for recovery and synchronization of deletions.
# - Transaction Management: Provides a context manager for atomic operations.
# - Standalone Functions: Offers utility functions that operate on a `Database`
#   instance (e.g., searching, fetching related data, maintenance).
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid  # For UUID generation
from contextlib import contextmanager, nullcontext
from configparser import ConfigParser
from datetime import datetime, timezone, timedelta  # Use timezone-aware UTC
from math import ceil
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional, Union
from tldw_Server_API.app.core.DB_Management.backends.fts_translator import FTSQueryTranslator
#
# Third-Party Libraries (Ensure these are installed if used)
# import gradio as gr # Removed if Gradio interfaces moved out
# import pandas as pd # Removed if Pandas formatting moved out
# import yaml # Keep if Obsidian import uses it
#
########################################################################################################################
#
# Functions:

# --- Logging Setup ---
# Assume logger is configured elsewhere or use basic config:
# Logging: prefer loguru's logger; fall back to stdlib logging
try:
    from loguru import logger
    # Note: alias for loguru logger; not the stdlib 'logging' module.
    # Kept for backward compatibility with existing references to 'logging'.
    logging = logger  # alias used throughout this module
except Exception:  # pragma: no cover - defensive fallback
    import logging as _stdlib_logging
    logger = _stdlib_logging.getLogger("Media_DB_v2")
    logging = logger

import yaml

from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter, log_histogram
from tldw_Server_API.app.core.DB_Management.db_migration import DatabaseMigrator, MigrationError
try:
    # Optional integration for Collections (highlights re-anchoring)
    from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase as _CollectionsDB
except Exception:
    _CollectionsDB = None  # Safe fallback when module unavailable
from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseBackend,
    DatabaseConfig,
    DatabaseError as BackendDatabaseError,
    QueryResult,
)
from tldw_Server_API.app.core.DB_Management.backends.query_utils import (
    convert_sqlite_placeholders_to_postgres,
    normalise_params,
    prepare_backend_many_statement,
    prepare_backend_statement,
)
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.content_backend import get_content_backend, load_content_db_settings
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.DB_Management.scope_context import get_scope

# Use application-wide logging configuration; avoid configuring here.

# --- Custom Exceptions ---
class DatabaseError(Exception):
    """Base exception for database related errors."""
    pass

class SchemaError(DatabaseError):
    """Exception for schema version mismatches or migration failures."""
    pass

class InputError(ValueError):
    """Custom exception for input validation errors."""
    pass

class ConflictError(DatabaseError):
    """Indicates a conflict due to concurrent modification (version mismatch)."""
    def __init__(self, message="Conflict detected: Record modified concurrently.", entity=None, identifier=None):
        super().__init__(message)
        self.entity = entity
        self.identifier = identifier  # Can be id or uuid

    def __str__(self):
        base = super().__str__()
        details = []
        if self.entity:
            details.append(f"Entity: {self.entity}")
        if self.identifier:
            details.append(f"ID: {self.identifier}")
        return f"{base} ({', '.join(details)})" if details else base


class _RowAdapter:
    """Row adapter that supports both key and index access.

    Wraps an underlying dict row and optional description metadata to preserve
    column order for index-based access (row[0]). Behaves like a mapping so
    dict(row) works and existing code expecting dict-like rows continues to work.
    """

    def __init__(self, row_dict: Dict[str, Any], description: Optional[List[tuple]] = None):
        self._data = row_dict
        # Build ordered column list from description when available
        self._cols = [d[0] for d in (description or []) if d and len(d) > 0]

    def __getitem__(self, key):
        if isinstance(key, int):
            # Index-based access: prefer description ordering; fallback to dict order
            if self._cols and 0 <= key < len(self._cols):
                col = self._cols[key]
                return self._data.get(col)
            try:
                return list(self._data.values())[key]
            except Exception as e:
                raise KeyError(key) from e
        # String key access
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __iter__(self):
        # Iterate over keys so dict(row) behaves as expected
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

    def __repr__(self):
        return f"RowAdapter({self._data!r})"


class BackendCursorAdapter:
    """Adapter exposing QueryResult via a sqlite3-like cursor interface."""

    def __init__(self, result: QueryResult):
        self._result = result
        self._index = 0
        self.rowcount = result.rowcount
        self.lastrowid = result.lastrowid
        self.description = result.description

    def _wrap(self, row: Dict[str, Any]):
        return _RowAdapter(row, self.description)

    def fetchall(self):
        return [self._wrap(r) for r in self._result.rows]

    def fetchone(self):
        if self._index >= len(self._result.rows):
            return None
        row = self._result.rows[self._index]
        self._index += 1
        return self._wrap(row)

    def fetchmany(self, size: int | None = None):
        if size is None or size <= 0:
            size = len(self._result.rows) - self._index
        end = min(self._index + size, len(self._result.rows))
        rows = self._result.rows[self._index:end]
        self._index = end
        return [self._wrap(r) for r in rows]

    def __iter__(self):
        return iter(self.fetchall())

    def close(self):
        self._result = QueryResult(rows=[], rowcount=0)
        self.rowcount = 0
        self.lastrowid = None
        self.description = None


# --- Database Class ---
class MediaDatabase:
    """
    Manages SQLite connection and operations for a specific database file,
    handling sync metadata and FTS updates internally via Python code.
    Requires client_id on initialization. Includes schema versioning.
    """
    _CURRENT_SCHEMA_VERSION = 8  # Add scope columns for org/team visibility

    # <<< Schema Definition (Version 1) >>>

    _TABLES_SQL_V1 = """
    PRAGMA foreign_keys = ON;

    -- Schema Version Table --
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY NOT NULL
    );
    -- Initialize version if table is newly created
    INSERT OR IGNORE INTO schema_version (version) VALUES (0);

    -- Media Table --
    CREATE TABLE IF NOT EXISTS Media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        title TEXT NOT NULL,
        type TEXT NOT NULL,
        content TEXT,
        author TEXT,
        ingestion_date DATETIME,
        transcription_model TEXT,
        is_trash BOOLEAN DEFAULT 0 NOT NULL,
        trash_date DATETIME,
        vector_embedding BLOB,
        chunking_status TEXT DEFAULT 'pending' NOT NULL,
        vector_processing INTEGER DEFAULT 0 NOT NULL,
        content_hash TEXT NOT NULL,
        uuid TEXT UNIQUE NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        org_id INTEGER,
        team_id INTEGER,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT
    );

    -- Keywords Table --
    CREATE TABLE IF NOT EXISTS Keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT NOT NULL UNIQUE COLLATE NOCASE,
        uuid TEXT UNIQUE NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT
    );

    -- MediaKeywords Table (Junction Table) --
    CREATE TABLE IF NOT EXISTS MediaKeywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER NOT NULL,
        keyword_id INTEGER NOT NULL,
        UNIQUE (media_id, keyword_id),
        FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE,
        FOREIGN KEY (keyword_id) REFERENCES Keywords(id) ON DELETE CASCADE
    );

    -- Transcripts Table --
    CREATE TABLE IF NOT EXISTS Transcripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER NOT NULL,
        whisper_model TEXT,
        transcription TEXT,
        created_at DATETIME,
        uuid TEXT UNIQUE NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT,
        UNIQUE (media_id, whisper_model),
        FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE
    );

    -- MediaChunks Table --
    CREATE TABLE IF NOT EXISTS MediaChunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER NOT NULL,
        chunk_text TEXT NOT NULL,
        start_index INTEGER,
        end_index INTEGER,
        chunk_id TEXT UNIQUE,
        uuid TEXT UNIQUE NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT,
        FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE
    );

    -- UnvectorizedMediaChunks Table --
    CREATE TABLE IF NOT EXISTS UnvectorizedMediaChunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER NOT NULL,
        chunk_text TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        start_char INTEGER,
        end_char INTEGER,
        chunk_type TEXT,
        creation_date DATETIME,
        last_modified_orig DATETIME,
        is_processed BOOLEAN DEFAULT FALSE NOT NULL,
        metadata TEXT,
        uuid TEXT UNIQUE NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT,
        UNIQUE (media_id, chunk_index, chunk_type),
        FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE
    );

    -- DocumentVersions Table --
    CREATE TABLE IF NOT EXISTS DocumentVersions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER NOT NULL,
        version_number INTEGER NOT NULL,
        prompt TEXT,
        analysis_content TEXT,
        safe_metadata TEXT,
        content TEXT NOT NULL,
        created_at DATETIME,
        uuid TEXT UNIQUE NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT,
        FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE,
        UNIQUE (media_id, version_number)
    );

    -- DocumentVersionIdentifiers Table --
    CREATE TABLE IF NOT EXISTS DocumentVersionIdentifiers (
        dv_id INTEGER PRIMARY KEY,
        doi TEXT,
        pmid TEXT,
        pmcid TEXT,
        arxiv_id TEXT,
        s2_paper_id TEXT,
        FOREIGN KEY (dv_id) REFERENCES DocumentVersions(id) ON DELETE CASCADE
    );

    -- DocumentStructureIndex Table --
    -- Stores structural boundaries for documents (sections, paragraphs, etc.)
    CREATE TABLE IF NOT EXISTS DocumentStructureIndex (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER NOT NULL,
        parent_id INTEGER,
        kind TEXT NOT NULL,           -- e.g., 'section', 'paragraph', 'list', 'table', 'header'
        level INTEGER,                 -- heading depth if applicable
        title TEXT,                    -- section title if applicable
        start_char INTEGER NOT NULL,
        end_char INTEGER NOT NULL,
        order_index INTEGER,           -- ordering within media
        path TEXT,                     -- optional JSON/text path of ancestry titles
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE
    );

    -- Sync Log Table --
    CREATE TABLE IF NOT EXISTS sync_log (
        change_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_uuid TEXT NOT NULL,
        operation TEXT NOT NULL CHECK(operation IN ('create','update','delete', 'link', 'unlink')),
        timestamp DATETIME NOT NULL,
        client_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        org_id INTEGER,
        team_id INTEGER,
        payload TEXT
    );

    -- Chunking Templates Table --
    CREATE TABLE IF NOT EXISTS ChunkingTemplates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        template_json TEXT NOT NULL,
        is_builtin BOOLEAN DEFAULT 0 NOT NULL,
        tags TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        version INTEGER NOT NULL DEFAULT 1,
        org_id INTEGER,
        team_id INTEGER,
        client_id TEXT NOT NULL,
        user_id TEXT,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT
    );
    """

    _INDICES_SQL_V1 = """
    -- Indices (Create after tables exist) --
    CREATE INDEX IF NOT EXISTS idx_media_title ON Media(title);
    CREATE INDEX IF NOT EXISTS idx_media_type ON Media(type);
    CREATE INDEX IF NOT EXISTS idx_media_author ON Media(author);
    CREATE INDEX IF NOT EXISTS idx_media_ingestion_date ON Media(ingestion_date);
    CREATE INDEX IF NOT EXISTS idx_media_chunking_status ON Media(chunking_status);
    CREATE INDEX IF NOT EXISTS idx_media_vector_processing ON Media(vector_processing);
    CREATE INDEX IF NOT EXISTS idx_media_is_trash ON Media(is_trash);
    CREATE INDEX IF NOT EXISTS idx_media_content_hash ON Media(content_hash);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_media_uuid ON Media(uuid);
    CREATE INDEX IF NOT EXISTS idx_media_last_modified ON Media(last_modified);
    CREATE INDEX IF NOT EXISTS idx_media_deleted ON Media(deleted);
    CREATE INDEX IF NOT EXISTS idx_media_prev_version ON Media(prev_version);
    CREATE INDEX IF NOT EXISTS idx_media_merge_parent_uuid ON Media(merge_parent_uuid);
    CREATE INDEX IF NOT EXISTS idx_media_org_id ON Media(org_id);
    CREATE INDEX IF NOT EXISTS idx_media_team_id ON Media(team_id);

    CREATE UNIQUE INDEX IF NOT EXISTS idx_keywords_uuid ON Keywords(uuid);
    CREATE INDEX IF NOT EXISTS idx_keywords_last_modified ON Keywords(last_modified);
    CREATE INDEX IF NOT EXISTS idx_keywords_deleted ON Keywords(deleted);
    CREATE INDEX IF NOT EXISTS idx_keywords_prev_version ON Keywords(prev_version);
    CREATE INDEX IF NOT EXISTS idx_keywords_merge_parent_uuid ON Keywords(merge_parent_uuid);

    CREATE INDEX IF NOT EXISTS idx_mediakeywords_media_id ON MediaKeywords(media_id);
    CREATE INDEX IF NOT EXISTS idx_mediakeywords_keyword_id ON MediaKeywords(keyword_id);

    CREATE INDEX IF NOT EXISTS idx_transcripts_media_id ON Transcripts(media_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_transcripts_uuid ON Transcripts(uuid);
    CREATE INDEX IF NOT EXISTS idx_transcripts_last_modified ON Transcripts(last_modified);
    CREATE INDEX IF NOT EXISTS idx_transcripts_deleted ON Transcripts(deleted);
    CREATE INDEX IF NOT EXISTS idx_transcripts_prev_version ON Transcripts(prev_version);
    CREATE INDEX IF NOT EXISTS idx_transcripts_merge_parent_uuid ON Transcripts(merge_parent_uuid);

    CREATE INDEX IF NOT EXISTS idx_mediachunks_media_id ON MediaChunks(media_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_mediachunks_uuid ON MediaChunks(uuid);
    CREATE INDEX IF NOT EXISTS idx_mediachunks_last_modified ON MediaChunks(last_modified);
    CREATE INDEX IF NOT EXISTS idx_mediachunks_deleted ON MediaChunks(deleted);
    CREATE INDEX IF NOT EXISTS idx_mediachunks_prev_version ON MediaChunks(prev_version);
    CREATE INDEX IF NOT EXISTS idx_mediachunks_merge_parent_uuid ON MediaChunks(merge_parent_uuid);

    CREATE INDEX IF NOT EXISTS idx_unvectorized_media_chunks_media_id ON UnvectorizedMediaChunks(media_id);
    CREATE INDEX IF NOT EXISTS idx_unvectorized_media_chunks_is_processed ON UnvectorizedMediaChunks(is_processed);
    CREATE INDEX IF NOT EXISTS idx_unvectorized_media_chunks_chunk_type ON UnvectorizedMediaChunks(chunk_type);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_unvectorizedmediachunks_uuid ON UnvectorizedMediaChunks(uuid);
    CREATE INDEX IF NOT EXISTS idx_unvectorizedmediachunks_last_modified ON UnvectorizedMediaChunks(last_modified);
    CREATE INDEX IF NOT EXISTS idx_unvectorizedmediachunks_deleted ON UnvectorizedMediaChunks(deleted);
    CREATE INDEX IF NOT EXISTS idx_unvectorizedmediachunks_prev_version ON UnvectorizedMediaChunks(prev_version);
    CREATE INDEX IF NOT EXISTS idx_unvectorizedmediachunks_merge_parent_uuid ON UnvectorizedMediaChunks(merge_parent_uuid);

    CREATE INDEX IF NOT EXISTS idx_document_versions_media_id ON DocumentVersions(media_id);
    CREATE INDEX IF NOT EXISTS idx_document_versions_version_number ON DocumentVersions(version_number);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_documentversions_uuid ON DocumentVersions(uuid);
    CREATE INDEX IF NOT EXISTS idx_documentversions_last_modified ON DocumentVersions(last_modified);
    CREATE INDEX IF NOT EXISTS idx_documentversions_deleted ON DocumentVersions(deleted);
    CREATE INDEX IF NOT EXISTS idx_documentversions_prev_version ON DocumentVersions(prev_version);
    CREATE INDEX IF NOT EXISTS idx_documentversions_merge_parent_uuid ON DocumentVersions(merge_parent_uuid);

    CREATE INDEX IF NOT EXISTS idx_dvi_doi ON DocumentVersionIdentifiers(doi);
    CREATE INDEX IF NOT EXISTS idx_dvi_pmid ON DocumentVersionIdentifiers(pmid);
    CREATE INDEX IF NOT EXISTS idx_dvi_pmcid ON DocumentVersionIdentifiers(pmcid);
    CREATE INDEX IF NOT EXISTS idx_dvi_arxiv ON DocumentVersionIdentifiers(arxiv_id);
    CREATE INDEX IF NOT EXISTS idx_dvi_s2 ON DocumentVersionIdentifiers(s2_paper_id);

    -- DocumentStructureIndex Indices --
    CREATE INDEX IF NOT EXISTS idx_dsi_media_kind ON DocumentStructureIndex(media_id, kind);
    CREATE INDEX IF NOT EXISTS idx_dsi_media_start ON DocumentStructureIndex(media_id, start_char);
    CREATE INDEX IF NOT EXISTS idx_dsi_media_parent ON DocumentStructureIndex(parent_id);

    CREATE INDEX IF NOT EXISTS idx_sync_log_ts ON sync_log(timestamp);
    CREATE INDEX IF NOT EXISTS idx_sync_log_entity_uuid ON sync_log(entity_uuid);
    CREATE INDEX IF NOT EXISTS idx_sync_log_client_id ON sync_log(client_id);
    CREATE INDEX IF NOT EXISTS idx_sync_log_org_id ON sync_log(org_id);
    CREATE INDEX IF NOT EXISTS idx_sync_log_team_id ON sync_log(team_id);

    -- Chunking Templates Indices --
    CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_template_name
        ON ChunkingTemplates(name) WHERE deleted = 0;
    CREATE INDEX IF NOT EXISTS idx_template_is_builtin ON ChunkingTemplates(is_builtin);
    CREATE INDEX IF NOT EXISTS idx_template_deleted ON ChunkingTemplates(deleted);
    CREATE INDEX IF NOT EXISTS idx_template_tags ON ChunkingTemplates(tags);
    """

    _TRIGGERS_SQL_V1 = """
    -- Validation Triggers (Create after tables and indices) --
    DROP TRIGGER IF EXISTS media_validate_sync_update;
    CREATE TRIGGER media_validate_sync_update BEFORE UPDATE ON Media
    BEGIN
        SELECT RAISE(ABORT, 'Sync Error (Media): Version must increment by exactly 1.')
        WHERE NEW.version IS NOT OLD.version + 1;
        SELECT RAISE(ABORT, 'Sync Error (Media): Client ID cannot be NULL or empty.')
        WHERE NEW.client_id IS NULL OR NEW.client_id = '';
        -- Add more checks if needed (e.g., UUID modification)
        SELECT RAISE(ABORT, 'Sync Error (Media): UUID cannot be changed.')
        WHERE NEW.uuid IS NOT OLD.uuid;
    END;

    DROP TRIGGER IF EXISTS keywords_validate_sync_update;
    CREATE TRIGGER keywords_validate_sync_update BEFORE UPDATE ON Keywords
    BEGIN
        SELECT RAISE(ABORT, 'Sync Error (Keywords): Version must increment by exactly 1.')
        WHERE NEW.version IS NOT OLD.version + 1;
        SELECT RAISE(ABORT, 'Sync Error (Keywords): Client ID cannot be NULL or empty.')
        WHERE NEW.client_id IS NULL OR NEW.client_id = '';
        SELECT RAISE(ABORT, 'Sync Error (Keywords): UUID cannot be changed.')
        WHERE NEW.uuid IS NOT OLD.uuid;
    END;

    DROP TRIGGER IF EXISTS transcripts_validate_sync_update;
    CREATE TRIGGER transcripts_validate_sync_update BEFORE UPDATE ON Transcripts
    BEGIN
        SELECT RAISE(ABORT, 'Sync Error (Transcripts): Version must increment by exactly 1.')
        WHERE NEW.version IS NOT OLD.version + 1;
        SELECT RAISE(ABORT, 'Sync Error (Transcripts): Client ID cannot be NULL or empty.')
        WHERE NEW.client_id IS NULL OR NEW.client_id = '';
        SELECT RAISE(ABORT, 'Sync Error (Transcripts): UUID cannot be changed.')
        WHERE NEW.uuid IS NOT OLD.uuid;
    END;

    DROP TRIGGER IF EXISTS mediachunks_validate_sync_update;
    CREATE TRIGGER mediachunks_validate_sync_update BEFORE UPDATE ON MediaChunks
    BEGIN
        SELECT RAISE(ABORT, 'Sync Error (MediaChunks): Version must increment by exactly 1.')
        WHERE NEW.version IS NOT OLD.version + 1;
        SELECT RAISE(ABORT, 'Sync Error (MediaChunks): Client ID cannot be NULL or empty.')
        WHERE NEW.client_id IS NULL OR NEW.client_id = '';
        SELECT RAISE(ABORT, 'Sync Error (MediaChunks): UUID cannot be changed.')
        WHERE NEW.uuid IS NOT OLD.uuid;
    END;

    DROP TRIGGER IF EXISTS unvectorizedmediachunks_validate_sync_update;
    CREATE TRIGGER unvectorizedmediachunks_validate_sync_update BEFORE UPDATE ON UnvectorizedMediaChunks
    BEGIN
        SELECT RAISE(ABORT, 'Sync Error (UnvectorizedMediaChunks): Version must increment by exactly 1.')
        WHERE NEW.version IS NOT OLD.version + 1;
        SELECT RAISE(ABORT, 'Sync Error (UnvectorizedMediaChunks): Client ID cannot be NULL or empty.')
        WHERE NEW.client_id IS NULL OR NEW.client_id = '';
        SELECT RAISE(ABORT, 'Sync Error (UnvectorizedMediaChunks): UUID cannot be changed.')
        WHERE NEW.uuid IS NOT OLD.uuid;
    END;

    DROP TRIGGER IF EXISTS documentversions_validate_sync_update;
    CREATE TRIGGER documentversions_validate_sync_update BEFORE UPDATE ON DocumentVersions
    BEGIN
        SELECT RAISE(ABORT, 'Sync Error (DocumentVersions): Version must increment by exactly 1.')
        WHERE NEW.version IS NOT OLD.version + 1;
        SELECT RAISE(ABORT, 'Sync Error (DocumentVersions): Client ID cannot be NULL or empty.')
        WHERE NEW.client_id IS NULL OR NEW.client_id = '';
        SELECT RAISE(ABORT, 'Sync Error (DocumentVersions): UUID cannot be changed.')
        WHERE NEW.uuid IS NOT OLD.uuid;
    END;
    """

    _FTS_TABLES_SQL = """
    -- FTS Tables (Executed Separately) --
    CREATE VIRTUAL TABLE IF NOT EXISTS media_fts USING fts5(
        title,
        content,
        content='Media',    -- Keep reference to source table
        content_rowid='id' -- Link to Media.id
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS keyword_fts USING fts5(
        keyword,
        content='Keywords',    -- Keep reference to source table
        content_rowid='id'  -- Link to Keywords.id
    );

    -- Optional FTS for Claims (content-backed; Stage 1 has no triggers)
    CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
        claim_text,
        content='Claims',     -- Keep reference to source table
        content_rowid='id'    -- Link to Claims.id
    );
    """

    _CLAIMS_FTS_TRIGGERS_SQL = """
    -- Keep claims_fts in sync with Claims via triggers
    CREATE TRIGGER IF NOT EXISTS claims_ai AFTER INSERT ON Claims BEGIN
        -- Only index non-deleted claims
        INSERT INTO claims_fts(rowid, claim_text)
        SELECT NEW.id, NEW.claim_text WHERE NEW.deleted = 0;
    END;

    CREATE TRIGGER IF NOT EXISTS claims_au AFTER UPDATE ON Claims BEGIN
        -- Remove any existing row
        DELETE FROM claims_fts WHERE rowid = NEW.id;
        -- Re-insert when not deleted
        INSERT INTO claims_fts(rowid, claim_text)
        SELECT NEW.id, NEW.claim_text WHERE NEW.deleted = 0;
    END;

    CREATE TRIGGER IF NOT EXISTS claims_ad AFTER DELETE ON Claims BEGIN
        DELETE FROM claims_fts WHERE rowid = OLD.id;
    END;
    """

    _CLAIMS_TABLE_SQL = """
    -- Claims table for ingestion-time factual statements tied to media chunks
    CREATE TABLE IF NOT EXISTS Claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        span_start INTEGER,
        span_end INTEGER,
        claim_text TEXT NOT NULL,
        confidence REAL,
        extractor TEXT NOT NULL,
        extractor_version TEXT NOT NULL,
        chunk_hash TEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        uuid TEXT UNIQUE NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT,
        FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_claims_media_id ON Claims(media_id);
    CREATE INDEX IF NOT EXISTS idx_claims_media_chunk ON Claims(media_id, chunk_index);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_claims_uuid ON Claims(uuid);
    CREATE INDEX IF NOT EXISTS idx_claims_deleted ON Claims(deleted);
    """

    def __init__(
        self,
        db_path: Union[str, Path],
        client_id: str,
        *,
        backend: DatabaseBackend | None = None,
        config: ConfigParser | None = None,
        default_org_id: Optional[int] = None,
        default_team_id: Optional[int] = None,
    ):
        """
        Initializes the Database instance, sets up the connection pool (via threading.local),
        and ensures the database schema is correctly initialized or migrated.

        Args:
            db_path (Union[str, Path]): The path to the database file or ':memory:'.
            client_id (str): A unique identifier for the client using this database instance.
            backend (Optional[DatabaseBackend]): Pre-instantiated backend (for tests or DI).
            config (Optional[ConfigParser]): Config parser used to resolve backend when one
                is not explicitly provided. Falls back to comprehensive config loader.

        Raises:
            ValueError: If client_id is empty or None.
            DatabaseError: If database initialization or schema setup fails.
        """
        # Validate input path early to avoid implicit fallbacks
        if isinstance(db_path, str):
            if db_path.strip() == "":
                raise ValueError("db_path cannot be an empty string; pass an explicit path or ':memory:'")

        # Determine if it's an in-memory DB and resolve the path
        if isinstance(db_path, Path):
            self.is_memory_db = False
            self.db_path = db_path.resolve()
        else:  # Treat as string
            self.is_memory_db = (db_path == ':memory:')
            if not self.is_memory_db:
                self.db_path = Path(db_path).resolve()
            else:
                # Even for memory, Path object can be useful internally, though str is ':memory:'
                self.db_path = Path(":memory:")  # Represent in-memory path consistently

        # Store the path as a string for convenience/logging
        self.db_path_str = str(self.db_path) if not self.is_memory_db else ':memory:'

        # Validate client_id
        if not client_id:
            raise ValueError("Client ID cannot be empty or None.")
        self.client_id = client_id

        # Ensure parent directory exists if it's a file-based DB
        if not self.is_memory_db:
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                # Catch potential errors creating the directory (e.g., permissions)
                raise DatabaseError(f"Failed to create database directory {self.db_path.parent}: {e}") from e

        logging.info(f"Initializing Database object for path: {self.db_path_str} [Client ID: {self.client_id}]")

        # Resolve database backend (defaults to sqlite when none configured)
        self.backend = self._resolve_backend(backend=backend, config=config)
        self.backend_type = self.backend.backend_type
        self.default_org_id = default_org_id
        self.default_team_id = default_team_id

        # Transaction-scoped connection and depth (no per-thread caching)
        self._txn_conn = None
        self._tx_depth = 0
        # Persistent non-transaction connection (PostgreSQL) to mimic previous per-thread behavior
        self._persistent_conn = None
        # For SQLite in-memory databases, maintain a persistent connection so state persists
        if self.backend_type == BackendType.SQLITE and self.is_memory_db:
            # Use autocommit for consistency with pooled connections
            pc = sqlite3.connect(self.db_path_str, check_same_thread=False, isolation_level=None)
            try:
                pc.row_factory = sqlite3.Row
                pc.execute("PRAGMA foreign_keys = ON")
                pc.execute("PRAGMA busy_timeout = 10000")
            except sqlite3.Error:
                pass
            self._persistent_conn = pc
        # Add lock for media insertion to prevent race conditions in concurrent uploads
        self._media_insert_lock = threading.Lock()
        self._scope_cache: Tuple[Optional[int], Optional[int]] = (self.default_org_id, self.default_team_id)

        # Flag to track successful initialization before logging completion
        initialization_successful = False
        try:
            # --- Core Initialization Logic ---
            # This establishes the first connection for the current thread
            # and applies/verifies the schema.
            self._initialize_schema()
            initialization_successful = True  # Mark as successful if no exception occurred
        except (DatabaseError, SchemaError, sqlite3.Error, BackendDatabaseError) as e:
            # Catch specific DB/Schema errors and general SQLite errors during init
            logging.critical(f"FATAL: DB Initialization failed for {self.db_path_str}: {e}", exc_info=True)
            # Attempt to clean up the connection before raising
            self.close_connection()
            # Re-raise as a DatabaseError to signal catastrophic failure
            raise DatabaseError(f"Database initialization failed: {e}") from e
        except Exception as e:
            # Catch any other unexpected errors during initialization
            logging.critical(f"FATAL: Unexpected error during DB Initialization for {self.db_path_str}: {e}", exc_info=True)
            # Attempt cleanup
            self.close_connection()
            # Re-raise as a DatabaseError
            raise DatabaseError(f"Unexpected database initialization error: {e}") from e
        finally:
            # Log completion status based on the flag
            if initialization_successful:
                logging.debug(f"Database initialization completed successfully for {self.db_path_str}")
            else:
                # This path indicates an exception was caught and raised above.
                # Logging here provides context that the __init__ block finished, albeit with failure.
                logging.error(f"Database initialization block finished for {self.db_path_str}, but failed.")

    def _resolve_scope_ids(self) -> Tuple[Optional[int], Optional[int]]:
        """Determine effective org/team IDs for the current execution context."""
        try:
            scope = get_scope()
        except Exception:
            scope = None

        org_id = self.default_org_id
        team_id = self.default_team_id

        if scope:
            scope_org = scope.effective_org_id
            scope_team = scope.effective_team_id
            if scope_org is not None:
                org_id = scope_org
            if scope_team is not None:
                team_id = scope_team

        self._scope_cache = (org_id, team_id)
        return org_id, team_id

    # --- Backend Resolution Helpers ---
    def _resolve_backend(
        self,
        *,
        backend: DatabaseBackend | None,
        config: ConfigParser | None,
    ) -> DatabaseBackend:
        # 1) Explicit backend passed in takes full precedence
        if backend is not None:
            return backend

        parser: ConfigParser | None = config
        if parser is None:
            try:
                parser = load_comprehensive_config()
            except Exception:
                parser = None

        backend_mode_env = (os.getenv("CONTENT_DB_MODE") or os.getenv("TLDW_CONTENT_DB_BACKEND") or "").strip().lower()
        forced_postgres = backend_mode_env in {"postgres", "postgresql"}

        if not forced_postgres and parser is not None:
            try:
                content_settings = load_content_db_settings(parser)
                forced_postgres = content_settings.backend_type == BackendType.POSTGRESQL
            except Exception:
                pass

        if forced_postgres:
            if parser is None:
                raise DatabaseError("PostgreSQL content backend requested but configuration could not be loaded")
            resolved_backend = get_content_backend(parser)
            if resolved_backend is None or resolved_backend.backend_type != BackendType.POSTGRESQL:
                raise DatabaseError("PostgreSQL content backend requested but could not be initialized")
            return resolved_backend

        # 2) If a concrete db_path (including ':memory:') was provided at construction,
        #    prefer a SQLite backend bound to that path. This ensures test fixtures and
        #    callers using custom paths do not accidentally share the global content DB
        #    from configuration.
        provided_path = self.db_path_str
        if provided_path:
            fallback_config = DatabaseConfig(
                backend_type=BackendType.SQLITE,
                sqlite_path=provided_path,
            )
            return DatabaseBackendFactory.create_backend(fallback_config)

        resolved = get_content_backend(parser) if parser else None
        if resolved is not None:
            return resolved

        # 4) Fallback to a local SQLite backend anchored to project root
        try:
            from tldw_Server_API.app.core.Utils.Utils import get_project_root as _gpr
            _default_sqlite_path = str((Path(_gpr()) / "Databases" / "Media_DB_v2.db").resolve())
        except Exception:
            _default_sqlite_path = str((Path(__file__).resolve().parents[5] / "Databases" / "Media_DB_v2.db").resolve())
        # Emit a warning so callers can fix missing explicit paths
        try:
            logging.warning(
                "MediaDatabase backend falling back to default SQLite path; pass an explicit db_path or configure content backend. path=%s",
                _default_sqlite_path,
            )
        except Exception:
            pass
        default_config = DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=_default_sqlite_path,
        )
        return DatabaseBackendFactory.create_backend(default_config)

    # --- Backend Statement Preparation Helpers ---
    def _prepare_backend_statement(
        self,
        query: str,
        params: Optional[Union[Tuple, List, Dict]] = None,
    ) -> tuple[str, Optional[Union[Tuple, Dict]]]:
        return prepare_backend_statement(
            self.backend_type,
            query,
            params,
            apply_default_transform=True,
            ensure_returning=False,
        )

    def _prepare_backend_many_statement(
        self,
        query: str,
        params_list: List[Union[Tuple, List, Dict]],
    ) -> tuple[str, List[Union[Tuple, Dict]]]:
        converted_query, prepared_params = prepare_backend_many_statement(
            self.backend_type,
            query,
            params_list,
            apply_default_transform=True,
            ensure_returning=False,
        )
        return converted_query, prepared_params

    def _keyword_order_expression(self, column: str) -> str:
        """Return keyword ORDER BY expression appropriate for the active backend."""

        if self.backend_type == BackendType.SQLITE:
            return f"{column} COLLATE NOCASE"
        return f"LOWER({column}), {column}"

    def _append_case_insensitive_like(
        self,
        clauses: List[str],
        params: List[Any],
        column: str,
        pattern: str,
    ) -> None:
        """Append backend-aware case-insensitive LIKE predicate and parameter."""

        if self.backend_type == BackendType.POSTGRESQL:
            clauses.append(f"{column} ILIKE ?")
        else:
            clauses.append(f"{column} LIKE ? COLLATE NOCASE")
        params.append(pattern)

    def _normalise_params(
        self,
        params: Optional[Any],
    ) -> Optional[Union[Tuple, Dict]]:
        return normalise_params(params)

    def _convert_sqlite_placeholders_to_postgres(self, query: str) -> str:
        return convert_sqlite_placeholders_to_postgres(query)

    def _execute_with_connection(
        self,
        conn,
        query: str,
        params: Optional[Union[Tuple, List, Dict]] = None,
    ):
        prepared_query, prepared_params = self._prepare_backend_statement(query, params)

        if self.backend_type == BackendType.SQLITE:
            cursor = conn.cursor()
            cursor.execute(prepared_query, prepared_params or ())
            return cursor

        try:
            result = self.backend.execute(
                prepared_query,
                prepared_params,
                connection=conn,
            )
            return BackendCursorAdapter(result)
        except BackendDatabaseError as exc:
            logging.error(
                "Backend execute failed: %s... Error: %s",
                prepared_query[:200],
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Backend execute failed: {exc}") from exc

    def _executemany_with_connection(
        self,
        conn,
        query: str,
        params_list: List[Union[Tuple, List, Dict]],
    ):
        prepared_query, prepared_params_list = self._prepare_backend_many_statement(query, params_list)

        if self.backend_type == BackendType.SQLITE:
            cursor = conn.cursor()
            cursor.executemany(prepared_query, prepared_params_list)
            return cursor

        try:
            result = self.backend.execute_many(
                prepared_query,
                prepared_params_list,
                connection=conn,
            )
            return BackendCursorAdapter(result)
        except BackendDatabaseError as exc:
            logging.error(
                "Backend execute_many failed: %s... Error: %s",
                prepared_query[:200],
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Backend execute_many failed: {exc}") from exc

    def _fetchone_with_connection(
        self,
        conn,
        query: str,
        params: Optional[Union[Tuple, List, Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        cursor = self._execute_with_connection(conn, query, params)
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def _fetchall_with_connection(
        self,
        conn,
        query: str,
        params: Optional[Union[Tuple, List, Dict]] = None,
    ) -> List[Dict[str, Any]]:
        cursor = self._execute_with_connection(conn, query, params)
        rows = cursor.fetchall() or []
        return [dict(r) for r in rows]

    # --- Connection Management ---
    def get_connection(self):
        """Compatibility shim to return a usable connection.

        - Inside transactions returns the transaction-scoped connection.
        - For SQLite, returns a pooled thread-local connection.
        - For PostgreSQL, returns a persistent connection grabbed from the pool
          on first use (released by close_connection()).
        """
        if self._txn_conn is not None:
            return self._txn_conn
        if self.backend_type == BackendType.SQLITE:
            if self.is_memory_db and self._persistent_conn is not None:
                return self._persistent_conn
            return self.backend.get_pool().get_connection()
        # PostgreSQL: reuse a single persistent connection outside transactions
        if self._persistent_conn is None:
            self._persistent_conn = self.backend.get_pool().get_connection()
        return self._persistent_conn

    def close_connection(self):
        """Release persistent non-transaction connection if present."""
        if self._txn_conn is not None:
            return
        try:
            if self._persistent_conn is not None:
                self.backend.get_pool().return_connection(self._persistent_conn)
        finally:
            self._persistent_conn = None

    def _ensure_sqlite_backend(self) -> None:
        if self.backend_type != BackendType.SQLITE:
            return

    # --- Query Execution (Unchanged, catches IntegrityError from validation triggers) ---
    def execute_query(
        self,
        query: str,
        params: Optional[Union[tuple, list, Dict]] = None,
        *,
        commit: bool = False,
        connection: Optional[Any] = None,
    ):
        """
         Executes a single SQL query.

         Args:
             query (str): The SQL query string.
             params (Optional[tuple]): Parameters to substitute into the query.
             commit (bool): If True, commit the transaction after execution.
                            Defaults to False. Usually managed by `transaction()`.

         Returns:
             sqlite3.Cursor: The cursor object after execution.

         Raises:
             DatabaseError: For general SQLite errors or integrity violations
                            not related to sync validation.
             sqlite3.IntegrityError: Specifically re-raised if a sync validation
                                     trigger (defined in schema) fails.
         """
        prepared_query, prepared_params = self._prepare_backend_statement(query, params)

        eff_conn = connection or self._txn_conn

        if self.backend_type == BackendType.SQLITE:
            try:
                if eff_conn is None and not self.is_memory_db:
                    eph = sqlite3.connect(self.db_path_str, check_same_thread=False)
                    eph.row_factory = sqlite3.Row
                    cur = eph.cursor()
                    cur.execute(prepared_query, prepared_params or ())
                    upper = prepared_query.strip().upper()
                    is_select = upper.startswith("SELECT")
                    has_returning = " RETURNING " in upper
                    # Auto-commit DML/DDL when using ephemeral connection
                    if commit or (not is_select and not has_returning):
                        try:
                            eph.commit()
                        except Exception:
                            pass
                    rows = []
                    if is_select or has_returning:
                        rows = [dict(r) for r in cur.fetchall()]
                    result = QueryResult(rows=rows, rowcount=cur.rowcount, lastrowid=cur.lastrowid, description=cur.description)
                    cur.close()
                    eph.close()
                    return BackendCursorAdapter(result)
                else:
                    # Use transaction/persistent connection (required for :memory: databases)
                    conn_use = eff_conn or self.get_connection()
                    cur = conn_use.cursor()
                    cur.execute(prepared_query, prepared_params or ())
                    if commit and conn_use:
                        conn_use.commit()
                    upper = prepared_query.strip().upper()
                    is_select = upper.startswith("SELECT")
                    has_returning = " RETURNING " in upper
                    rows = []
                    if is_select or has_returning:
                        rows = [dict(r) for r in cur.fetchall()]
                    result = QueryResult(rows=rows, rowcount=cur.rowcount, lastrowid=cur.lastrowid, description=cur.description)
                    return BackendCursorAdapter(result)
            except sqlite3.IntegrityError as e:
                msg = str(e).lower()
                if "sync error" in msg:
                    logging.error(f"Sync Validation Failed: {e}")
                    raise e
                logging.error("Integrity error executing query: %s", e, exc_info=True)
                raise DatabaseError(f"Integrity constraint violation: {e}") from e
            except sqlite3.Error as e:
                logging.error("SQLite query failed: %s", e, exc_info=True)
                raise DatabaseError(f"Query execution failed: {e}") from e

        try:
            if eff_conn is None:
                raw = self.backend.get_pool().get_connection()
                try:
                    result = self.backend.execute(prepared_query, prepared_params, connection=raw)
                    if commit:
                        try:
                            raw.commit()
                        except Exception as exc:
                            raise DatabaseError(f"Backend commit failed: {exc}") from exc
                finally:
                    try:
                        self.backend.get_pool().return_connection(raw)
                    except Exception:
                        pass
            else:
                result = self.backend.execute(prepared_query, prepared_params, connection=eff_conn)
                if commit:
                    try:
                        eff_conn.commit()
                    except Exception as exc:
                        raise DatabaseError(f"Backend commit failed: {exc}") from exc
            return BackendCursorAdapter(result)
        except BackendDatabaseError as exc:
            logging.error("Backend query failed: %s", exc, exc_info=True)
            raise DatabaseError(f"Backend query execution failed: {exc}") from exc

    def execute_many(
        self,
        query: str,
        params_list: List[Union[tuple, list, Dict]],
        *,
        commit: bool = False,
        connection: Optional[Any] = None,
    ) -> Optional[object]:
        """
        Executes a SQL query for multiple sets of parameters.

        Args:
            query (str): The SQL query string (e.g., INSERT INTO ... VALUES (?,?)).
            params_list (List[tuple]): A list of tuples, each tuple containing
                                       parameters for one execution.
            commit (bool): If True, commit the transaction after execution.
                           Defaults to False. Usually managed by `transaction()`.

        Returns:
            Optional[sqlite3.Cursor]: The cursor object after execution, or None if
                                     `params_list` was empty.

        Raises:
            TypeError: If `params_list` is not a list or contains invalid data types.
            DatabaseError: For general SQLite errors or integrity violations.
        """
        if not isinstance(params_list, list):
            raise TypeError("params_list must be a list of parameter iterables for execute_many().")
        if not params_list:
            logging.debug("execute_many received empty params_list; nothing to execute.")
            return None

        prepared_query, prepared_params_list = self._prepare_backend_many_statement(query, params_list)

        eff_conn = connection or self._txn_conn

        if self.backend_type == BackendType.SQLITE:
            try:
                if eff_conn is None and not self.is_memory_db:
                    eph = sqlite3.connect(self.db_path_str, check_same_thread=False)
                    eph.row_factory = sqlite3.Row
                    cur = eph.cursor()
                    cur.executemany(prepared_query, prepared_params_list)
                    # executemany implies DML; commit when using ephemeral connection
                    try:
                        eph.commit()
                    except Exception:
                        pass
                    result = QueryResult(rows=[], rowcount=cur.rowcount, lastrowid=cur.lastrowid, description=cur.description)
                    cur.close()
                    eph.close()
                    return BackendCursorAdapter(result)
                else:
                    conn_use = eff_conn or self.get_connection()
                    cur = conn_use.cursor()
                    cur.executemany(prepared_query, prepared_params_list)
                    if commit and conn_use:
                        conn_use.commit()
                    result = QueryResult(rows=[], rowcount=cur.rowcount, lastrowid=cur.lastrowid, description=cur.description)
                    return BackendCursorAdapter(result)
            except sqlite3.IntegrityError as e:
                logging.error("Integrity error during execute_many: %s", e, exc_info=True)
                raise DatabaseError(f"Integrity constraint violation during batch: {e}") from e
            except sqlite3.Error as e:
                logging.error("SQLite execute_many failed: %s", e, exc_info=True)
                raise DatabaseError(f"Execute Many failed: {e}") from e
            except TypeError as te:
                logging.error("TypeError during execute_many: %s", te, exc_info=True)
                raise TypeError(f"Parameter list format error: {te}") from te

        try:
            if eff_conn is None:
                raw = self.backend.get_pool().get_connection()
                try:
                    result = self.backend.execute_many(prepared_query, prepared_params_list, connection=raw)
                    if commit:
                        try:
                            raw.commit()
                        except Exception as exc:
                            raise DatabaseError(f"Backend batch commit failed: {exc}") from exc
                finally:
                    try:
                        self.backend.get_pool().return_connection(raw)
                    except Exception:
                        pass
            else:
                result = self.backend.execute_many(prepared_query, prepared_params_list, connection=eff_conn)
                if commit:
                    try:
                        eff_conn.commit()
                    except Exception as exc:
                        raise DatabaseError(f"Backend batch commit failed: {exc}") from exc
            return BackendCursorAdapter(result)
        except BackendDatabaseError as exc:
            logging.error("Backend execute_many failed: %s", exc, exc_info=True)
            raise DatabaseError(f"Backend execute_many failed: {exc}") from exc

    # -------------------------
    # Chunk-level FTS helpers
    # -------------------------
    def ensure_chunk_fts(self) -> None:
        """Ensure the chunk-level FTS virtual table exists (SQLite only).

        Uses content=UnvectorizedMediaChunks so rowid aligns with base table `id`.
        Safe to call repeatedly. No-op for non-SQLite backends.
        """
        try:
            if self.backend_type != BackendType.SQLITE:
                return
            ddl = (
                "CREATE VIRTUAL TABLE IF NOT EXISTS unvectorized_chunks_fts "
                "USING fts5(\n"
                "  chunk_text,\n"
                "  content='UnvectorizedMediaChunks',\n"
                "  content_rowid='id'\n"
                ")"
            )
            self.execute_query(ddl, commit=True)
        except Exception as e:
            logging.debug(f"ensure_chunk_fts skipped or failed: {e}")

    def maybe_rebuild_chunk_fts_if_empty(self) -> None:
        """Rebuild chunk FTS index if it exists and is currently empty.

        This primes the FTS table after initial creation or bulk inserts
        without requiring triggers. No-op for non-SQLite backends.
        """
        try:
            if self.backend_type != BackendType.SQLITE:
                return
            # Check existence and emptiness
            try:
                cur = self.execute_query("SELECT count(*) AS c FROM unvectorized_chunks_fts")
                row = cur.fetchone()
                count_val = (row[0] if row and not isinstance(row, dict) else (row.get('c') if row else 0)) or 0
            except Exception:
                # Table missing - try to create and continue
                self.ensure_chunk_fts()
                cur = self.execute_query("SELECT count(*) AS c FROM unvectorized_chunks_fts")
                row = cur.fetchone()
                count_val = (row[0] if row and not isinstance(row, dict) else (row.get('c') if row else 0)) or 0

            if int(count_val) == 0:
                # Rebuild from content table
                self.execute_query(
                    "INSERT INTO unvectorized_chunks_fts(unvectorized_chunks_fts) VALUES('rebuild')",
                    commit=True,
                )
        except Exception as e:
            logging.debug(f"maybe_rebuild_chunk_fts_if_empty skipped or failed: {e}")

    # --- Transaction Context (Unchanged) ---
    @contextmanager
    def transaction(self):
        """
        Provides a context manager for database transactions.

        Ensures that a block of operations is executed atomically. Commits
        on successful exit, rolls back on any exception. Handles nested
        transactions gracefully (only outermost commit/rollback matters).

        Yields:
            sqlite3.Connection: The current thread's database connection.

        Raises:
            Exception: Re-raises any exception that occurs within the block
                       after attempting a rollback.
        """
        # no-op: connection will be set by backend/transaction logic below

        if self.backend_type == BackendType.SQLITE:
            # Nest-aware transaction handling for SQLite
            outermost = self._txn_conn is None
            if outermost:
                # Dedicated connection for this transaction
                conn = self._persistent_conn or self.backend.connect()
                try:
                    conn.row_factory = sqlite3.Row
                except Exception:
                    pass
                try:
                    conn.execute("PRAGMA foreign_keys = ON")
                    conn.execute("PRAGMA busy_timeout = 10000")
                except sqlite3.Error:
                    pass
            else:
                conn = self._txn_conn

            self._tx_depth += 1
            try:
                if outermost:
                    conn.execute("BEGIN")
                    self._txn_conn = conn
                    logging.debug("Started SQLite transaction.")
                yield conn
                if outermost:
                    conn.commit()
                    logging.debug("Committed SQLite transaction.")
            except Exception as e:
                logging.error("SQLite transaction failed, rolling back: %s", e)
                if outermost:
                    try:
                        conn.rollback()
                    except sqlite3.Error:
                        pass
                raise
            finally:
                self._tx_depth -= 1
                if outermost:
                    self._txn_conn = None
                    if self._persistent_conn is None:
                        try:
                            conn.close()
                        except Exception:
                            pass
            return

        # PostgreSQL and others: reuse a single connection for nested transactions
        manages_backend_conn = self._txn_conn is None
        if manages_backend_conn:
            conn = self.backend.get_pool().get_connection()
        else:
            conn = self._txn_conn

        manages_backend_tx = self._tx_depth == 0
        self._tx_depth += 1
        ctx = self.backend.transaction(conn) if manages_backend_tx else nullcontext(conn)
        try:
            with ctx as inner_conn:
                self._txn_conn = inner_conn
                yield inner_conn
        finally:
            self._tx_depth -= 1
            if self._tx_depth == 0:
                self._txn_conn = None
            if manages_backend_conn:
                try:
                    self.backend.get_pool().return_connection(conn)
                except Exception:
                    pass

    # --- Schema Initialization and Migration ---
    def _get_db_version(self, conn: sqlite3.Connection) -> int:
        """Internal helper to get the current schema version."""
        try:
            cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
            result = cursor.fetchone()
            return result['version'] if result else 0
        except sqlite3.Error as e:
            if "no such table: schema_version" in str(e):
                return 0  # Table doesn't exist yet
            else:
                raise DatabaseError(f"Could not determine database schema version: {e}") from e

    @property
    def _SCHEMA_UPDATE_VERSION_SQL_V1(self):
        return (
            "DELETE FROM schema_version WHERE version <> 0;\n"
            f"UPDATE schema_version SET version = {self._CURRENT_SCHEMA_VERSION} WHERE version = 0;"
        )

    def _apply_schema_v1_sqlite(self, conn: sqlite3.Connection):
        """Applies the full Version 1 schema, ensuring version update is part of the main script."""
        logging.info(f"Applying initial schema (Version 1) to DB: {self.db_path_str}...")
        try:
            # --- Combine Core Schema + Version Update for one executescript call ---
            # This ensures the version update is part of the same atomic operation block
            # executed by executescript within the transaction.
            core_schema_script_with_version_update = f"""
                {self._TABLES_SQL_V1}
                {self._INDICES_SQL_V1}
                {self._TRIGGERS_SQL_V1}
                {self._SCHEMA_UPDATE_VERSION_SQL_V1}
            """  # Note the added UPDATE statement

            # --- Transaction for Core Schema + Version Update ---
            with self.transaction():  # Use the transaction context manager
                logging.debug("[Schema V1] Applying Core Schema + Version Update...")
                conn.executescript(core_schema_script_with_version_update)
                logging.debug("[Schema V1] Core Schema script (incl. version update) executed.")

                # Ensure Claims table exists as part of base schema (additive)
                try:
                    conn.executescript(self._CLAIMS_TABLE_SQL)
                    logging.debug("[Schema V1] Claims table and indices ensured.")
                except sqlite3.Error as e:
                    logging.error(f"[Schema V1] Failed creating Claims table: {e}", exc_info=True)
                    raise

                # Ensure Collections tables exist (output_templates, reading_highlights)
                try:
                    conn.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS output_templates (
                            id INTEGER PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            type TEXT NOT NULL,
                            format TEXT NOT NULL,
                            body TEXT NOT NULL,
                            description TEXT,
                            is_default INTEGER NOT NULL DEFAULT 0,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        CREATE INDEX IF NOT EXISTS idx_output_templates_user ON output_templates(user_id);
                        CREATE UNIQUE INDEX IF NOT EXISTS ux_output_templates_user_name ON output_templates(user_id, name);

                        CREATE TABLE IF NOT EXISTS reading_highlights (
                            id INTEGER PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            item_id INTEGER NOT NULL,
                            quote TEXT NOT NULL,
                            start_offset INTEGER,
                            end_offset INTEGER,
                            color TEXT,
                            note TEXT,
                            created_at TEXT NOT NULL,
                            anchor_strategy TEXT NOT NULL DEFAULT 'fuzzy_quote',
                            content_hash_ref TEXT,
                            context_before TEXT,
                            context_after TEXT,
                            state TEXT NOT NULL DEFAULT 'active'
                        );
                        CREATE INDEX IF NOT EXISTS idx_highlights_user_item ON reading_highlights(user_id, item_id);
                        """
                    )
                    logging.debug("[Schema V1] Collections tables ensured.")
                except sqlite3.Error as e:
                    logging.error(f"[Schema V1] Failed creating Collections tables: {e}", exc_info=True)
                    raise

                # --- Validation step (optional but good) - Check Media table ---
                try:
                    cursor = conn.execute("PRAGMA table_info(Media)")
                    columns = {row['name'] for row in cursor.fetchall()}
                    # Update this set to match ALL columns defined in _TABLES_SQL_V1.Media
                    expected_cols = {'id', 'url', 'title', 'type', 'content', 'author', 'ingestion_date', 'transcription_model', 'is_trash', 'trash_date', 'vector_embedding', 'chunking_status', 'vector_processing', 'content_hash', 'uuid', 'last_modified', 'version', 'client_id', 'deleted', 'prev_version', 'merge_parent_uuid'}
                    if not expected_cols.issubset(columns):
                        missing_cols = expected_cols - columns
                        raise SchemaError(f"Validation Error: Media table is missing columns after creation: {missing_cols}")
                    logging.debug("[Schema V1] Media table structure validated successfully.")
                except (sqlite3.Error, SchemaError) as val_err:
                    logging.error(f"[Schema V1] Validation failed after table creation: {val_err}", exc_info=True)
                    raise  # Re-raise to trigger rollback

                # --- Explicitly check version *inside* transaction AFTER script ---
                # This helps debug if the update itself isn't working
                cursor_check = conn.execute("SELECT version FROM schema_version LIMIT 1")
                version_in_tx = cursor_check.fetchone()
                if not version_in_tx or version_in_tx['version'] != self._CURRENT_SCHEMA_VERSION:
                    logging.error(f"[Schema V1] Version check *inside* transaction failed. Found: {version_in_tx['version'] if version_in_tx else 'None'}")
                    raise SchemaError("Schema version update did not take effect within the transaction.")
                logging.debug(f"[Schema V1] Version check inside transaction confirmed version is {self._CURRENT_SCHEMA_VERSION}.")

            # Transaction commits here if all steps above succeeded
            logging.info(f"[Schema V1] Core Schema V1 (incl. version update) applied and committed successfully for DB: {self.db_path_str}.")

            # --- Create FTS Tables Separately (Remains the same) ---
            try:
                logging.debug("[Schema V1] Applying FTS Tables...")
                self._ensure_fts_structures(conn)
                logging.info("[Schema V1] FTS Tables created successfully.")
            except (sqlite3.Error, DatabaseError) as fts_err:
                logging.error(f"[Schema V1] Failed to create FTS tables: {fts_err}", exc_info=True)

        except sqlite3.Error as e:
            logging.error(f"[Schema V1] Application failed during core transaction: {e}", exc_info=True)
            raise DatabaseError(f"DB schema V1 setup failed: {e}") from e
        except Exception as e:
            logging.error(f"[Schema V1] Unexpected error during schema V1 application: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error applying schema V1: {e}") from e

    def _convert_sqlite_sql_to_postgres_statements(self, sql: str) -> List[str]:
        """Convert SQLite-oriented SQL blob into Postgres-compatible statements."""

        statements: List[str] = []
        buffer: List[str] = []
        for raw_line in sql.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('--'):
                continue
            upper = line.upper()
            if upper.startswith('PRAGMA'):
                continue
            if 'VIRTUAL TABLE' in upper and 'FTS5' in upper:
                continue
            if upper.startswith('DROP TRIGGER') or upper.startswith('CREATE TRIGGER'):
                continue
            buffer.append(raw_line)
            if line.endswith(';'):
                stmt = '\n'.join(buffer)
                buffer = []
                transformed = self._transform_sqlite_statement_to_postgres(stmt)
                if transformed:
                    statements.append(transformed)
        return statements

    def _transform_sqlite_statement_to_postgres(self, statement: str) -> Optional[str]:
        """Apply token-level rewrites so a SQLite statement can run on Postgres."""
        # Remove SQL comments before any normalization to avoid commenting-out tokens
        # - Strip single-line comments starting with '--'
        # - Strip simple block comments '/* ... */' (best-effort, non-nested)
        stmt = re.sub(r"--.*?$", "", statement, flags=re.MULTILINE)
        stmt = re.sub(r"/\*.*?\*/", "", stmt, flags=re.DOTALL)
        stmt = stmt.strip()
        if not stmt:
            return None

        upper = stmt.upper()
        # Skip SQLite-only statements that are not relevant in Postgres
        if upper.startswith('ANALYZE '):
            return None
        if upper.startswith('PRAGMA '):
            return None

        # Normalize whitespace for easier pattern replacements
        stmt = re.sub(r'\s+', ' ', stmt)

        # Data type adjustments
        stmt = re.sub(r'INTEGER PRIMARY KEY AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'INTEGER PRIMARY KEY', 'BIGINT PRIMARY KEY', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN NOT NULL DEFAULT 0', 'BOOLEAN NOT NULL DEFAULT FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN NOT NULL DEFAULT 1', 'BOOLEAN NOT NULL DEFAULT TRUE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN DEFAULT 0', 'BOOLEAN DEFAULT FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN DEFAULT 1', 'BOOLEAN DEFAULT TRUE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'DATETIME', 'TIMESTAMPTZ', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BLOB', 'BYTEA', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'REAL', 'DOUBLE PRECISION', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'COLLATE NOCASE', '', stmt, flags=re.IGNORECASE)

        # Partial index predicate conversion
        stmt = re.sub(r'WHERE deleted = 0', 'WHERE deleted = FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'WHERE deleted = 1', 'WHERE deleted = TRUE', stmt, flags=re.IGNORECASE)

        # Insert semantics
        if stmt.upper().startswith('INSERT OR IGNORE'):
            stmt = re.sub(r'INSERT OR IGNORE', 'INSERT', stmt, flags=re.IGNORECASE, count=1)
            if stmt.endswith(';'):
                stmt = stmt[:-1] + ' ON CONFLICT DO NOTHING;'
            else:
                stmt = stmt + ' ON CONFLICT DO NOTHING;'

        # Ensure statement ends with semicolon
        if not stmt.endswith(';'):
            stmt = stmt + ';'
        return stmt

    def _apply_schema_v1_postgres(self, conn) -> None:
        """Apply the Version 1 schema using Postgres-compatible statements."""

        table_statements = self._convert_sqlite_sql_to_postgres_statements(self._TABLES_SQL_V1)
        # Ensure base tables definitely exist before any indices
        # Add Claims table after base
        table_statements += self._convert_sqlite_sql_to_postgres_statements(self._CLAIMS_TABLE_SQL)

        # Defensive ordering: run CREATE TABLE statements first, then non-DDL (INSERT/UPDATE), then indexes
        create_tables = [s for s in table_statements if s.strip().upper().startswith('CREATE TABLE')]
        other_table_stmts = [s for s in table_statements if s not in create_tables]

        # Execute CREATE TABLEs
        for stmt in create_tables:
            logger.debug(f"Applying Postgres base table DDL: {stmt[:120]}...")
            self.backend.execute(stmt, connection=conn)

        # Now run any INSERT/UPDATE initializers (e.g., schema_version seed)
        for stmt in other_table_stmts:
            logger.debug(f"Applying Postgres base initializer DDL: {stmt[:120]}...")
            self.backend.execute(stmt, connection=conn)

        # Verify critical tables exist (defensive):
        must_tables = [
            'media', 'keywords', 'mediakeywords', 'transcripts',
            'mediachunks', 'unvectorizedmediachunks',
            'documentversions', 'documentversionidentifiers', 'documentstructureindex',
            'sync_log', 'chunkingtemplates', 'claims',
        ]
        for t in must_tables:
            if not self.backend.table_exists(t, connection=conn):
                raise SchemaError(f"Postgres schema init missing table: {t}")

        index_statements = self._convert_sqlite_sql_to_postgres_statements(self._INDICES_SQL_V1)
        for stmt in index_statements:
            logger.debug(f"Applying Postgres index DDL: {stmt[:120]}...")
            self.backend.execute(stmt, connection=conn)

        # Ensure schema_version reflects the current code version (single row)
        self.backend.execute(
            "DELETE FROM schema_version WHERE version <> %s",
            (0,),
            connection=conn,
        )
        self.backend.execute(
            "INSERT INTO schema_version (version) VALUES (%s) ON CONFLICT (version) DO NOTHING",
            (0,),
            connection=conn,
        )
        self.backend.execute(
            "UPDATE schema_version SET version = %s",
            (self._CURRENT_SCHEMA_VERSION,),
            connection=conn,
        )
    def _initialize_schema(self):
        """Checks schema version and applies initial schema or migrations."""
        if self.backend_type == BackendType.SQLITE:
            self._initialize_schema_sqlite()
        elif self.backend_type == BackendType.POSTGRESQL:
            self._initialize_schema_postgres()
        else:
            raise NotImplementedError(
                f"Schema initialization not implemented for backend {self.backend_type}"
            )

    def _initialize_schema_sqlite(self):
        conn = self.get_connection()
        try:
            current_db_version = self._get_db_version(conn)
            target_version = self._CURRENT_SCHEMA_VERSION

            logging.info(f"Checking DB schema. Current version: {current_db_version}. Code supports: {target_version}")

            if current_db_version == target_version:
                logging.debug("Database schema is up to date.")
                # Optionally ensure FTS tables exist even if schema version matches
                try:
                    # Ensure Claims table exists for older DBs without bumping version
                    conn.executescript(self._CLAIMS_TABLE_SQL)
                    self._ensure_fts_structures(conn)
                    # Ensure Collections tables exist
                    conn.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS output_templates (
                            id INTEGER PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            type TEXT NOT NULL,
                            format TEXT NOT NULL,
                            body TEXT NOT NULL,
                            description TEXT,
                            is_default INTEGER NOT NULL DEFAULT 0,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        CREATE INDEX IF NOT EXISTS idx_output_templates_user ON output_templates(user_id);
                        CREATE UNIQUE INDEX IF NOT EXISTS ux_output_templates_user_name ON output_templates(user_id, name);

                        CREATE TABLE IF NOT EXISTS reading_highlights (
                            id INTEGER PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            item_id INTEGER NOT NULL,
                            quote TEXT NOT NULL,
                            start_offset INTEGER,
                            end_offset INTEGER,
                            color TEXT,
                            note TEXT,
                            created_at TEXT NOT NULL,
                            anchor_strategy TEXT NOT NULL DEFAULT 'fuzzy_quote',
                            content_hash_ref TEXT,
                            context_before TEXT,
                            context_after TEXT,
                            state TEXT NOT NULL DEFAULT 'active'
                        );
                        CREATE INDEX IF NOT EXISTS idx_highlights_user_item ON reading_highlights(user_id, item_id);
                        """
                    )
                    logging.debug("Verified FTS tables exist.")
                except (sqlite3.Error, DatabaseError) as fts_err:
                    logging.warning(f"Could not verify/create FTS tables on already correct schema version: {fts_err}")
                return

            if current_db_version > target_version:
                raise SchemaError(f"Database schema version ({current_db_version}) is newer than supported by code ({target_version}).")

            # --- Apply Migrations ---
            if current_db_version == 0:
                # Fresh database, apply base schema directly at current version
                self._apply_schema_v1_sqlite(conn)
                # Verify version update
                final_db_version = self._get_db_version(conn)
                if final_db_version != target_version:
                    raise SchemaError(f"Schema applied, but final DB version is {final_db_version}, expected {target_version}.")
                logger.info(f"Database schema initialized to version {target_version}.")

            elif current_db_version < target_version:
                # Use the migration system for existing databases.
                # Special-case in-memory DBs: treat them as fresh and apply base schema,
                # since migration helpers open separate connections that won't share :memory: state.
                try:
                    if self.is_memory_db:
                        self._apply_schema_v1_sqlite(conn)
                    else:
                        # Close the current connection to avoid locks
                        conn.close()

                        # Run migrations
                        # For test databases, use the migrations from the source code directory
                        migrations_dir = None
                        # Treat common test/temp locations as needing source-bound migrations
                        db_name = os.path.basename(self.db_path_str)
                        db_dir = os.path.dirname(self.db_path_str)
                        db_dir_lower = db_dir.lower()
                        if (
                            "test_" in db_name
                            or "tmp" in db_dir_lower
                            or "temp" in db_dir_lower
                            or "pytest" in db_dir_lower
                        ):
                            migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
                        migrator = DatabaseMigrator(self.db_path_str, migrations_dir=migrations_dir)
                        result = migrator.migrate_to_version(target_version)

                        status = (result or {}).get("status")
                        if status in {"success", "no_migrations", "no_change"}:
                            if status == "success":
                                logger.info(
                                    f"Database migrated from version {result['previous_version']} to {result['current_version']}"
                                )
                            else:
                                logger.info(
                                    f"No migration scripts to apply (status={status}); proceeding with FTS/setup checks"
                                )
                            # Get a new connection after migration (or when no migration files present)
                            conn = sqlite3.connect(self.db_path_str, check_same_thread=False)
                            conn.row_factory = sqlite3.Row
                            final_db_version = self._get_db_version(conn)
                            if final_db_version != target_version:
                                raise SchemaError(
                                    "Database schema did not reach expected version after migration run "
                                    f"(status={status}, current={final_db_version}, expected={target_version})."
                                )
                            # Ensure FTS tables exist
                            self._ensure_fts_structures(conn)
                            # Ensure Collections tables exist
                            conn.executescript(
                                """
                                CREATE TABLE IF NOT EXISTS output_templates (
                                    id INTEGER PRIMARY KEY,
                                    user_id TEXT NOT NULL,
                                    name TEXT NOT NULL,
                                    type TEXT NOT NULL,
                                    format TEXT NOT NULL,
                                    body TEXT NOT NULL,
                                    description TEXT,
                                    is_default INTEGER NOT NULL DEFAULT 0,
                                    created_at TEXT NOT NULL,
                                    updated_at TEXT NOT NULL
                                );
                                CREATE INDEX IF NOT EXISTS idx_output_templates_user ON output_templates(user_id);
                                CREATE UNIQUE INDEX IF NOT EXISTS ux_output_templates_user_name ON output_templates(user_id, name);

                                CREATE TABLE IF NOT EXISTS reading_highlights (
                                    id INTEGER PRIMARY KEY,
                                    user_id TEXT NOT NULL,
                                    item_id INTEGER NOT NULL,
                                    quote TEXT NOT NULL,
                                    start_offset INTEGER,
                                    end_offset INTEGER,
                                    color TEXT,
                                    note TEXT,
                                    created_at TEXT NOT NULL,
                                    anchor_strategy TEXT NOT NULL DEFAULT 'fuzzy_quote',
                                    content_hash_ref TEXT,
                                    context_before TEXT,
                                    context_after TEXT,
                                    state TEXT NOT NULL DEFAULT 'active'
                                );
                                CREATE INDEX IF NOT EXISTS idx_highlights_user_item ON reading_highlights(user_id, item_id);
                                """
                            )
                        else:
                            raise SchemaError(f"Migration failed: {result}")

                except MigrationError as e:
                    raise SchemaError(f"Database migration failed: {e}") from e

            else:
                raise SchemaError(f"Migration needed from version {current_db_version} to {target_version}, but no migration path is defined.")

        except (DatabaseError, SchemaError, sqlite3.Error) as e:
            logger.error(f"Schema initialization/migration failed: {e}", exc_info=True)
            raise DatabaseError(f"Schema initialization failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during schema initialization: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error applying schema: {e}") from e

    def _initialize_schema_postgres(self):
        target_version = self._CURRENT_SCHEMA_VERSION
        backend = self.backend

        with backend.transaction() as conn:
            schema_exists = backend.table_exists('schema_version', connection=conn)

            if not schema_exists:
                self._apply_schema_v1_postgres(conn)
                self._ensure_postgres_fts(conn)
                # Ensure Collections tables exist
                try:
                    backend.execute(
                        (
                            "CREATE TABLE IF NOT EXISTS output_templates ("
                            "id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, type TEXT NOT NULL, "
                            "format TEXT NOT NULL, body TEXT NOT NULL, description TEXT, is_default BOOLEAN NOT NULL DEFAULT FALSE, "
                            "created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)"
                        ),
                        connection=conn,
                    )
                    backend.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_output_templates_user_name ON output_templates(user_id, name)", connection=conn)
                    backend.execute(
                        (
                            "CREATE TABLE IF NOT EXISTS reading_highlights ("
                            "id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, item_id INTEGER NOT NULL, quote TEXT NOT NULL, "
                            "start_offset INTEGER, end_offset INTEGER, color TEXT, note TEXT, created_at TIMESTAMPTZ NOT NULL, "
                            "anchor_strategy TEXT NOT NULL DEFAULT 'fuzzy_quote', content_hash_ref TEXT, context_before TEXT, context_after TEXT, "
                            "state TEXT NOT NULL DEFAULT 'active')"
                        ),
                        connection=conn,
                    )
                    backend.execute("CREATE INDEX IF NOT EXISTS idx_highlights_user_item ON reading_highlights(user_id, item_id)", connection=conn)
                except Exception:
                    pass
                self._sync_postgres_sequences(conn)
                self._ensure_postgres_rls(conn)
                return

            result = backend.execute("SELECT version FROM schema_version LIMIT 1", connection=conn)
            current_version_raw = result.scalar if result else None
            current_version = int(current_version_raw or 0)

            if current_version > target_version:
                raise SchemaError(
                    f"Database schema version ({current_version}) is newer than supported by code ({target_version})."
                )

            # Defensive: ensure base tables exist even if schema_version table is present
            # Some environments may create schema_version before full schema creation.
            must_tables = [
                'media', 'keywords', 'mediakeywords', 'transcripts',
                'mediachunks', 'unvectorizedmediachunks', 'documentversions',
                'documentversionidentifiers', 'sync_log', 'chunkingtemplates', 'claims',
            ]
            missing = [t for t in must_tables if not backend.table_exists(t, connection=conn)]
            if missing:
                logger.warning(
                    "Postgres schema_version exists but base tables missing: %s. Applying base schema.", missing
                )
                self._apply_schema_v1_postgres(conn)
                current_version = target_version  # base schema applies current version
                self._ensure_postgres_fts(conn)
                # Ensure Collections tables exist
                try:
                    backend.execute(
                        (
                            "CREATE TABLE IF NOT EXISTS output_templates ("
                            "id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, type TEXT NOT NULL, "
                            "format TEXT NOT NULL, body TEXT NOT NULL, description TEXT, is_default BOOLEAN NOT NULL DEFAULT FALSE, "
                            "created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)"
                        ),
                        connection=conn,
                    )
                    backend.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_output_templates_user_name ON output_templates(user_id, name)", connection=conn)
                    backend.execute(
                        (
                            "CREATE TABLE IF NOT EXISTS reading_highlights ("
                            "id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, item_id INTEGER NOT NULL, quote TEXT NOT NULL, "
                            "start_offset INTEGER, end_offset INTEGER, color TEXT, note TEXT, created_at TIMESTAMPTZ NOT NULL, "
                            "anchor_strategy TEXT NOT NULL DEFAULT 'fuzzy_quote', content_hash_ref TEXT, context_before TEXT, context_after TEXT, "
                            "state TEXT NOT NULL DEFAULT 'active')"
                        ),
                        connection=conn,
                    )
                    backend.execute("CREATE INDEX IF NOT EXISTS idx_highlights_user_item ON reading_highlights(user_id, item_id)", connection=conn)
                except Exception:
                    pass
                self._sync_postgres_sequences(conn)
                self._ensure_postgres_rls(conn)
                return

            if current_version < target_version:
                self._run_postgres_migrations(conn, current_version, target_version)

            self._ensure_postgres_fts(conn)
            # Ensure Collections tables exist
            try:
                backend.execute(
                    (
                        "CREATE TABLE IF NOT EXISTS output_templates ("
                        "id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, type TEXT NOT NULL, "
                        "format TEXT NOT NULL, body TEXT NOT NULL, description TEXT, is_default BOOLEAN NOT NULL DEFAULT FALSE, "
                        "created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)"
                    ),
                    connection=conn,
                )
                backend.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_output_templates_user_name ON output_templates(user_id, name)", connection=conn)
                backend.execute(
                    (
                        "CREATE TABLE IF NOT EXISTS reading_highlights ("
                        "id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, item_id INTEGER NOT NULL, quote TEXT NOT NULL, "
                        "start_offset INTEGER, end_offset INTEGER, color TEXT, note TEXT, created_at TIMESTAMPTZ NOT NULL, "
                        "anchor_strategy TEXT NOT NULL DEFAULT 'fuzzy_quote', content_hash_ref TEXT, context_before TEXT, context_after TEXT, "
                        "state TEXT NOT NULL DEFAULT 'active')"
                    ),
                    connection=conn,
                )
                backend.execute("CREATE INDEX IF NOT EXISTS idx_highlights_user_item ON reading_highlights(user_id, item_id)", connection=conn)
            except Exception:
                pass
            self._sync_postgres_sequences(conn)
            self._ensure_postgres_rls(conn)

    def _run_postgres_migrations(self, conn, current_version: int, target_version: int) -> None:
        """Execute sequential PostgreSQL migrations until the target version is reached."""

        migrations = self._get_postgres_migrations()
        applied_version = current_version

        for version in sorted(migrations.keys()):
            if applied_version < version <= target_version:
                migrations[version](conn)
                self._update_schema_version_postgres(conn, version)
                applied_version = version

        self._ensure_postgres_rls(conn)

        if applied_version < target_version:
            raise SchemaError(
                f"PostgreSQL migration path incomplete for MediaDatabase: reached {applied_version}, expected {target_version}."
            )

    def _get_postgres_migrations(self):
        """Return mapping of target version to migration callable."""

        return {
            5: self._postgres_migrate_to_v5,
            6: self._postgres_migrate_to_v6,
            7: self._postgres_migrate_to_v7,
            8: self._postgres_migrate_to_v8,
        }

    def _postgres_migrate_to_v5(self, conn) -> None:
        """Add safe_metadata column to DocumentVersions for PostgreSQL deployments."""

        backend = self.backend
        ident = backend.escape_identifier
        # Use lower-case identifiers for PostgreSQL to avoid case-sensitive quoted names
        backend.execute(
            (
                f"ALTER TABLE {ident('documentversions')} "
                f"ADD COLUMN IF NOT EXISTS {ident('safe_metadata')} TEXT"
            ),
            connection=conn,
        )

    def _postgres_migrate_to_v6(self, conn) -> None:
        """Introduce the DocumentVersionIdentifiers table and supporting indexes.

        For PostgreSQL we standardize on lower-case, unquoted identifiers to
        avoid case-sensitive table name issues. The base schema creation path
        also uses lower-case names via the SQL translator, so we reference
        documentversions consistently here.
        """

        backend = self.backend
        ident = backend.escape_identifier

        # Always use lower-case identifiers to match base PostgreSQL schema
        backend.execute(
            (
                f"CREATE TABLE IF NOT EXISTS {ident('documentversionidentifiers')} ("
                f"{ident('dv_id')} BIGINT PRIMARY KEY REFERENCES {ident('documentversions')}({ident('id')}) ON DELETE CASCADE,"
                f"{ident('doi')} TEXT,"
                f"{ident('pmid')} TEXT,"
                f"{ident('pmcid')} TEXT,"
                f"{ident('arxiv_id')} TEXT,"
                f"{ident('s2_paper_id')} TEXT"
                ")"
            ),
            connection=conn,
        )

        index_defs = [
            ("idx_dvi_doi", "doi"),
            ("idx_dvi_pmid", "pmid"),
            ("idx_dvi_pmcid", "pmcid"),
            ("idx_dvi_arxiv", "arxiv_id"),
            ("idx_dvi_s2", "s2_paper_id"),
        ]

        for index_name, column in index_defs:
            backend.execute(
                (
                    f"CREATE INDEX IF NOT EXISTS {ident(index_name)} "
                    f"ON {ident('documentversionidentifiers')} ({ident(column)})"
                ),
                connection=conn,
            )

    def _postgres_migrate_to_v7(self, conn) -> None:
        """Add DocumentStructureIndex table and indices (PostgreSQL)."""
        backend = self.backend
        ident = backend.escape_identifier
        # Create table
        backend.execute(
            (
                f"CREATE TABLE IF NOT EXISTS {ident('documentstructureindex')} ("
                f"{ident('id')} BIGSERIAL PRIMARY KEY,"
                f"{ident('media_id')} BIGINT NOT NULL REFERENCES {ident('media')}({ident('id')}) ON DELETE CASCADE,"
                f"{ident('parent_id')} BIGINT NULL,"
                f"{ident('kind')} TEXT NOT NULL,"
                f"{ident('level')} INTEGER,"
                f"{ident('title')} TEXT,"
                f"{ident('start_char')} BIGINT NOT NULL,"
                f"{ident('end_char')} BIGINT NOT NULL,"
                f"{ident('order_index')} INTEGER,"
                f"{ident('path')} TEXT,"
                f"{ident('created_at')} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
                f"{ident('last_modified')} TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                f"{ident('version')} INTEGER NOT NULL DEFAULT 1,"
                f"{ident('client_id')} TEXT NOT NULL,"
                f"{ident('deleted')} BOOLEAN NOT NULL DEFAULT FALSE"
                ")"
            ),
            connection=conn,
        )
        # Indices
        idx_defs = [
            ("idx_dsi_media_kind", "media_id, kind"),
            ("idx_dsi_media_start", "media_id, start_char"),
            ("idx_dsi_media_parent", "parent_id"),
        ]
        for name, cols in idx_defs:
            backend.execute(
                (
                    f"CREATE INDEX IF NOT EXISTS {ident(name)} ON {ident('documentstructureindex')} ({cols})"
                ),
                connection=conn,
            )

    def _postgres_migrate_to_v8(self, conn) -> None:
        """Add org_id and team_id scope columns to content tables (PostgreSQL)."""
        backend = self.backend
        ident = backend.escape_identifier

        scoped_tables = [
            "media",
            "sync_log",
        ]

        for table in scoped_tables:
            backend.execute(
                (
                    f"ALTER TABLE {ident(table)} "
                    f"ADD COLUMN IF NOT EXISTS {ident('org_id')} BIGINT"
                ),
                connection=conn,
            )
            backend.execute(
                (
                    f"ALTER TABLE {ident(table)} "
                    f"ADD COLUMN IF NOT EXISTS {ident('team_id')} BIGINT"
                ),
                connection=conn,
            )

    def _update_schema_version_postgres(self, conn, version: int) -> None:
        """Ensure schema_version table reflects the supplied version."""

        backend = self.backend
        backend.execute(
            "UPDATE schema_version SET version = %s",
            (version,),
            connection=conn,
        )

    def _sync_postgres_sequences(self, conn) -> None:
        """Align PostgreSQL sequences with current table maxima."""

        backend = self.backend
        sequence_rows = backend.execute(
            """
            SELECT
                sequence_ns.nspname AS sequence_schema,
                seq.relname AS sequence_name,
                tab.relname AS table_name,
                col.attname AS column_name
            FROM pg_class seq
            JOIN pg_namespace sequence_ns ON sequence_ns.oid = seq.relnamespace
            JOIN pg_depend dep ON dep.objid = seq.oid AND dep.deptype = 'a'
            JOIN pg_class tab ON tab.oid = dep.refobjid
            JOIN pg_namespace tab_ns ON tab_ns.oid = tab.relnamespace
            JOIN pg_attribute col ON col.attrelid = tab.oid AND col.attnum = dep.refobjsubid
            WHERE seq.relkind = 'S' AND tab_ns.nspname = 'public';
            """,
            connection=conn,
        )

        for row in sequence_rows.rows:
            table_name = row.get('table_name')
            column_name = row.get('column_name')
            sequence_schema = row.get('sequence_schema', 'public')
            sequence_name = row.get('sequence_name')

            if not table_name or not column_name or not sequence_name:
                continue

            qualified_sequence = f"{sequence_schema}.{sequence_name}"
            ident = backend.escape_identifier

            max_result = backend.execute(
                (
                    f"SELECT COALESCE(MAX({ident(column_name)}), 0) AS max_id "
                    f"FROM {ident(table_name)}"
                ),
                connection=conn,
            )

            max_id_raw = max_result.scalar
            try:
                max_id = int(max_id_raw or 0)
            except (TypeError, ValueError):
                max_id = 0

            if max_id <= 0:
                backend.execute(
                    "SELECT setval(%s, %s, false)",
                    (qualified_sequence, 1),
                    connection=conn,
                )
            else:
                backend.execute(
                    "SELECT setval(%s, %s)",
                    (qualified_sequence, max_id),
                    connection=conn,
                )

    def _ensure_fts_structures(self, conn) -> None:
        if self.backend_type == BackendType.SQLITE:
            self._ensure_sqlite_fts(conn)
        elif self.backend_type == BackendType.POSTGRESQL:
            self._ensure_postgres_fts(conn)
        else:
            raise NotImplementedError(
                f"FTS bootstrap not implemented for backend {self.backend_type}"
            )

    def _ensure_sqlite_fts(self, conn: sqlite3.Connection) -> None:
        conn.executescript(self._FTS_TABLES_SQL)
        conn.executescript(self._CLAIMS_FTS_TRIGGERS_SQL)
        # Verify core FTS tables exist to avoid silent search failures
        try:
            cur = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('media_fts','keyword_fts')
                """
            )
            existing = {row[0] for row in cur.fetchall()}
            missing = {"media_fts", "keyword_fts"} - existing
            if missing:
                raise DatabaseError(f"Missing required FTS tables: {', '.join(sorted(missing))}")
        finally:
            conn.commit()

    def _ensure_postgres_fts(self, conn) -> None:
        backend = self.backend
        backend.create_fts_table(
            table_name='media_fts',
            source_table='media',
            columns=['title', 'content'],
            connection=conn,
        )
        backend.create_fts_table(
            table_name='keyword_fts',
            source_table='keywords',
            columns=['keyword'],
            connection=conn,
        )
        backend.create_fts_table(
            table_name='claims_fts',
            source_table='claims',
            columns=['claim_text'],
            connection=conn,
        )
        # Chunk-level FTS on UnvectorizedMediaChunks
        try:
            backend.create_fts_table(
                table_name='unvectorized_chunks_fts',
                source_table='unvectorizedmediachunks',
                columns=['chunk_text'],
                connection=conn,
            )
        except Exception as e:
            logging.warning(f"Failed to ensure Postgres chunk-level FTS: {e}")

    def _postgres_policy_exists(self, conn, table: str, policy: str) -> bool:
        """Check whether a named RLS policy exists for the given table."""
        try:
            result = self.backend.execute(
                "SELECT 1 FROM pg_policies WHERE schemaname = current_schema() AND tablename = %s AND policyname = %s",
                (table, policy),
                connection=conn,
            )
            rows = getattr(result, "rows", None)
            return bool(rows)
        except Exception:
            return False

    def _ensure_postgres_rls(self, conn) -> None:
        """Ensure row-level security policies exist for shared content tables."""
        backend = self.backend
        ident = backend.escape_identifier

        org_array = "COALESCE(string_to_array(NULLIF(current_setting('app.org_ids', true), ''), ',')::BIGINT[], ARRAY[]::BIGINT[])"
        team_array = "COALESCE(string_to_array(NULLIF(current_setting('app.team_ids', true), ''), ',')::BIGINT[], ARRAY[]::BIGINT[])"

        policy_sets = {
            'media': [
                ('media_scope_admin', "COALESCE(current_setting('app.is_admin', true), '0') = '1'"),
                ('media_scope_personal', f"{ident('media')}.client_id = current_setting('app.current_user_id', true)"),
                ('media_scope_org', f"{ident('media')}.org_id IS NOT NULL AND {ident('media')}.org_id = ANY({org_array})"),
                ('media_scope_team', f"{ident('media')}.team_id IS NOT NULL AND {ident('media')}.team_id = ANY({team_array})"),
            ],
            'sync_log': [
                ('sync_scope_admin', "COALESCE(current_setting('app.is_admin', true), '0') = '1'"),
                ('sync_scope_personal', f"{ident('sync_log')}.client_id = current_setting('app.current_user_id', true)"),
                ('sync_scope_org', f"{ident('sync_log')}.org_id IS NOT NULL AND {ident('sync_log')}.org_id = ANY({org_array})"),
                ('sync_scope_team', f"{ident('sync_log')}.team_id IS NOT NULL AND {ident('sync_log')}.team_id = ANY({team_array})"),
            ],
        }

        try:
            backend.execute(f"ALTER TABLE {ident('media')} ENABLE ROW LEVEL SECURITY", connection=conn)
            backend.execute(f"ALTER TABLE {ident('media')} FORCE ROW LEVEL SECURITY", connection=conn)
        except Exception as exc:
            logging.debug(f"Could not enable RLS for media: {exc}")

        # Create policies only if missing (idempotent)
        for policy_name, predicate in policy_sets['media']:
            try:
                if not self._postgres_policy_exists(conn, 'media', policy_name):
                    backend.execute(
                        f"""
                        CREATE POLICY {backend.escape_identifier(policy_name)} ON {ident('media')}
                        FOR ALL
                        USING ({predicate})
                        WITH CHECK ({predicate})
                        """,
                        connection=conn,
                    )
            except Exception as exc:
                logging.debug(f"Skipping media policy {policy_name}: {exc}")

        try:
            backend.execute(f"ALTER TABLE {ident('sync_log')} ENABLE ROW LEVEL SECURITY", connection=conn)
            backend.execute(f"ALTER TABLE {ident('sync_log')} FORCE ROW LEVEL SECURITY", connection=conn)
        except Exception as exc:
            logging.debug(f"Could not enable RLS for sync_log: {exc}")

        # Create policies only if missing (idempotent)
        for policy_name, predicate in policy_sets['sync_log']:
            try:
                if not self._postgres_policy_exists(conn, 'sync_log', policy_name):
                    backend.execute(
                        f"""
                        CREATE POLICY {backend.escape_identifier(policy_name)} ON {ident('sync_log')}
                        FOR ALL
                        USING ({predicate})
                        WITH CHECK ({predicate})
                        """,
                        connection=conn,
                    )
            except Exception as exc:
                logging.debug(f"Skipping sync_log policy {policy_name}: {exc}")

    # --- Internal Helpers (Unchanged) ---
    def _get_current_utc_timestamp_str(self) -> str:
        """
        Internal helper to generate a UTC timestamp string in ISO 8601 format.

        Returns:
            str: Timestamp string (e.g., '2023-10-27T10:30:00.123Z').
        """
        # Use ISO 8601 format with Z for UTC, more standard
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    # --- Claims Helpers (Stage 1 minimal CRUD) ---
    def upsert_claims(self, claims: List[Dict[str, Any]]) -> int:
        """
        Insert claims in bulk. This is a minimal Stage 1 helper.

        Expects each item to contain: media_id, chunk_index, claim_text, chunk_hash,
        extractor, extractor_version. Optional: span_start, span_end, confidence,
        uuid, last_modified, version, client_id, deleted.

        Returns:
            int: Number of rows inserted.
        """
        if not claims:
            return 0
        now = self._get_current_utc_timestamp_str()
        rows: List[tuple] = []
        for c in claims:
            rows.append((
                int(c["media_id"]),
                int(c.get("chunk_index", 0)),
                c.get("span_start"),
                c.get("span_end"),
                str(c["claim_text"]),
                float(c.get("confidence")) if c.get("confidence") is not None else None,
                str(c.get("extractor", "heuristic")),
                str(c.get("extractor_version", "v1")),
                str(c["chunk_hash"]),
                str(c.get("uuid", self._generate_uuid())),
                str(c.get("last_modified", now)),
                int(c.get("version", 1)),
                str(c.get("client_id", self.client_id)),
                c.get("prev_version"),
                c.get("merge_parent_uuid"),
            ))
        with self.transaction() as conn:
            self.execute_many(
                """
                INSERT INTO Claims (
                    media_id, chunk_index, span_start, span_end, claim_text, confidence,
                    extractor, extractor_version, chunk_hash, uuid, last_modified,
                    version, client_id, prev_version, merge_parent_uuid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
                commit=False,
                connection=conn,
            )
        return len(rows)

    def get_claims_by_media(self, media_id: int, *, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Fetch claims for a media item (excluding soft-deleted), ordered by chunk_index then id.
        """
        cur = self.execute_query(
            """
            SELECT id, media_id, chunk_index, span_start, span_end, claim_text, confidence,
                   extractor, extractor_version, chunk_hash, created_at, uuid,
                   last_modified, version, client_id
            FROM Claims
            WHERE media_id = ? AND deleted = 0
            ORDER BY chunk_index ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            (media_id, int(limit), int(max(0, offset))),
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def soft_delete_claims_for_media(self, media_id: int) -> int:
        """
        Soft-delete all claims for a given media_id by setting deleted=1 and bumping version.
        Returns the number of affected rows.
        """
        try:
            with self.transaction() as conn:
                current_time = self._get_current_utc_timestamp_str()
                # Mark rows as deleted and bump version/last_modified
                update_sql = (
                    "UPDATE Claims "
                    "SET deleted = 1, version = version + 1, last_modified = ?, client_id = ? "
                    "WHERE media_id = ? AND deleted = 0"
                )
                cur = self._execute_with_connection(
                    conn,
                    update_sql,
                    (current_time, self.client_id, int(media_id)),
                )
                affected = cur.rowcount or 0

                # Best-effort cleanup of SQLite FTS table; Postgres uses triggers/tsvector on base table
                if self.backend_type == BackendType.SQLITE:
                    try:
                        self._execute_with_connection(
                            conn,
                            "DELETE FROM claims_fts WHERE rowid IN (SELECT id FROM Claims WHERE media_id = ?)",
                            (int(media_id),),
                        )
                    except sqlite3.Error:
                        pass

                return affected
        except sqlite3.Error as e:
            logging.error(f"Failed to soft-delete claims for media_id={media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to soft-delete claims: {e}") from e

    def rebuild_claims_fts(self) -> int:
        """
        Rebuild the claims full-text search index using the active backend.

        Returns:
            int: Number of rows indexed.
        """
        try:
            with self.transaction() as conn:
                if self.backend_type == BackendType.SQLITE:
                    try:
                        self._execute_with_connection(
                            conn,
                            "INSERT INTO claims_fts(claims_fts) VALUES ('delete-all')",
                        )
                    except sqlite3.Error as sqlite_err:
                        logging.warning("claims_fts table missing during rebuild; recreating. Error: %s", sqlite_err)
                        self._execute_with_connection(
                            conn,
                            """
                            CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
                                claim_text,
                                content='Claims',
                                content_rowid='id'
                            )
                            """,
                        )
                        self._execute_with_connection(
                            conn,
                            "INSERT INTO claims_fts(claims_fts) VALUES ('delete-all')",
                        )
                    self._execute_with_connection(
                        conn,
                        "INSERT INTO claims_fts(rowid, claim_text) SELECT id, claim_text FROM Claims WHERE deleted = 0",
                    )
                    count_row = self._fetchone_with_connection(
                        conn,
                        "SELECT COUNT(*) AS total FROM claims_fts",
                    )
                    return int(count_row.get("total", 0)) if count_row else 0
                elif self.backend_type == BackendType.POSTGRESQL:
                    backend = self.backend
                    backend.create_fts_table(
                        table_name="claims_fts",
                        source_table="claims",
                        columns=["claim_text"],
                        connection=conn,
                    )
                    rebuild_query = (
                        "UPDATE claims "
                        "SET claims_fts_tsv = CASE "
                        "WHEN deleted = 0 THEN to_tsvector('english', coalesce(claim_text, '')) "
                        "ELSE NULL END"
                    )
                    self._execute_with_connection(conn, rebuild_query)
                    count_row = self._fetchone_with_connection(
                        conn,
                        "SELECT COUNT(*) AS total FROM claims WHERE deleted = 0",
                    )
                    return int(count_row.get("total", 0)) if count_row else 0
                else:
                    raise NotImplementedError(
                        f"Claims FTS rebuild not implemented for backend {self.backend_type}"
                    )
        except sqlite3.Error as exc:
            logging.error(f"Failed to rebuild claims_fts: {exc}", exc_info=True)
            raise DatabaseError(f"Failed to rebuild claims_fts: {exc}") from exc
        except BackendDatabaseError as exc:
            logging.error(f"Failed to rebuild claims_fts (backend): {exc}", exc_info=True)
            raise DatabaseError(f"Failed to rebuild claims_fts: {exc}") from exc

    def search_claims(
        self,
        query: str,
        *,
        limit: int = 20,
        fallback_to_like: bool = True
    ) -> List[Dict[str, Any]]:
        """Search claims using the configured backend."""
        cleaned_query = (query or "").strip()
        if not cleaned_query:
            return []
        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError):
            limit = 20
        results: List[Dict[str, Any]] = []
        try:
            with self.transaction() as conn:
                if self.backend_type == BackendType.SQLITE:
                    # Defensive: ensure the FTS index reflects current Claims content.
                    # In some environments, FTS triggers may not have been applied yet
                    # (e.g., freshly created DBs in tests). A lightweight rebuild ensures
                    # correctness for subsequent MATCH queries.
                    try:
                        conn.execute("INSERT INTO claims_fts(claims_fts) VALUES('rebuild')")
                    except sqlite3.Error:
                        pass
                    sql = (
                        "SELECT c.id, c.media_id, c.chunk_index, c.claim_text, "
                        "       bm25(claims_fts) AS relevance_score "
                        "FROM claims_fts JOIN Claims c ON claims_fts.rowid = c.id "
                        "WHERE claims_fts MATCH ? AND c.deleted = 0 "
                        "ORDER BY relevance_score ASC LIMIT ?"
                    )
                    rows = self._fetchall_with_connection(conn, sql, (cleaned_query, limit))
                    results.extend(dict(row) for row in rows)
                elif self.backend_type == BackendType.POSTGRESQL:
                    tsquery = FTSQueryTranslator.normalize_query(cleaned_query, 'postgresql')
                    if tsquery:
                        sql = (
                            "SELECT c.id, c.media_id, c.chunk_index, c.claim_text, "
                            "       ts_rank(c.claims_fts_tsv, to_tsquery('english', ?)) AS relevance_score "
                            "FROM claims c "
                            "WHERE c.deleted IS FALSE "
                            "  AND c.claims_fts_tsv @@ to_tsquery('english', ?) "
                            "ORDER BY relevance_score DESC LIMIT ?"
                        )
                        rows = self._fetchall_with_connection(conn, sql, (tsquery, tsquery, limit))
                        results.extend(dict(row) for row in rows)
                else:
                    raise NotImplementedError(
                        f"Claims search not implemented for backend {self.backend_type}"
                    )

                if fallback_to_like and not results:
                    like_pattern = f"%{cleaned_query}%"
                    if self.backend_type == BackendType.POSTGRESQL:
                        like_sql = (
                            "SELECT id, media_id, chunk_index, claim_text "
                            "FROM claims WHERE deleted IS FALSE AND claim_text ILIKE ? LIMIT ?"
                        )
                    else:
                        like_sql = (
                            "SELECT id, media_id, chunk_index, claim_text "
                            "FROM Claims WHERE deleted = 0 AND claim_text LIKE ? LIMIT ?"
                        )
                    fallback_rows = self._fetchall_with_connection(conn, like_sql, (like_pattern, limit))
                    for row in fallback_rows:
                        row_dict = dict(row)
                        row_dict.setdefault('relevance_score', 0.0)
                        results.append(row_dict)
        except Exception as exc:
            logging.error("Failed to search claims: %s", exc, exc_info=True)
            return []
        return results

    # --- Backwards Compatibility Helpers ---
    def initialize_db(self):
        """
        Backwards-compatibility wrapper for legacy tests/consumers.

        Historically, callers invoked `initialize_db()` after constructing the
        database. The current implementation initializes the schema during
        `__init__`. This method simply re-validates (idempotent) schema state
        and returns self, preserving older calling patterns.

        Returns:
            MediaDatabase: self, to allow call-chaining in legacy code.
        """
        try:
            self._initialize_schema()
        except Exception as e:
            # Re-raise as DatabaseError for consistent error semantics
            raise DatabaseError(f"Database initialization failed: {e}") from e
        return self

    def _generate_uuid(self) -> str:
        """
        Internal helper to generate a new UUID string.

        Returns:
            str: A unique UUID version 4 string.
        """
        return str(uuid.uuid4())

    def _get_next_version(self, conn: sqlite3.Connection, table: str, id_col: str, id_val: Any) -> Optional[Tuple[int, int]]:
        """
        Internal helper to get the current and next sync version for a record.

        Fetches the current 'version' column value for a given record and
        returns it along with the incremented next version number. Used for
        optimistic concurrency checks during updates.

        Args:
            conn (sqlite3.Connection): The database connection.
            table (str): The table name.
            id_col (str): The name of the identifier column (e.g., 'id', 'uuid').
            id_val (Any): The value of the identifier.

        Returns:
            Optional[Tuple[int, int]]: A tuple containing (current_version, next_version)
                                       if the record exists and has an integer version,
                                       otherwise None.

        Raises:
            DatabaseError: If the database query fails.
        """
        try:
            cursor = conn.execute(f"SELECT version FROM {table} WHERE {id_col} = ? AND deleted = 0", (id_val,))
            result = cursor.fetchone()
            if result:
                current_version = result['version']
                if isinstance(current_version, int):
                    return current_version, current_version + 1
                else:
                    logging.error(f"Invalid non-integer version '{current_version}' found for {table} {id_col}={id_val}")
                    return None
        except sqlite3.Error as e:
            logging.error(f"Database error fetching version for {table} {id_col}={id_val}: {e}")
            raise DatabaseError(f"Failed to fetch current version: {e}") from e
        return None

    # --- Internal Sync Logging Helper ---
    def _log_sync_event(self, conn: sqlite3.Connection, entity: str, entity_uuid: str, operation: str, version: int, payload: Optional[Dict] = None):
        """
        Internal helper to insert a record into the sync_log table.

        This should be called within an active transaction context after a
        successful data modification (insert, update, delete, link, unlink).

        Args:
            conn (sqlite3.Connection): The database connection (within transaction).
            entity (str): The name of the entity/table being changed (e.g., "Media").
            entity_uuid (str): The UUID of the entity affected. For links/unlinks,
                               this might be a composite identifier.
            operation (str): The type of operation ('create', 'update', 'delete',
                             'link', 'unlink').
            version (int): The new sync version number of the entity after the change.
            payload (Optional[Dict]): A dictionary containing relevant data about
                                      the change (e.g., the updated row). Sensitive
                                      or large fields like 'vector_embedding' are
                                      automatically excluded. Defaults to None.

        Raises:
            DatabaseError: If the sync log insertion fails.
        """
        if not entity or not entity_uuid or not operation:
            logging.error("Sync log attempt with missing entity, uuid, or operation.")
            return

        current_time = self._get_current_utc_timestamp_str()  # Generate timestamp here
        client_id = self.client_id
        scope_org_id, scope_team_id = self._resolve_scope_ids()

        # Exclude potentially large/binary fields from default payload logging
        if payload:
            payload = payload.copy()  # Avoid modifying the original dict
            if 'vector_embedding' in payload:
                del payload['vector_embedding']
            # Normalise non-JSON-native types (e.g., datetimes) to strings
            for k, v in list(payload.items()):
                try:
                    from datetime import datetime
                    if isinstance(v, datetime):
                        payload[k] = v.isoformat()
                except Exception:
                    pass

        payload_json = json.dumps(payload, separators=(',', ':')) if payload else None  # Compact JSON

        try:
            if self.backend_type == BackendType.SQLITE:
                conn.execute(
                    """
                    INSERT INTO sync_log (entity, entity_uuid, operation, timestamp, client_id, version, org_id, team_id, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (entity, entity_uuid, operation, current_time, client_id, version, scope_org_id, scope_team_id, payload_json),
                )
            else:
                self._execute_with_connection(
                    conn,
                    """
                    INSERT INTO sync_log (entity, entity_uuid, operation, timestamp, client_id, version, org_id, team_id, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (entity, entity_uuid, operation, current_time, client_id, version, scope_org_id, scope_team_id, payload_json),
                )
            logging.debug(
                f"Logged sync event: {entity} {entity_uuid} {operation} v{version} at {current_time}"
            )
        except Exception as e:
            logging.error(
                f"Failed to insert sync log event for {entity} {entity_uuid}: {e}", exc_info=True
            )
            raise DatabaseError(f"Failed to log sync event: {e}") from e

    # --- NEW: Internal FTS Helper Methods ---
    def _update_fts_media(self, conn: sqlite3.Connection, media_id: int, title: str, content: Optional[str]):
        """
        Internal helper to update or insert into the media_fts table.

        Uses INSERT OR REPLACE to handle both creating new FTS entries and
        updating existing ones based on the Media.id (rowid). Should be called
        within a transaction after Media insert/update.

        Args:
            conn (sqlite3.Connection): The database connection (within transaction).
            media_id (int): The ID (rowid) of the Media item.
            title (str): The title of the media.
            content (Optional[str]): The content of the media. Empty string if None.

        Raises:
            DatabaseError: If the FTS update fails.
        """
        if self.backend_type == BackendType.SQLITE:
            content = content or ""
            # Optional: append synonyms expansions to content for index-time synonyming
            try:
                from tldw_Server_API.app.core.RAG.rag_service.synonyms_registry import get_corpus_synonyms  # type: ignore
                corpus = os.getenv("DEFAULT_FTS_CORPUS", "").strip() or None
                syn_map = get_corpus_synonyms(corpus)
            except Exception:
                syn_map = {}
            expanded_terms: list[str] = []
            if syn_map:
                try:
                    import re as _re
                    tokens = set([t for t in _re.split(r"\W+", f"{title} {content}".lower()) if t])
                    for t in tokens:
                        al = syn_map.get(t)
                        if al:
                            expanded_terms.extend(a for a in al if a)
                    # Cap expansion to avoid index bloat
                    max_terms = int(os.getenv("FTS_SYNONYM_EXPANSION_LIMIT", "200") or 200)
                    if len(expanded_terms) > max_terms:
                        expanded_terms = expanded_terms[:max_terms]
                except Exception:
                    expanded_terms = []
            exp_str = (" " + " ".join(expanded_terms)) if expanded_terms else ""
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO media_fts (rowid, title, content) VALUES (?, ?, ?)",
                    (media_id, title, f"{content}{exp_str}"),
                )
                logging.debug("Updated SQLite FTS entry for Media ID %s", media_id)
            except sqlite3.Error as e:
                logging.error("Failed to update media_fts for Media ID %s: %s", media_id, e, exc_info=True)
                raise DatabaseError(f"Failed to update FTS for Media ID {media_id}: {e}") from e
            return

        if self.backend_type == BackendType.POSTGRESQL:
            # Use fielded weights: title=A (highest), content=C (lower)
            try:
                enable_syn = str(os.getenv("PG_FTS_ENABLE_SYNONYMS", "false")).lower() in {"1","true","yes","on","y"}
                if enable_syn:
                    # Best-effort create synonyms support
                    try:
                        ensure_fn = getattr(self.backend, 'ensure_synonyms_support', None)
                        if callable(ensure_fn):
                            ensure_fn(connection=conn)
                    except Exception as _syn_err:
                        logging.debug(f"Synonyms support ensure failed (non-fatal): {_syn_err}")
                if enable_syn:
                    sql = (
                        "UPDATE media SET media_fts_tsv = CASE "
                        "WHEN deleted IS FALSE THEN "
                        " setweight(to_tsvector('english', synonyms_expand(coalesce(title, ''))),'A') || "
                        " setweight(to_tsvector('english', synonyms_expand(coalesce(content, ''))),'C') "
                        "ELSE NULL END WHERE id = ?"
                    )
                else:
                    sql = (
                        "UPDATE media SET media_fts_tsv = CASE "
                        "WHEN deleted IS FALSE THEN "
                        " setweight(to_tsvector('english', coalesce(title, '')),'A') || "
                        " setweight(to_tsvector('english', coalesce(content, '')),'C') "
                        "ELSE NULL END WHERE id = ?"
                    )
                self._execute_with_connection(conn, sql, (media_id,))
                logging.debug("Updated PostgreSQL FTS vector for Media ID %s", media_id)
            except DatabaseError as exc:
                logging.error("Failed to update PostgreSQL FTS for Media ID %s: %s", media_id, exc, exc_info=True)
                raise
            return

    def _delete_fts_media(self, conn: sqlite3.Connection, media_id: int):
        """
        Internal helper to delete from the media_fts table.

        Deletes the FTS entry corresponding to the given Media ID (rowid).
        Should be called within a transaction after Media soft delete or
        permanent delete. Ignores if the entry doesn't exist.

        Args:
            conn (sqlite3.Connection): The database connection (within transaction).
            media_id (int): The ID (rowid) of the Media item whose FTS entry to delete.

        Raises:
            DatabaseError: If the FTS deletion fails (excluding 'not found').
        """
        if self.backend_type == BackendType.SQLITE:
            try:
                conn.execute("DELETE FROM media_fts WHERE rowid = ?", (media_id,))
                logging.debug("Deleted SQLite FTS entry for Media ID %s", media_id)
            except sqlite3.Error as e:
                logging.error("Failed to delete from media_fts for Media ID %s: %s", media_id, e, exc_info=True)
                raise DatabaseError(f"Failed to delete FTS for Media ID {media_id}: {e}") from e
            return

        if self.backend_type == BackendType.POSTGRESQL:
            try:
                self._execute_with_connection(
                    conn,
                    "UPDATE media SET media_fts_tsv = NULL WHERE id = ?",
                    (media_id,),
                )
                logging.debug("Cleared PostgreSQL FTS vector for Media ID %s", media_id)
            except DatabaseError as exc:
                logging.error("Failed to clear PostgreSQL FTS for Media ID %s: %s", media_id, exc, exc_info=True)
                raise
            return

    def _update_fts_keyword(self, conn: sqlite3.Connection, keyword_id: int, keyword: str):
        """
        Internal helper to update or insert into the keyword_fts table.

        Uses INSERT OR REPLACE based on the Keywords.id (rowid). Should be
        called within a transaction after Keywords insert/update/undelete.

        Args:
            conn (sqlite3.Connection): The database connection (within transaction).
            keyword_id (int): The ID (rowid) of the Keywords item.
            keyword (str): The keyword text.

        Raises:
            DatabaseError: If the FTS update fails.
        """
        if self.backend_type == BackendType.SQLITE:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO keyword_fts (rowid, keyword) VALUES (?, ?)",
                    (keyword_id, keyword),
                )
                logging.debug("Updated SQLite FTS entry for Keyword ID %s", keyword_id)
            except sqlite3.Error as e:
                logging.error("Failed to update keyword_fts for Keyword ID %s: %s", keyword_id, e, exc_info=True)
                raise DatabaseError(f"Failed to update FTS for Keyword ID {keyword_id}: {e}") from e
            return

        if self.backend_type == BackendType.POSTGRESQL:
            try:
                self._execute_with_connection(
                    conn,
                    (
                        "UPDATE keywords SET keyword_fts_tsv = CASE "
                        "WHEN deleted IS FALSE THEN to_tsvector('english', coalesce(keyword, '')) "
                        "ELSE NULL END WHERE id = ?"
                    ),
                    (keyword_id,),
                )
                logging.debug("Updated PostgreSQL FTS vector for Keyword ID %s", keyword_id)
            except DatabaseError as exc:
                logging.error("Failed to update PostgreSQL FTS for Keyword ID %s: %s", keyword_id, exc, exc_info=True)
                raise
            return

    def _delete_fts_keyword(self, conn: sqlite3.Connection, keyword_id: int):
        """
        Internal helper to delete from the keyword_fts table.

        Deletes the FTS entry corresponding to the given Keyword ID (rowid).
        Should be called within a transaction after Keyword soft delete.
        Ignores if the entry doesn't exist.

        Args:
            conn (sqlite3.Connection): The database connection (within transaction).
            keyword_id (int): The ID (rowid) of the Keyword whose FTS entry to delete.

        Raises:
            DatabaseError: If the FTS deletion fails (excluding 'not found').
        """
        if self.backend_type == BackendType.SQLITE:
            try:
                conn.execute("DELETE FROM keyword_fts WHERE rowid = ?", (keyword_id,))
                logging.debug("Deleted SQLite FTS entry for Keyword ID %s", keyword_id)
            except sqlite3.Error as e:
                logging.error("Failed to delete from keyword_fts for Keyword ID %s: %s", keyword_id, e, exc_info=True)
                raise DatabaseError(f"Failed to delete FTS for Keyword ID {keyword_id}: {e}") from e
            return

        if self.backend_type == BackendType.POSTGRESQL:
            try:
                self._execute_with_connection(
                    conn,
                    "UPDATE keywords SET keyword_fts_tsv = NULL WHERE id = ?",
                    (keyword_id,),
                )
                logging.debug("Cleared PostgreSQL FTS vector for Keyword ID %s", keyword_id)
            except DatabaseError as exc:
                logging.error("Failed to clear PostgreSQL FTS for Keyword ID %s: %s", keyword_id, exc, exc_info=True)
                raise
            return

        # In Media_DB_v2.py (within the Database class)

        # Add 'media_ids_filter' to the method signature
        # from typing import List, Tuple, Dict, Any, Optional, Union # Ensure Union is imported

    def search_media_db(
        self,
        search_query: Optional[str], # Main text for FTS/LIKE (can be pre-formatted for exact phrase)
        search_fields: Optional[List[str]] = None,
        media_types: Optional[List[str]] = None,
        date_range: Optional[Dict[str, datetime]] = None, # Expects datetime objects
        must_have_keywords: Optional[List[str]] = None,
        must_not_have_keywords: Optional[List[str]] = None,
        sort_by: Optional[str] = "last_modified_desc", # Default sort order
        # boost_fields: Optional[Dict[str, float]] = None, # Future: for FTS boosting
        media_ids_filter: Optional[List[Union[int, str]]] = None,
        page: int = 1,
        results_per_page: int = 20,
        include_trash: bool = False,
        include_deleted: bool = False
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Searches media items based on a variety of criteria, supporting text search,
        filtering, and sorting.

        The method combines Full-Text Search (FTS) for 'title' and 'content' fields
        with LIKE queries for 'author' and 'type' fields. It also allows filtering
        by media types, date ranges, required keywords, excluded keywords, and
        specific media IDs. Results are paginated and can optionally include
        items marked as trash or soft-deleted.

        Args:
            search_query (Optional[str]): The primary text string for searching.
                If `search_fields` include 'title' or 'content', this query is
                matched against the FTS index. It can be pre-formatted for exact
                phrases (e.g., "\"exact phrase\""). For 'author' or 'type' in
                `search_fields`, it's used in a LIKE '%query%' match.
            search_fields (Optional[List[str]]): A list of fields to apply the
                `search_query` against. Valid fields: 'title', 'content' (FTS),
                'author', 'type' (LIKE). Defaults to ['title', 'content'] if
                `search_query` is provided.
            media_types (Optional[List[str]]): A list of media type strings
                (e.g., ['video', 'pdf']) to filter results. Only items matching
                one of these types will be returned.
            date_range (Optional[Dict[str, datetime]]): A dictionary to filter
                media items by their ingestion date. Expected keys:
                - 'start_date' (datetime): Items ingested on or after this date.
                - 'end_date' (datetime): Items ingested on or before this date.
                Both keys are optional. Expects datetime objects.
            must_have_keywords (Optional[List[str]]): A list of keyword strings.
                Media items must be associated with *all* these keywords to be
                included. Case-insensitive.
            must_not_have_keywords (Optional[List[str]]): A list of keyword strings.
                Media items associated with *any* of these keywords will be
                excluded. Case-insensitive.
            sort_by (Optional[str]): The criteria for sorting results.
                Available options:
                - 'relevance': (Default if FTS is active) Sorts by FTS match score.
                - 'last_modified_desc': (Default otherwise) Newest items first based on last modification.
                - 'last_modified_asc': Oldest items first based on last modification.
                - 'date_desc': Newest items first based on ingestion date.
                - 'date_asc': Oldest items first based on ingestion date.
                - 'title_asc': Sort by title alphabetically (A-Z).
                - 'title_desc': Sort by title reverse alphabetically (Z-A).
                Defaults to 'last_modified_desc'.
            media_ids_filter (Optional[List[Union[int, str]]]): A list of media IDs
                (integer) or UUIDs (string) to restrict the search to. If provided,
                only media items with these IDs/UUIDs will be considered.
            page (int): The page number for pagination (1-based). Defaults to 1.
            results_per_page (int): Number of results per page. Defaults to 20.
            include_trash (bool): If True, include items marked as trash
                (Media.is_trash = 1). Defaults to False.
            include_deleted (bool): If True, include items marked as soft-deleted
                (Media.deleted = 1). Defaults to False.

        Returns:
            Tuple[List[Dict[str, Any]], int]: A tuple containing:
                - results_list (List[Dict[str, Any]]): A list of dictionaries,
                  each representing a matching media item for the current page.
                  Includes standard media fields. If FTS was active and sort_by
                  was 'relevance', a 'relevance_score' key may also be present.
                - total_matches (int): The total number of items matching all
                  criteria across all pages.

        Raises:
            ValueError: If `page` or `results_per_page` are less than 1,
                        if `media_ids_filter` contains invalid types,
                        if `media_types` contains non-string elements,
                        or if `date_range` values are not datetime objects.
            DatabaseError: If the FTS table is missing, or for other general
                           database query errors.
        """
        if page < 1:
            raise ValueError("Page number must be 1 or greater")
        if results_per_page < 1:
            raise ValueError("Results per page must be 1 or greater")

        if search_query and not search_fields:
            search_fields = ["title", "content"] # Default fields for search_query
        elif not search_fields: # Ensure search_fields is a list even if empty
            search_fields = []

        valid_text_search_fields = {"title", "content", "author", "type"}
        sanitized_text_search_fields = [f for f in search_fields if f in valid_text_search_fields]

        # Optional hardening: clamp very long FTS inputs to avoid pathological queries
        if search_query:
            try:
                import os as _os
                max_chars = int((_os.getenv("FTS_QUERY_MAX_CHARS") or "1000").strip() or 1000)
            except Exception:
                max_chars = 1000
            if isinstance(search_query, str) and len(search_query) > max_chars:
                logging.warning(
                    "Clamping search_query from %s to %s chars for FTS hardening",
                    len(search_query),
                    max_chars,
                )
                search_query = search_query[:max_chars]

        offset = (page - 1) * results_per_page
        # Define base SELECT, FROM clauses
        base_select_parts = ["m.id", "m.uuid", "m.url", "m.title", "m.content", "m.type", "m.author", "m.ingestion_date",
                             "m.transcription_model", "m.is_trash", "m.trash_date", "m.chunking_status",
                             "m.vector_processing", "m.content_hash", "m.last_modified", "m.version",
                             "m.client_id", "m.deleted"]
        count_select = "COUNT(DISTINCT m.id)"
        base_from = "FROM Media m"
        joins = []
        conditions = []
        params = []
        fts_condition_index: Optional[int] = None
        fts_param_index: Optional[int] = None
        fts_join_added = False
        fts_relevance_added = False

        fts_select_params: List[Any] = []
        fts_condition_params: List[Any] = []
        postgres_tsquery: Optional[str] = None

        # Basic filters
        if not include_deleted:
            conditions.append("m.deleted = 0")
        if not include_trash:
            conditions.append("m.is_trash = 0")

        # Media IDs Filter
        if media_ids_filter:
            if not all(isinstance(mid, (int, str)) for mid in media_ids_filter):
                raise ValueError("media_ids_filter must be a list of ints or strings.")
            int_ids = [mid for mid in media_ids_filter if isinstance(mid, int)]
            uuid_ids = [mid for mid in media_ids_filter if isinstance(mid, str) and mid]
            if int_ids:
                id_placeholders = ','.join('?' * len(int_ids))
                conditions.append(f"m.id IN ({id_placeholders})")
                params.extend(int_ids)
            if uuid_ids:
                uuid_placeholders = ','.join('?' * len(uuid_ids))
                conditions.append(f"m.uuid IN ({uuid_placeholders})")
                params.extend(uuid_ids)

        # Media Types Filter
        if media_types:
            if not all(isinstance(mt, str) for mt in media_types):
                raise ValueError("media_types must be a list of strings.")
            if media_types:
                type_placeholders = ','.join('?' * len(media_types))
                conditions.append(f"m.type IN ({type_placeholders})")
                params.extend(media_types)

        # Date Range Filter (m.ingestion_date is DATETIME)
        # SQLite can compare ISO8601 date strings correctly.
        if date_range:
            start_date = date_range.get('start_date')
            end_date = date_range.get('end_date')
            if start_date:
                if not isinstance(start_date, datetime):
                    # Should ideally be caught by Pydantic, but defensive check
                    raise ValueError("date_range['start_date'] must be a datetime object.")
                conditions.append("m.ingestion_date >= ?")
                params.append(start_date.isoformat())
            if end_date:
                if not isinstance(end_date, datetime):
                    raise ValueError("date_range['end_date'] must be a datetime object.")
                # For 'less than or equal to the end of the day' if end_date is just a date:
                # end_date_inclusive = datetime.combine(end_date, datetime.max.time())
                # params.append(end_date_inclusive.isoformat())
                # Or simply use the provided datetime as is
                conditions.append("m.ingestion_date <= ?")
                params.append(end_date.isoformat())


        # Must Have Keywords
        cleaned_must_have = [k.strip().lower() for k in must_have_keywords if k and k.strip()] if must_have_keywords else []
        if cleaned_must_have:
            kw_mh_placeholders = ','.join('?' * len(cleaned_must_have))
            # Subquery to ensure media_id is linked to ALL provided keywords
            conditions.append(f"""
                (SELECT COUNT(DISTINCT k_mh.id)
                 FROM MediaKeywords mk_mh
                 JOIN Keywords k_mh ON mk_mh.keyword_id = k_mh.id
                 WHERE mk_mh.media_id = m.id AND k_mh.deleted = 0 AND LOWER(k_mh.keyword) IN ({kw_mh_placeholders})
                ) = ?
            """)
            params.extend(cleaned_must_have)
            params.append(len(cleaned_must_have))

        # Must Not Have Keywords
        cleaned_must_not_have = [k.strip().lower() for k in must_not_have_keywords if k and k.strip()] if must_not_have_keywords else []
        if cleaned_must_not_have:
            kw_mnh_placeholders = ','.join('?' * len(cleaned_must_not_have))
            conditions.append(f"""
                NOT EXISTS (
                    SELECT 1
                    FROM MediaKeywords mk_mnh
                    JOIN Keywords k_mnh ON mk_mnh.keyword_id = k_mnh.id
                    WHERE mk_mnh.media_id = m.id AND k_mnh.deleted = 0 AND LOWER(k_mnh.keyword) IN ({kw_mnh_placeholders})
                )
            """)
            params.extend(cleaned_must_not_have)

        # Text Search Logic (FTS or LIKE)
        fts_search_active = False
        if search_query:  # search_query is the actual text to match (e.g., "my query" or "\"exact phrase\"")
            like_conditions = []
            like_params = []

            like_search_query = search_query.strip('"') if search_query.startswith('"') and search_query.endswith('"') else search_query

            if any(f in sanitized_text_search_fields for f in ["title", "content"]):
                fts_search_active = True
                fts_query_parts: List[str] = []

                if len(search_query) <= 2 and not (search_query.startswith('"') and search_query.endswith('"')):
                    fts_query_parts.append(f"{search_query}*")
                    if search_query.lower() != search_query:
                        fts_query_parts.append(f"{search_query.lower()}*")
                else:
                    fts_query_parts.append(search_query)
                    if not (search_query.startswith('"') and search_query.endswith('"')) and search_query.lower() != search_query:
                        fts_query_parts.append(search_query.lower())

                combined_fts_query = " OR ".join(fts_query_parts)
                logging.debug(f"Combined FTS query: '{combined_fts_query}'")
                logging.info(f"Search using FTS with query parts: {fts_query_parts}")

                if self.backend_type == BackendType.SQLITE:
                    if not any("media_fts fts" in j_item for j_item in joins):
                        joins.append("JOIN media_fts fts ON fts.rowid = m.id")
                        fts_join_added = True
                    # Use table name for MATCH for SQLite FTS5 compatibility
                    conditions.append("media_fts MATCH ?")
                    params.append(combined_fts_query)
                    fts_condition_index = len(conditions) - 1
                    fts_param_index = len(params) - 1
                elif self.backend_type == BackendType.POSTGRESQL:
                    postgres_tsquery = FTSQueryTranslator.normalize_query(combined_fts_query, 'postgresql')
                    if postgres_tsquery:
                        conditions.append("m.media_fts_tsv @@ to_tsquery('english', ?)")
                        fts_condition_params.append(postgres_tsquery)
                        fts_condition_index = len(conditions) - 1
                    else:
                        logging.debug("PostgreSQL tsquery normalization produced empty output; falling back to LIKE-only search.")
                        fts_search_active = False
                else:
                    logging.warning("FTS requested for unsupported backend %s", self.backend_type)
                    fts_search_active = False

                title_content_like_parts: List[str] = []
                for field in ["title", "content"]:
                    if field in sanitized_text_search_fields:
                        column = f"m.{field}"
                        self._append_case_insensitive_like(
                            title_content_like_parts,
                            like_params,
                            column,
                            f"%{like_search_query}%",
                        )
                        if len(like_search_query) <= 2 and not (search_query.startswith('"') and search_query.endswith('"')):
                            self._append_case_insensitive_like(
                                title_content_like_parts,
                                like_params,
                                column,
                                f"%{like_search_query}",
                            )
                if title_content_like_parts:
                    like_conditions.append(f"({' OR '.join(title_content_like_parts)})")

            like_fields_to_search = [f for f in sanitized_text_search_fields if f in ["author", "type"]]
            if like_fields_to_search:
                like_parts: List[str] = []
                for field in like_fields_to_search:
                    if field == "type" and media_types:
                        logging.debug("LIKE search on 'type' skipped due to active 'media_types' filter.")
                        continue

                    self._append_case_insensitive_like(
                        like_parts,
                        like_params,
                        f"m.{field}",
                        f"%{like_search_query}%",
                    )
                    if len(like_search_query) <= 2 and not (search_query.startswith('"') and search_query.endswith('"')):
                        self._append_case_insensitive_like(
                            like_parts,
                            like_params,
                            f"m.{field}",
                            f"%{like_search_query}",
                        )
                if like_parts:
                    like_conditions.append(f"({' OR '.join(like_parts)})")

            if like_conditions:
                logging.info(f"Search using LIKE with patterns: {like_params}")
                conditions.append(f"({' OR '.join(like_conditions)})")
                params.extend(like_params)

        elif sanitized_text_search_fields:
            conditions.append("1=1")


        # Order By Clause
        order_by_clause_str = ""
        default_order_by = "ORDER BY m.last_modified DESC, m.id DESC"

        if fts_search_active and (sort_by == "relevance" or not sort_by):
            # Ensure relevance score is available for ordering.
            if self.backend_type == BackendType.SQLITE:
                # Use bm25 for consistent relevance and let lower scores rank higher
                if not any("AS relevance_score" in part for part in base_select_parts):
                    # bm25() expects the FTS5 table name, not the alias
                    base_select_parts.append("bm25(media_fts) AS relevance_score")
                    fts_relevance_added = True
                order_by_clause_str = "ORDER BY relevance_score ASC, m.last_modified DESC, m.id DESC"
            elif self.backend_type == BackendType.POSTGRESQL and postgres_tsquery:
                if not any("relevance_score" in part for part in base_select_parts):
                    base_select_parts.append("ts_rank(m.media_fts_tsv, to_tsquery('english', ?)) AS relevance_score")
                    fts_select_params.append(postgres_tsquery)
                    fts_relevance_added = True
                order_by_clause_str = "ORDER BY relevance_score DESC, m.last_modified DESC, m.id DESC"

        else:
            if sort_by == "date_desc":
                order_by_clause_str = "ORDER BY m.ingestion_date DESC, m.last_modified DESC, m.id DESC"
            elif sort_by == "date_asc":
                order_by_clause_str = "ORDER BY m.ingestion_date ASC, m.last_modified ASC, m.id ASC"
            elif sort_by == "title_asc":
                if self.backend_type == BackendType.POSTGRESQL:
                    order_by_clause_str = "ORDER BY LOWER(m.title) ASC, m.title ASC, m.id ASC"
                else:
                    order_by_clause_str = "ORDER BY m.title ASC COLLATE NOCASE, m.id ASC"
            elif sort_by == "title_desc":
                if self.backend_type == BackendType.POSTGRESQL:
                    order_by_clause_str = "ORDER BY LOWER(m.title) DESC, m.title DESC, m.id DESC"
                else:
                    order_by_clause_str = "ORDER BY m.title DESC COLLATE NOCASE, m.id DESC"
            elif sort_by == "last_modified_asc":
                order_by_clause_str = "ORDER BY m.last_modified ASC, m.id ASC"
            elif sort_by == "last_modified_desc": # Also default
                order_by_clause_str = default_order_by
            else: # Unrecognized sort_by or default
                order_by_clause_str = default_order_by

        # Finalize SELECT statement
        final_select_stmt = f"SELECT DISTINCT {', '.join(base_select_parts)}"

        # --- Construct and Execute Queries ---
        join_clause = " ".join(list(dict.fromkeys(joins))) # Unique joins
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        try:
            # Count Query
            count_sql = f"SELECT {count_select} {base_from} {join_clause} {where_clause}"
            logging.debug(f"Search Count SQL ({self.db_path_str}): {count_sql}")
            if self.backend_type == BackendType.POSTGRESQL:
                count_params_seq = list(fts_condition_params) + list(params)
            else:
                count_params_seq = list(params)
            logging.debug(f"Search Count Params: {count_params_seq}")

            try:
                count_cursor = self.execute_query(count_sql, tuple(count_params_seq))
                total_matches_row = count_cursor.fetchone()
                if isinstance(total_matches_row, dict):
                    total_matches = (
                        total_matches_row.get('count')
                        or total_matches_row.get('total')
                        or next(iter(total_matches_row.values()))
                        or 0
                    )
                else:
                    total_matches = total_matches_row[0] if total_matches_row else 0
                logging.info(f"Search query '{search_query}' found {total_matches} total matches")
            except sqlite3.OperationalError as e:
                if (
                    self.backend_type == BackendType.SQLITE
                    and "unable to use function MATCH in the requested context" in str(e)
                    and fts_condition_index is not None
                ):
                    logging.warning(f"FTS MATCH error, falling back to LIKE-only search: {e}")
                    fallback_conditions = [
                        condition
                        for idx, condition in enumerate(conditions)
                        if idx != fts_condition_index
                    ]
                    fallback_params = list(params)
                    if fts_param_index is not None and 0 <= fts_param_index < len(fallback_params):
                        fallback_params.pop(fts_param_index)
                    fallback_joins = [join for join in joins if "media_fts fts" not in join]

                    if not fallback_conditions and not fallback_params and not fallback_joins and not search_query:
                        logging.warning("No valid search conditions after removing FTS MATCH, returning empty results")
                        return [], 0

                    if fts_relevance_added:
                        base_select_parts[:] = [
                            part for part in base_select_parts if "relevance_score" not in part
                        ]
                        order_by_clause_str = default_order_by
                        fts_relevance_added = False
                    final_select_stmt = f"SELECT DISTINCT {', '.join(base_select_parts)}"

                    conditions[:] = fallback_conditions
                    params[:] = fallback_params
                    joins[:] = fallback_joins
                    fts_condition_index = None
                    fts_param_index = None
                    fts_join_added = False
                    join_clause = " ".join(list(dict.fromkeys(joins)))
                    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
                    count_sql = f"SELECT {count_select} {base_from} {join_clause} {where_clause}"
                    logging.debug(f"Fallback Count SQL ({self.db_path_str}): {count_sql}")
                    count_params_seq = list(params)
                    logging.debug(f"Fallback Count Params: {count_params_seq}")
                    count_cursor = self.execute_query(count_sql, tuple(count_params_seq))
                    total_matches_row = count_cursor.fetchone()
                    if isinstance(total_matches_row, dict):
                        total_matches = (
                            total_matches_row.get('count')
                            or total_matches_row.get('total')
                            or next(iter(total_matches_row.values()))
                            or 0
                        )
                    else:
                        total_matches = total_matches_row[0] if total_matches_row else 0
                    logging.info(f"Fallback search query '{search_query}' found {total_matches} total matches")
                else:
                    raise

            results_list = []
            if total_matches > 0 and offset < total_matches:
                # Results Query
                results_sql = f"{final_select_stmt} {base_from} {join_clause} {where_clause} {order_by_clause_str} LIMIT ? OFFSET ?"
                if self.backend_type == BackendType.POSTGRESQL:
                    paginated_params = tuple(list(fts_select_params) + list(fts_condition_params) + list(params) + [results_per_page, offset])
                else:
                    paginated_params = tuple(params + [results_per_page, offset])
                logging.debug(f"Search Results SQL ({self.db_path_str}): {results_sql}")
                logging.debug(f"Search Results Params: {paginated_params}")

                try:
                    results_cursor = self.execute_query(results_sql, paginated_params)
                    results_list = [dict(row) for row in results_cursor.fetchall()]
                except sqlite3.OperationalError as e:
                    # Handle specific FTS MATCH errors in results query
                    if (
                        self.backend_type == BackendType.SQLITE
                        and "unable to use function MATCH in the requested context" in str(e)
                        and fts_condition_index is not None
                    ):
                        logging.warning(f"FTS MATCH error in results query, falling back to LIKE-only search: {e}")
                        fallback_conditions = [
                            condition
                            for idx, condition in enumerate(conditions)
                            if idx != fts_condition_index
                        ]
                        fallback_params = list(params)
                        if fts_param_index is not None and 0 <= fts_param_index < len(fallback_params):
                            fallback_params.pop(fts_param_index)
                        fallback_joins = [join for join in joins if "media_fts fts" not in join]

                        if fts_relevance_added:
                            base_select_parts[:] = [
                                part for part in base_select_parts if "relevance_score" not in part
                            ]
                            order_by_clause_str = default_order_by
                            fts_relevance_added = False

                        conditions[:] = fallback_conditions
                        params[:] = fallback_params
                        joins[:] = fallback_joins
                        fts_condition_index = None
                        fts_param_index = None
                        fts_join_added = False

                        join_clause = " ".join(list(dict.fromkeys(joins)))
                        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
                        final_select_stmt = f"SELECT DISTINCT {', '.join(base_select_parts)}"
                        results_sql = f"{final_select_stmt} {base_from} {join_clause} {where_clause} {order_by_clause_str} LIMIT ? OFFSET ?"
                        paginated_params = tuple(list(params) + [results_per_page, offset])
                        logging.debug(f"Fallback Results SQL ({self.db_path_str}): {results_sql}")
                        logging.debug(f"Fallback Results Params: {paginated_params}")
                        results_cursor = self.execute_query(results_sql, paginated_params)
                        results_list = [dict(row) for row in results_cursor.fetchall()]
                    else:
                        # Re-raise other SQLite errors
                        raise

                # Log the titles of the found items for debugging
                titles = [row.get('title', 'Untitled') for row in results_list]
                logging.info(f"Search results for '{search_query}' (page {page}): {titles}")

            return results_list, total_matches

        except sqlite3.Error as e:
            if "no such table: media_fts" in str(e).lower():
                logging.error(f"FTS table 'media_fts' missing in database '{self.db_path_str}'. Search will fail.")
                raise DatabaseError(f"FTS table 'media_fts' not found in {self.db_path_str}.") from e
            logging.error(f"Database error during media search in '{self.db_path_str}': {e}", exc_info=True)
            raise DatabaseError(f"Failed to search media in {self.db_path_str}: {e}") from e
        except Exception as e:
            logging.error(f"Unexpected error during media search in '{self.db_path_str}': {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred during media search: {e}") from e

    # --- Public Mutating Methods (Modified for Python Sync/FTS Logging) ---

    def search_by_safe_metadata(
        self,
        filters: Optional[List[Dict[str, Any]]] = None,
        match_all: bool = True,
        page: int = 1,
        per_page: int = 20,
        group_by_media: bool = True,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search by fields inside DocumentVersions.safe_metadata and identifiers table.

        - filters: [{field, op, value}] where op in (eq, contains, icontains, startswith, endswith)
        - Known identifier fields (doi, pmid, pmcid, arxiv_id, s2_paper_id) are matched via DocumentVersionIdentifiers.
        - Other fields fallback to LIKE search against the JSON string in dv.safe_metadata.
        - When group_by_media, returns latest matching version per media.
        """
        try:
            offset = (max(1, page) - 1) * per_page
            clauses: List[str] = ["dv.deleted = 0", "m.deleted = 0"]
            params: List[Any] = []
            join_ident = False

            id_fields = {"doi","pmid","pmcid","arxiv_id","s2_paper_id"}
            ops_sql = {
                'eq': lambda col: (f"{col} = ?", lambda v: v),
                'contains': lambda col: (f"{col} LIKE ?", lambda v: f"%{v}%"),
                'icontains': lambda col: (f"LOWER({col}) LIKE ?", lambda v: f"%{str(v).lower()}%"),
                'startswith': lambda col: (f"{col} LIKE ?", lambda v: f"{v}%"),
                'endswith': lambda col: (f"{col} LIKE ?", lambda v: f"%{v}"),
            }

            filter_exprs: List[str] = []
            if filters:
                for flt in filters:
                    field = (flt.get('field') or '').strip()
                    op = (flt.get('op') or 'icontains').lower()
                    val = flt.get('value')
                    if not field or val is None:
                        continue
                    if field in id_fields:
                        join_ident = True
                        col = f"dvi.{field}"
                        sql_tpl, xform = ops_sql.get(op, ops_sql['icontains'])(col)
                        filter_exprs.append(sql_tpl)
                        params.append(xform(val))
                    else:
                        # Fallback LIKE on JSON text
                        if op == 'eq':
                            frag = f'"{field}":"{val}"'
                            filter_exprs.append("dv.safe_metadata LIKE ?")
                            params.append(f"%{frag}%")
                        elif op == 'icontains':
                            filter_exprs.append("LOWER(dv.safe_metadata) LIKE ?")
                            params.append(f"%{str(val).lower()}%")
                        else:
                            filter_exprs.append("dv.safe_metadata LIKE ?")
                            like_val = val
                            if op == 'contains': like_val = f"%{val}%"
                            elif op == 'startswith': like_val = f"{val}%"
                            elif op == 'endswith': like_val = f"%{val}"
                            else: like_val = f"%{val}%"
                            params.append(like_val)

            where_filters = ""
            if filter_exprs:
                join_op = " AND " if match_all else " OR "
                where_filters = f" AND (" + join_op.join(filter_exprs) + ")"

            base_from = "FROM DocumentVersions dv JOIN Media m ON dv.media_id = m.id"
            if join_ident:
                base_from += " LEFT JOIN DocumentVersionIdentifiers dvi ON dvi.dv_id = dv.id"

            # Count
            if group_by_media:
                count_sql = (
                    f"SELECT COUNT(DISTINCT m.id) AS total_count {base_from} "
                    f"WHERE {' AND '.join(clauses)}{where_filters}"
                )
            else:
                count_sql = (
                    f"SELECT COUNT(*) AS total_count {base_from} "
                    f"WHERE {' AND '.join(clauses)}{where_filters}"
                )
            count_cursor = self.execute_query(count_sql, tuple(params))
            count_row = count_cursor.fetchone()
            total = count_row['total_count'] if count_row else 0

            if total == 0:
                return [], 0

            select_cols = "m.id AS media_id, m.title, m.type, dv.version_number, dv.created_at, dv.safe_metadata"
            order_clause = "ORDER BY m.last_modified DESC"
            if group_by_media:
                results_sql = f"""
                    SELECT {select_cols}
                    {base_from}
                    WHERE {' AND '.join(clauses)}{where_filters}
                    GROUP BY m.id
                    {order_clause}
                    LIMIT ? OFFSET ?
                """
                res_params = tuple(params + [per_page, offset])
            else:
                results_sql = f"""
                    SELECT {select_cols}
                    {base_from}
                    WHERE {' AND '.join(clauses)}{where_filters}
                    {order_clause}
                    LIMIT ? OFFSET ?
                """
                res_params = tuple(params + [per_page, offset])

            cur = self.execute_query(results_sql, res_params)
            rows = [dict(r) for r in cur.fetchall()]
            return rows, total
        except Exception as e:
            logging.error(f"Metadata search failed: {e}", exc_info=True)
            raise DatabaseError(f"Failed metadata search: {e}")
    def add_keyword(self, keyword: str, conn: Optional[Any] = None) -> Tuple[Optional[int], Optional[str]]:
        """
        Adds a new keyword or undeletes an existing soft-deleted one.

        Handles case-insensitivity (stores lowercase) and ensures uniqueness.
        Logs a 'create' or 'update' (for undelete) sync event.
        Updates the `keyword_fts` table accordingly.

        Args:
            keyword (str): The keyword text to add or activate.

        Returns:
            Tuple[Optional[int], Optional[str]]: A tuple containing the keyword's
                database ID and UUID. Returns (None, None) or raises error on failure.

        Raises:
            InputError: If the keyword is empty or whitespace only.
            ConflictError: If an update (undelete) fails due to version mismatch.
            DatabaseError: For other database errors during insert/update or sync logging.
        """
        if not keyword or not keyword.strip():
            raise InputError("Keyword cannot be empty.")
        keyword = keyword.strip().lower()
        current_time = self._get_current_utc_timestamp_str()  # Get current time once
        client_id = self.client_id

        try:
            # If a connection is provided, perform all operations within that
            # transaction to avoid nested write transactions on separate connections
            if conn is not None:
                existing = self._fetchone_with_connection(
                    conn,
                    'SELECT id, uuid, deleted, version FROM Keywords WHERE keyword = ?',
                    (keyword,),
                )

                if existing:
                    kw_id = existing['id']
                    kw_uuid = existing['uuid']
                    is_deleted = existing['deleted']
                    current_version = existing['version']
                    if is_deleted:
                        new_version = current_version + 1
                        logger.info(f"Undeleting keyword '{keyword}' (ID: {kw_id}). New ver: {new_version}")
                        update_cursor = self._execute_with_connection(
                            conn,
                            "UPDATE Keywords SET deleted=0, last_modified=?, version=?, client_id=? WHERE id=? AND version=?",
                            (current_time, new_version, client_id, kw_id, current_version),
                        )
                        if update_cursor.rowcount == 0:
                            raise ConflictError("Keywords", kw_id)

                        # Fetch data for payload AFTER update to get correct last_modified
                        payload_data = self._fetchone_with_connection(
                            conn,
                            "SELECT * FROM Keywords WHERE id=?",
                            (kw_id,),
                        ) or {}
                        self._log_sync_event(conn, 'Keywords', kw_uuid, 'update', new_version, payload_data)
                        self._update_fts_keyword(conn, kw_id, keyword)
                        return kw_id, kw_uuid
                    else:
                        logger.debug(f"Keyword '{keyword}' already active.")
                        return kw_id, kw_uuid
                else:
                    new_uuid = self._generate_uuid()
                    new_version = 1
                    logger.info(f"Adding new keyword '{keyword}' UUID {new_uuid}")
                    # Omit 'deleted' to rely on DEFAULT (FALSE) across backends
                    insert_sql = (
                        "INSERT INTO Keywords (keyword, uuid, last_modified, version, client_id) "
                        "VALUES (?, ?, ?, ?, ?)"
                    )
                    if self.backend_type == BackendType.POSTGRESQL:
                        insert_sql += " RETURNING id"

                    insert_cursor = self._execute_with_connection(
                        conn,
                        insert_sql,
                        (keyword, new_uuid, current_time, new_version, client_id),
                    )

                    if self.backend_type == BackendType.POSTGRESQL:
                        inserted_row = insert_cursor.fetchone()
                        kw_id = inserted_row["id"] if inserted_row else None
                    else:
                        kw_id = insert_cursor.lastrowid

                    if not kw_id:
                        raise DatabaseError("Failed to get last row ID for new keyword.")

                    # Fetch data for payload AFTER insert to get correct last_modified
                    payload_data = self._fetchone_with_connection(
                        conn,
                        "SELECT * FROM Keywords WHERE id=?",
                        (kw_id,),
                    ) or {}
                    self._log_sync_event(conn, 'Keywords', new_uuid, 'create', new_version, payload_data)
                    self._update_fts_keyword(conn, kw_id, keyword)
                    return kw_id, new_uuid
            else:
                # No connection provided: create a transaction-scoped connection
                with self.transaction() as tx_conn:
                    existing = self._fetchone_with_connection(
                        tx_conn,
                        'SELECT id, uuid, deleted, version FROM Keywords WHERE keyword = ?',
                        (keyword,),
                    )

                    if existing:
                        kw_id = existing['id']
                        kw_uuid = existing['uuid']
                        is_deleted = existing['deleted']
                        current_version = existing['version']
                        if is_deleted:
                            new_version = current_version + 1
                            logger.info(f"Undeleting keyword '{keyword}' (ID: {kw_id}). New ver: {new_version}")
                            update_cursor = self._execute_with_connection(
                                tx_conn,
                                "UPDATE Keywords SET deleted=0, last_modified=?, version=?, client_id=? WHERE id=? AND version=?",
                                (current_time, new_version, client_id, kw_id, current_version),
                            )
                            if update_cursor.rowcount == 0:
                                raise ConflictError("Keywords", kw_id)

                            # Fetch data for payload AFTER update to get correct last_modified
                            payload_data = self._fetchone_with_connection(
                                tx_conn,
                                "SELECT * FROM Keywords WHERE id=?",
                                (kw_id,),
                            ) or {}
                            self._log_sync_event(tx_conn, 'Keywords', kw_uuid, 'update', new_version, payload_data)
                            self._update_fts_keyword(tx_conn, kw_id, keyword)
                            return kw_id, kw_uuid
                        else:
                            logger.debug(f"Keyword '{keyword}' already active.")
                            return kw_id, kw_uuid
                    else:
                        new_uuid = self._generate_uuid()
                        new_version = 1
                        logger.info(f"Adding new keyword '{keyword}' UUID {new_uuid}")
                        # Omit 'deleted' to rely on DEFAULT (FALSE) across backends
                        insert_sql = (
                            "INSERT INTO Keywords (keyword, uuid, last_modified, version, client_id) "
                            "VALUES (?, ?, ?, ?, ?)"
                        )
                        if self.backend_type == BackendType.POSTGRESQL:
                            insert_sql += " RETURNING id"

                        insert_cursor = self._execute_with_connection(
                            tx_conn,
                            insert_sql,
                            (keyword, new_uuid, current_time, new_version, client_id),
                        )

                        if self.backend_type == BackendType.POSTGRESQL:
                            inserted_row = insert_cursor.fetchone()
                            kw_id = inserted_row["id"] if inserted_row else None
                        else:
                            kw_id = insert_cursor.lastrowid

                        if not kw_id:
                            raise DatabaseError("Failed to get last row ID for new keyword.")

                        # Fetch data for payload AFTER insert to get correct last_modified
                        payload_data = self._fetchone_with_connection(
                            tx_conn,
                            "SELECT * FROM Keywords WHERE id=?",
                            (kw_id,),
                        ) or {}
                        self._log_sync_event(tx_conn, 'Keywords', new_uuid, 'create', new_version, payload_data)
                        self._update_fts_keyword(tx_conn, kw_id, keyword)
                        return kw_id, new_uuid
        except (InputError, ConflictError, DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error in add_keyword for '{keyword}': {e}", exc_info=isinstance(e, (DatabaseError, sqlite3.Error)))
            if isinstance(e, (InputError, ConflictError, DatabaseError)):
                raise e
            else:
                raise DatabaseError(f"Failed to add/update keyword: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in add_keyword for '{keyword}': {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error adding/updating keyword: {e}") from e

    def fetch_media_for_keywords(self, keywords: List[str], include_trash: bool = False) -> Dict[
        str, List[Dict[str, Any]]]:
        """
        Fetches all active, non-deleted media items associated with each of the
        provided active keywords.

        The media items themselves are filtered based on their `deleted` status (must be 0)
        and optionally their `is_trash` status. Keywords are always filtered for `deleted = 0`.

        Args:
            keywords (List[str]): A list of keyword strings to search for.
                                  The search is case-insensitive.
            include_trash (bool): If True, include media items marked as trash
                                  (Media.is_trash = 1). Defaults to False.

        Returns:
            Dict[str, List[Dict[str, Any]]]: A dictionary where keys are the
                unique, cleaned (lowercase, stripped) input keywords that were found
                active in the database and have associated media matching the criteria.
                Values are lists of dictionaries, each representing a media item.
                Media items include: 'id', 'uuid', 'title', 'type', 'url',
                'content_hash', 'last_modified', 'ingestion_date', 'author'.
                Returns an empty dictionary if no keywords are provided or if
                no matching media is found for any of the provided keywords under
                the given criteria.

        Raises:
            TypeError: If `keywords` is not a list.
            DatabaseError: For database query errors.
        """
        if not isinstance(keywords, list):
            raise TypeError("Input 'keywords' must be a list of strings.")

        if not keywords:
            logger.debug("fetch_media_for_keywords called with an empty list of keywords.")
            return {}

        # Normalize keywords: lowercase, strip whitespace, filter out empty strings, and ensure uniqueness.
        # Sort for consistent query parameter order (good for logging/debugging, though IN order doesn't matter for SQL).
        potential_keywords = [k.strip().lower() for k in keywords if k and k.strip()]
        if not potential_keywords:
            logger.debug("fetch_media_for_keywords: no valid keywords after initial cleaning and stripping.")
            return {}

        unique_clean_keywords = sorted(list(set(potential_keywords)))

        if not unique_clean_keywords:  # Should be redundant due to above check, but defensive.
            logger.debug("fetch_media_for_keywords: no unique valid keywords remain.")
            return {}

        placeholders = ','.join('?' * len(unique_clean_keywords))

        media_conditions = ["m.deleted = ?"]
        media_params: List[Any] = [False]
        if not include_trash:
            media_conditions.append("m.is_trash = ?")
            media_params.append(False)
        media_where_clause = " AND ".join(media_conditions)

        # Select desired fields from Media table
        media_fields = "m.id AS media_id, m.uuid AS media_uuid, m.title AS media_title, " \
                       "m.type AS media_type, m.url AS media_url, m.content_hash AS media_content_hash, " \
                       "m.last_modified AS media_last_modified, m.ingestion_date AS media_ingestion_date, " \
                       "m.author AS media_author"

        order_expr = self._keyword_order_expression("k.keyword")
        query = f"""
            SELECT
                k.keyword AS keyword_text,
                {media_fields}
            FROM Keywords k
            JOIN MediaKeywords mk ON k.id = mk.keyword_id
            JOIN Media m ON mk.media_id = m.id
            WHERE {media_where_clause}
              AND k.keyword IN ({placeholders})
              AND k.deleted = ?
            ORDER BY {order_expr}, m.last_modified DESC, m.id DESC
        """

        params = tuple(media_params + [False] + unique_clean_keywords)

        logger.debug(
            f"Executing fetch_media_for_keywords query for keywords: {unique_clean_keywords}, include_trash: {include_trash}")

        # Initialize results dictionary. Keys will be the cleaned, unique input keywords.
        # If a keyword has no matching media, its list will remain empty.
        results_by_keyword: Dict[str, List[Dict[str, Any]]] = {kw: [] for kw in unique_clean_keywords}

        try:
            conn = self.get_connection()
            rows = self._fetchall_with_connection(conn, query, params)

            for row in rows:
                # keyword_text from DB is the canonical version (e.g. "recipe")
                # It will be one of the unique_clean_keywords due to the IN clause and
                # case-insensitive matching + storage of keywords as lowercase.
                db_keyword = row['keyword_text']

                media_item = {
                    'id': row['media_id'],
                    'uuid': row['media_uuid'],
                    'title': row['media_title'],
                    'type': row['media_type'],
                    'url': row['media_url'],
                    'content_hash': row['media_content_hash'],
                    'last_modified': row['media_last_modified'],
                    'ingestion_date': row['media_ingestion_date'],
                    'author': row['media_author']
                }

                # db_keyword should be a key in results_by_keyword because unique_clean_keywords
                # are already lowercase, and keywords in DB are stored lowercase.
                if db_keyword in results_by_keyword:
                    results_by_keyword[db_keyword].append(media_item)
                else:
                    # This case should not be reached if keyword handling (storage, cleaning, query) is consistent.
                    # Logging an error if it occurs.
                    logger.error(f"Data consistency alert in fetch_media_for_keywords: "
                                 f"Keyword '{db_keyword}' from DB results was not in the "
                                 f"expected set of unique_clean_keywords: {unique_clean_keywords}. "
                                 f"This may indicate a mismatch in case handling or normalization.")
                    # Fallback: add it as a new key to avoid losing data, though it signals an issue.
                    results_by_keyword[db_keyword] = [media_item]

            # Filter out keywords that ended up with no media, if preferred.
            # The current approach returns all queried (unique, clean) keywords as keys.
            # To only return keywords that *had* media:
            # final_results = {k: v for k, v in results_by_keyword.items() if v}

            num_keywords_with_media = len([k for k, v in results_by_keyword.items() if v])
            total_media_items_found = sum(len(v) for v in results_by_keyword.values())
            logger.info(f"Fetched media for keywords. Queried unique keywords: {len(unique_clean_keywords)}. "
                        f"Keywords with media found: {num_keywords_with_media}. "
                        f"Total media items grouped: {total_media_items_found}")

            return results_by_keyword

        except Exception as e:
            logger.error(f"Unexpected error fetching media for keywords from DB {self.db_path_str}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while fetching media for keywords: {e}") from e

    def get_sync_log_entries(self, since_change_id: int = 0, limit: Optional[int] = None) -> List[Dict]:
        """
        Retrieves sync log entries newer than a given change_id.

        Useful for fetching changes to be processed by a synchronization mechanism.

        Args:
            since_change_id (int): The minimum change_id (exclusive) to fetch.
                                   Defaults to 0 to fetch all entries.
            limit (Optional[int]): The maximum number of entries to return.
                                   Defaults to None (no limit).

        Returns:
            List[Dict]: A list of sync log entries, each as a dictionary.
                        The 'payload' field is JSON-decoded if present.
                        Returns an empty list if no new entries are found.

        Raises:
            DatabaseError: If fetching log entries fails.
        """
        query = (
            "SELECT change_id, entity, entity_uuid, operation, timestamp, client_id, version, "
            "org_id, team_id, payload FROM sync_log WHERE change_id > ? ORDER BY change_id ASC"
        )
        params = [since_change_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        try:
            conn = self.get_connection()
            rows = self._fetchall_with_connection(conn, query, tuple(params))
            results = []
            for row_dict in rows:
                if row_dict.get('payload'):
                    try:
                        row_dict['payload'] = json.loads(row_dict['payload'])
                    except json.JSONDecodeError:
                        logging.warning(f"Failed to decode JSON payload for sync log change_id {row_dict.get('change_id')}")
                        row_dict['payload'] = None
                results.append(row_dict)
            return results
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error fetching sync log entries from DB '{self.db_path_str}': {e}")
            raise DatabaseError("Failed to fetch sync log entries") from e

    def delete_sync_log_entries(self, change_ids: List[int]) -> int:
        """
        Deletes specific sync log entries by their change_id.

        Typically used after successfully processing sync events.

        Args:
            change_ids (List[int]): A list of `change_id` values to delete.

        Returns:
            int: The number of sync log entries actually deleted.

        Raises:
            ValueError: If `change_ids` is not a list of integers.
            DatabaseError: If the deletion fails.
        """
        if not change_ids:
            return 0
        if not all(isinstance(cid, int) for cid in change_ids):
            raise ValueError("change_ids must be a list of integers.")
        placeholders = ','.join('?' * len(change_ids))
        query = f"DELETE FROM sync_log WHERE change_id IN ({placeholders})"
        try:
            with self.transaction() as conn:
                cursor = self._execute_with_connection(
                    conn,
                    query,
                    tuple(change_ids),
                )
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} sync log entries from DB '{self.db_path_str}'.")
                return deleted_count
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting sync log entries from DB '{self.db_path_str}': {e}")
            raise DatabaseError(f"Unexpected error deleting sync log entries: {e}") from e

    def delete_sync_log_entries_before(self, change_id_threshold: int) -> int:
        """
        Deletes sync log entries with change_id less than or equal to a threshold.

        Useful for purging old, processed sync history.

        Args:
            change_id_threshold (int): The maximum `change_id` (inclusive) to delete.
                                       Must be a non-negative integer.

        Returns:
            int: The number of sync log entries actually deleted.

        Raises:
            ValueError: If `change_id_threshold` is not a non-negative integer.
            DatabaseError: If the deletion fails.
        """
        if not isinstance(change_id_threshold, int) or change_id_threshold < 0:
            raise ValueError("change_id_threshold must be a non-negative integer.")
        query = "DELETE FROM sync_log WHERE change_id <= ?"
        try:
            with self.transaction() as conn:
                cursor = self._execute_with_connection(
                    conn,
                    query,
                    (change_id_threshold,),
                )
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} sync log entries before or at ID {change_id_threshold} from DB '{self.db_path_str}'.")
                return deleted_count
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting sync log entries before {change_id_threshold} from DB '{self.db_path_str}': {e}")
            raise DatabaseError(f"Unexpected error deleting sync log entries before threshold: {e}") from e

    def soft_delete_media(self, media_id: int, cascade: bool = True) -> bool:
        """
        Soft deletes a Media item by setting its 'deleted' flag to 1.

        Increments the version number, updates `last_modified`, logs a 'delete'
        sync event for the Media item, and removes its FTS entry.
        If `cascade` is True (default), it also performs the following within
        the same transaction:
        - Deletes corresponding MediaKeywords links and logs 'unlink' events.
        - Soft deletes associated child records (Transcripts, MediaChunks,
          UnvectorizedMediaChunks, DocumentVersions), logging 'delete' events
          for each child.

        Args:
            media_id (int): The ID of the Media item to soft delete.
            cascade (bool): Whether to also soft delete related child records
                            and unlink keywords. Defaults to True.

        Returns:
            bool: True if the media item was successfully soft-deleted,
                  False if the item was not found or already deleted.

        Raises:
            ConflictError: If the media item's version has changed since being read.
            DatabaseError: For other database errors during the operation or sync logging.
        """
        current_time = self._get_current_utc_timestamp_str()  # Get time
        client_id = self.client_id
        logger.info(f"Attempting soft delete for Media ID: {media_id} [Client: {client_id}, Cascade: {cascade}]")

        try:
            with self.transaction() as conn:
                media_info = self._fetchone_with_connection(
                    conn,
                    "SELECT uuid, version FROM Media WHERE id = ? AND deleted = 0",
                    (media_id,),
                )
                if not media_info:
                    logger.warning(f"Cannot soft delete: Media ID {media_id} not found or already deleted.")
                    return False
                media_uuid, current_media_version = media_info['uuid'], media_info['version']
                new_media_version = current_media_version + 1

                # Update Media: Pass current_time for last_modified
                update_cursor = self._execute_with_connection(
                    conn,
                    "UPDATE Media SET deleted = 1, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ?",
                    (current_time, new_media_version, client_id, media_id, current_media_version),
                )
                if update_cursor.rowcount == 0:
                    raise ConflictError(entity="Media", identifier=media_id)

                # Payload reflects the state *after* the update
                delete_payload = {'uuid': media_uuid, 'last_modified': current_time, 'version': new_media_version, 'client_id': client_id, 'deleted': 1}
                self._log_sync_event(conn, 'Media', media_uuid, 'delete', new_media_version, delete_payload)
                self._delete_fts_media(conn, media_id)

                if cascade:
                    logger.info(f"Performing explicit cascade delete for Media ID: {media_id}")
                    # Unlinking MediaKeywords - logic remains the same
                    keywords_to_unlink = self._fetchall_with_connection(
                        conn,
                        "SELECT mk.keyword_id AS keyword_id, k.uuid AS keyword_uuid FROM MediaKeywords mk "
                        "JOIN Keywords k ON mk.keyword_id = k.id "
                        "WHERE mk.media_id = ? AND k.deleted = 0",
                        (media_id,),
                    )
                    if keywords_to_unlink:
                        # Delete links by the actual keyword_id values (not the MediaKeywords row id)
                        keyword_ids = [k['keyword_id'] for k in keywords_to_unlink]
                        placeholders = ','.join('?' * len(keyword_ids))
                        params = (media_id, *keyword_ids)
                        self._execute_with_connection(
                            conn,
                            f"DELETE FROM MediaKeywords WHERE media_id = ? AND keyword_id IN ({placeholders})",
                            params,
                        )
                        unlink_version = 1
                        for kw_link in keywords_to_unlink:
                            link_uuid = f"{media_uuid}_{kw_link['keyword_uuid']}"
                            unlink_payload = {'media_uuid': media_uuid, 'keyword_uuid': kw_link['keyword_uuid']}
                            self._log_sync_event(conn, 'MediaKeywords', link_uuid, 'unlink', unlink_version, unlink_payload)

                    # Soft deleting child tables
                    child_tables = [("Transcripts", "media_id", "uuid"), ("MediaChunks", "media_id", "uuid"),
                                    ("UnvectorizedMediaChunks", "media_id", "uuid"), ("DocumentVersions", "media_id", "uuid")]
                    for table, fk_col, uuid_col in child_tables:
                        children = self._fetchall_with_connection(
                            conn,
                            f"SELECT id, {uuid_col} AS uuid, version FROM {table} WHERE {fk_col} = ? AND deleted = 0",
                            (media_id,),
                        )
                        if not children:
                            continue
                        # Pass current_time for last_modified in child update
                        update_sql = f"UPDATE {table} SET deleted = 1, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ? AND deleted = 0"
                        processed_children_count = 0
                        for child in children:
                            child_id, child_uuid, child_current_version = child['id'], child['uuid'], child['version']
                            child_new_version = child_current_version + 1
                            # Pass current_time here
                            params = (current_time, child_new_version, client_id, child_id, child_current_version)
                            child_cursor = self._execute_with_connection(conn, update_sql, params)
                            if child_cursor.rowcount == 1:
                                processed_children_count += 1
                                # Ensure payload includes correct last_modified and deleted status
                                child_delete_payload = {'uuid': child_uuid, 'media_uuid': media_uuid, 'last_modified': current_time, 'version': child_new_version, 'client_id': client_id, 'deleted': 1}
                                self._log_sync_event(conn, table, child_uuid, 'delete', child_new_version, child_delete_payload)
                            else:
                                logger.warning(f"Conflict/error cascade deleting {table} ID {child_id}")
                        logger.debug(f"Cascade deleted {processed_children_count}/{len(children)} records in {table}.")

            logger.info(f"Soft delete successful for Media ID: {media_id}.")
            # Invalidate agentic intra-doc paragraph vectors for this document
            try:
                from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import invalidate_intra_doc_vectors  # lazy import
                invalidate_intra_doc_vectors(str(media_id))
            except Exception:
                pass
            return True
        except (ConflictError, DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error soft deleting media ID {media_id}: {e}", exc_info=True)
            if isinstance(e, (ConflictError, DatabaseError)):
                raise e
            else:
                raise DatabaseError(f"Failed to soft delete media: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error soft deleting media ID {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error during soft delete: {e}") from e

    def add_media_with_keywords(
            self,
            *,
            url: Optional[str] = None,
            title: Optional[str] = None,
            media_type: Optional[str] = None,
            content: Optional[str] = None,
            keywords: Optional[List[str]] = None,
            prompt: Optional[str] = None,
            analysis_content: Optional[str] = None,
            safe_metadata: Optional[str] = None,
            transcription_model: Optional[str] = None,
            author: Optional[str] = None,
            ingestion_date: Optional[str] = None,
            overwrite: bool = False,
            chunk_options: Optional[Dict] = None,
            chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Optional[int], Optional[str], str]:
        """Add or update a media record, handle keyword links, optional chunks and full-text sync."""

        # ---------------------------------------------------------------------
        # 1. Fast-fail validation & normalisation
        # ---------------------------------------------------------------------
        if content is None:
            raise InputError("Content cannot be None.")

        title = title or "Untitled"
        media_type = media_type or "unknown"
        keywords_norm = [k.strip().lower() for k in keywords or [] if k and k.strip()]

        now = self._get_current_utc_timestamp_str()
        ingestion_date = ingestion_date or now
        client_id = self.client_id

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        url = url or f"local://{media_type}/{content_hash}"

        # Determine the final chunk status before any DB operation
        final_chunk_status = "completed" if chunks is not None else "pending"

        logging.info("add_media_with_keywords: url=%s, title=%s, client=%s", url, title, client_id)
        # Topic monitoring (non-blocking) for ingestion text (bounded at service level)
        try:
            from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import get_topic_monitoring_service
            mon = get_topic_monitoring_service()
            uid = str(client_id) if client_id is not None else None
            if title:
                mon.evaluate_and_alert(user_id=uid, text=title, source="ingestion.media", scope_type="user", scope_id=uid)
            if content:
                mon.evaluate_and_alert(user_id=uid, text=content, source="ingestion.media", scope_type="user", scope_id=uid)
            if analysis_content:
                mon.evaluate_and_alert(user_id=uid, text=analysis_content, source="ingestion.media", scope_type="user", scope_id=uid)
        except Exception:
            pass

        # ------------------------------------------------------------------
        # Helper builders
        # ------------------------------------------------------------------
        def _media_payload(uuid_: str, version_: int, *, chunk_status: str) -> Dict[str, Any]:
            """Return a dict suitable for INSERT/UPDATE parameters and for sync logging."""
            bool_false = False if self.backend_type == BackendType.POSTGRESQL else 0
            scope_org_id, scope_team_id = self._resolve_scope_ids()
            return {
                "url": url,
                "title": title,
                "type": media_type,
                "content": content,
                "author": author,
                "ingestion_date": ingestion_date,
                "transcription_model": transcription_model,
                "content_hash": content_hash,
                "is_trash": bool_false,
                "trash_date": None,
                "chunking_status": chunk_status,
                # Keep vector_processing as integer for both backends (schema uses INTEGER)
                "vector_processing": 0,
                "uuid": uuid_,
                "last_modified": now,
                "version": version_,
                "org_id": scope_org_id,
                "team_id": scope_team_id,
                "client_id": client_id,
                "deleted": bool_false,
            }

        def _persist_chunks(cnx: sqlite3.Connection, media_id: int) -> None:
            """Delete/insert un-vectorized chunks as requested. DOES NOT update parent Media."""
            if chunks is None:
                return  # caller did not touch chunks

            if overwrite:
                cnx.execute("DELETE FROM UnvectorizedMediaChunks WHERE media_id = ?", (media_id,))

            if not chunks:  # empty list means just wipe
                return

            created = self._get_current_utc_timestamp_str()
            for idx, ch in enumerate(chunks):
                if not isinstance(ch, dict) or ch.get("text") is None:
                    logging.warning("Skipping invalid chunk index %s for media_id %s", idx, media_id)
                    continue

                chunk_uuid = self._generate_uuid()
                bool_false = False if self.backend_type == BackendType.POSTGRESQL else 0
                cnx.execute(
                    """INSERT INTO UnvectorizedMediaChunks (media_id, chunk_text, chunk_index, start_char, end_char,
                                                            chunk_type, creation_date, last_modified_orig, is_processed,
                                                            metadata, uuid, last_modified, version, client_id, deleted,
                                                            prev_version, merge_parent_uuid)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        media_id, ch["text"], idx, ch.get("start_char"), ch.get("end_char"), ch.get("chunk_type"),
                        created, created, False,
                        json.dumps(ch.get("metadata")) if isinstance(ch.get("metadata"), dict) else None,
                        chunk_uuid, created, 1, client_id, bool_false, None, None,
                    ),
                )
                self._log_sync_event(
                    cnx, "UnvectorizedMediaChunks", chunk_uuid, "create", 1,
                    {
                        **ch, "media_id": media_id, "uuid": chunk_uuid, "chunk_index": idx,
                        "creation_date": created, "last_modified": created, "version": 1,
                        "client_id": client_id, "deleted": bool_false,
                    },
                )

        # ------------------------------------------------------------------
        # 2. Main transactional block
        # ------------------------------------------------------------------
        try:
            with self.transaction() as conn:
                def _exec(query: str, params: Optional[Union[Tuple, List, Dict]] = None):
                    return self._execute_with_connection(conn, query, params)

                def _fetchone(query: str, params: Optional[Union[Tuple, List, Dict]] = None):
                    return self._fetchone_with_connection(conn, query, params)

                def _fetchall(query: str, params: Optional[Union[Tuple, List, Dict]] = None):
                    return self._fetchall_with_connection(conn, query, params)

                # Find existing record by URL or content_hash
                row = _fetchone(
                    "SELECT id, uuid, version, url, content_hash FROM Media WHERE url = ? AND deleted = 0 LIMIT 1",
                    (url,),
                )

                if not row:
                    row = _fetchone(
                        "SELECT id, uuid, version, url, content_hash FROM Media WHERE content_hash = ? AND deleted = 0 LIMIT 1",
                        (content_hash,),
                    )

                # --- Path A: Record exists, handle UPDATE, CANONICALIZATION, or SKIP ---
                if row:
                    media_id = row["id"]
                    media_uuid = row["uuid"]
                    current_ver = row["version"]
                    existing_url = row["url"]
                    existing_hash = row["content_hash"]

                    # Case A.1: Overwrite is requested.
                    if overwrite:
                        # Case A.1.a: Content is identical. No version bump needed for main content.
                        if content_hash == existing_hash:
                            logging.info(f"Media content for ID {media_id} is identical. Updating metadata/chunks only.")

                            # Update keywords and chunks without changing the main Media record yet.
                            self.update_keywords_for_media(media_id, keywords_norm, conn=conn)
                            _persist_chunks(conn, media_id)

                            # If new chunks were provided, the media's chunking status has changed,
                            # which justifies a version bump on the parent Media record.
                            if chunks is not None:
                                logging.info(f"Chunks provided for identical media; updating media chunk_status and version for ID {media_id}.")
                                new_ver = current_ver + 1
                                update_cursor = _exec(
                                    """UPDATE Media SET chunking_status = 'completed', version = ?, last_modified = ?
                                       WHERE id = ? AND version = ?""",
                                    (new_ver, now, media_id, current_ver),
                                )
                                if update_cursor.rowcount == 0:
                                    raise ConflictError(f"Media (updating chunk status for identical content id={media_id})", media_id)

                                self._log_sync_event(conn, "Media", media_uuid, "update", new_ver, {"chunking_status": "completed", "last_modified": now})

                            return media_id, media_uuid, f"Media '{title}' is already up-to-date."

                        # Case A.1.b: Content is different. Proceed with a full versioned update.
                        new_ver = current_ver + 1
                        payload = _media_payload(media_uuid, new_ver, chunk_status=final_chunk_status)
                        update_sql = """
                            UPDATE Media
                               SET url = ?, title = ?, type = ?, content = ?, author = ?,
                                   ingestion_date = ?, transcription_model = ?,
                                   content_hash = ?, is_trash = ?, trash_date = ?,
                                   chunking_status = ?, vector_processing = ?,
                                   last_modified = ?, version = ?, client_id = ?, deleted = ?
                               WHERE id = ? AND version = ?
                        """
                        update_params = (
                            payload['url'],
                            payload['title'],
                            payload['type'],
                            payload['content'],
                            payload['author'],
                            payload['ingestion_date'],
                            payload['transcription_model'],
                            payload['content_hash'],
                            payload['is_trash'],
                            payload['trash_date'],
                            payload['chunking_status'],
                            payload['vector_processing'],
                            payload['last_modified'],
                            payload['version'],
                            payload['client_id'],
                            payload['deleted'],
                            media_id,
                            current_ver,
                        )
                        update_cursor = _exec(update_sql, update_params)
                        if update_cursor.rowcount == 0:
                            raise ConflictError(f"Media (full update id={media_id})", media_id)

                        self._log_sync_event(conn, "Media", media_uuid, "update", new_ver, payload)
                        self._update_fts_media(conn, media_id, payload["title"], payload["content"])
                        self.update_keywords_for_media(media_id, keywords_norm, conn=conn)
                        self.create_document_version(
                            media_id=media_id, content=content, prompt=prompt, analysis_content=analysis_content
                        )
                        _persist_chunks(conn, media_id)
                        # Re-anchoring: mark reading highlights stale if content changed
                        try:
                            if _CollectionsDB is not None and client_id is not None:
                                _CollectionsDB.from_backend(user_id=str(client_id), backend=self.backend).mark_highlights_stale_if_content_changed(media_id, content_hash)
                        except Exception as _anch_err:
                            logging.debug(f"Highlight re-anchoring hook failed (non-fatal): {_anch_err}")
                        # Invalidate agentic intra-doc vectors on content update
                        try:
                            from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import invalidate_intra_doc_vectors  # lazy import
                            invalidate_intra_doc_vectors(str(media_id))
                        except Exception:
                            pass
                        return media_id, media_uuid, f"Media '{title}' updated to new version."

                    # Case A.2: Overwrite is FALSE.
                    else:
                        is_canonicalisation = (
                                existing_url.startswith("local://")
                                and not url.startswith("local://")
                                and content_hash == existing_hash
                        )
                        if is_canonicalisation:
                            logging.info(f"Canonicalizing URL for media_id {media_id} to {url}")
                            new_ver = current_ver + 1
                            canon_cursor = _exec(
                                "UPDATE Media SET url = ?, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ?",
                                (url, now, new_ver, client_id, media_id, current_ver),
                            )
                            if canon_cursor.rowcount == 0:
                                raise ConflictError(f"Media (canonicalization id={media_id})", media_id)

                            self._log_sync_event(
                                conn, "Media", media_uuid, "update", new_ver, {"url": url, "last_modified": now}
                            )
                            return media_id, media_uuid, f"Media '{title}' URL canonicalized."

                        # Touch last_modified to reflect recent access so listing surfaces it
                        try:
                            new_ver = current_ver + 1
                            touch_cursor = _exec(
                                "UPDATE Media SET last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ?",
                                (now, new_ver, client_id, media_id, current_ver),
                            )
                            if touch_cursor.rowcount == 1:
                                self._log_sync_event(
                                    conn, "Media", media_uuid, "update", new_ver, {"last_modified": now, "touched": True}
                                )
                            else:
                                logging.debug(f"No rows updated when touching media {media_id}; possible version change.")
                        except Exception as _touch_err:
                            logging.debug(f"Non-fatal: failed to touch media {media_id}: {_touch_err}")

                        # Return existing record references to allow callers to treat as a non-fatal result
                        return media_id, media_uuid, f"Media '{title}' already exists. Overwrite not enabled."

                # --- Path B: Record does not exist, perform INSERT ---
                else:
                    # Use lock to prevent race conditions during concurrent inserts
                    with self._media_insert_lock:
                        # Double-check within lock that record still doesn't exist
                        recheck_row = _fetchone(
                            "SELECT id, uuid, version FROM Media WHERE url = ? AND deleted = 0",
                            (url,),
                        )
                        if recheck_row:
                            # Another thread inserted while we were waiting for lock
                            media_id, media_uuid, current_ver = recheck_row["id"], recheck_row["uuid"], recheck_row["version"]
                            if not overwrite:
                                # Return existing record references to allow idempotent client behavior
                                return media_id, media_uuid, f"Media '{title}' already exists (concurrent insert). Overwrite not enabled."
                            # If overwrite is True, we could update, but for simplicity return existing
                            return media_id, media_uuid, f"Media '{title}' already exists (handled concurrent insert)."

                        # Proceed with INSERT - now protected by lock
                        media_uuid = self._generate_uuid()
                        payload = _media_payload(media_uuid, 1, chunk_status=final_chunk_status)
                        insert_sql = """
                            INSERT INTO Media (url, title, type, content, author, ingestion_date,
                                               transcription_model, content_hash, is_trash, trash_date,
                                               chunking_status, vector_processing, uuid, last_modified,
                                               version, org_id, team_id, client_id, deleted)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        insert_params = (
                            payload['url'],
                            payload['title'],
                            payload['type'],
                            payload['content'],
                            payload['author'],
                            payload['ingestion_date'],
                            payload['transcription_model'],
                            payload['content_hash'],
                            payload['is_trash'],
                            payload['trash_date'],
                            payload['chunking_status'],
                            payload['vector_processing'],
                            payload['uuid'],
                            payload['last_modified'],
                            payload['version'],
                            payload['org_id'],
                            payload['team_id'],
                            payload['client_id'],
                            payload['deleted'],
                        )
                        if self.backend_type == BackendType.POSTGRESQL:
                            insert_sql += " RETURNING id"

                        insert_cursor = _exec(insert_sql, insert_params)
                        if self.backend_type == BackendType.POSTGRESQL:
                            inserted_row = insert_cursor.fetchone()
                            media_id = inserted_row['id'] if inserted_row else None
                        else:
                            media_id = insert_cursor.lastrowid
                        if not media_id:
                            raise DatabaseError("Failed to obtain new media ID.")

                    # Continue with the rest of the operations outside the lock
                    self._log_sync_event(conn, "Media", media_uuid, "create", 1, payload)
                    self._update_fts_media(conn, media_id, payload["title"], payload["content"])
                    self.update_keywords_for_media(media_id, keywords_norm, conn=conn)
                    self.create_document_version(
                        media_id=media_id, content=content, prompt=prompt, analysis_content=analysis_content, safe_metadata=safe_metadata
                    )
                    _persist_chunks(conn, media_id)

                    # Optionally populate structure index based on provided chunks metadata
                    try:
                        from tldw_Server_API.app.core.config import rag_enable_structure_index  # lazy import to avoid heavy deps
                        enable_si = rag_enable_structure_index()
                    except Exception:
                        enable_si = True
                    if enable_si and chunks:
                        try:
                            # Derive section ranges using chunk metadata 'section_path' or 'ancestry_titles'
                            sections_agg: Dict[str, Dict[str, Any]] = {}
                            order = 0
                            for ch in chunks:
                                md = ch.get('metadata') or {}
                                start = ch.get('start_char')
                                end = ch.get('end_char')
                                if start is None or end is None:
                                    continue
                                path = md.get('section_path') or md.get('ancestry_titles') or []
                                if isinstance(path, str):
                                    # Some callers may store as CSV
                                    path = [p.strip() for p in path.split('/') if p.strip()]
                                if not isinstance(path, list) or not path:
                                    continue
                                title = str(path[-1])
                                key = ' / '.join([str(x) for x in path])
                                rec = sections_agg.get(key)
                                if not rec:
                                    sections_agg[key] = {
                                        'kind': 'section',
                                        'level': len(path),
                                        'title': title,
                                        'start_char': int(start),
                                        'end_char': int(end),
                                        'order_index': order,
                                        'path': key,
                                    }
                                    order += 1
                                else:
                                    # Expand section bounds
                                    rec['start_char'] = min(int(start), int(rec['start_char']))
                                    rec['end_char'] = max(int(end), int(rec['end_char']))

                            section_ids_by_range: List[Dict[str, Any]] = []
                            if sections_agg:
                                # Insert sections first
                                self._write_structure_index_records(conn, media_id, list(sections_agg.values()))
                                # Preload section rows to speed up parent_id lookup
                                try:
                                    cur = conn.execute(
                                        "SELECT id, start_char, end_char FROM DocumentStructureIndex "
                                        "WHERE media_id=? AND deleted=0 AND kind IN ('section','header')",
                                        (media_id,),
                                    )
                                    section_ids_by_range = [dict(row) for row in cur.fetchall()]
                                except Exception:
                                    section_ids_by_range = []

                            # Insert paragraph entries linked to their containing section
                            try:
                                created = self._get_current_utc_timestamp_str()
                                bool_false = False if self.backend_type == BackendType.POSTGRESQL else 0
                                order = 0
                                for ch in chunks:
                                    if not isinstance(ch, dict):
                                        continue
                                    ctype = (ch.get('chunk_type') or '').lower()
                                    # Treat text/list/code as paragraph-like; skip heading/table for this index
                                    if ctype not in ('text', 'list', 'code'):
                                        continue
                                    s = ch.get('start_char')
                                    e = ch.get('end_char')
                                    if s is None or e is None:
                                        continue
                                    parent_id = None
                                    # Fast path: find containing section from preloaded ranges
                                    try:
                                        for row in section_ids_by_range:
                                            if int(row.get('start_char')) <= int(s) < int(row.get('end_char')):
                                                parent_id = int(row.get('id'))
                                                break
                                    except Exception:
                                        parent_id = None
                                    # Fallback DB lookup
                                    if parent_id is None:
                                        try:
                                            cur2 = conn.execute(
                                                "SELECT id FROM DocumentStructureIndex WHERE media_id=? AND deleted=0 AND kind IN ('section','header') AND start_char <= ? AND end_char > ? ORDER BY COALESCE(level,0) DESC, start_char DESC LIMIT 1",
                                                (media_id, int(s), int(s)),
                                            )
                                            row2 = cur2.fetchone()
                                            parent_id = int(row2['id']) if row2 else None
                                        except Exception:
                                            parent_id = None
                                    path = None
                                    md = ch.get('metadata') or {}
                                    if md.get('section_path'):
                                        path = md.get('section_path') if isinstance(md.get('section_path'), str) else '/'.join(map(str, md.get('section_path')))
                                    elif md.get('ancestry_titles'):
                                        path = md.get('ancestry_titles') if isinstance(md.get('ancestry_titles'), str) else '/'.join(map(str, md.get('ancestry_titles')))
                                    conn.execute(
                                        """
                                        INSERT INTO DocumentStructureIndex (
                                            media_id, parent_id, kind, level, title, start_char, end_char,
                                            order_index, path, created_at, last_modified, version, client_id, deleted
                                        ) VALUES (?, ?, 'paragraph', NULL, NULL, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                                        """,
                                        (
                                            media_id,
                                            parent_id,
                                            int(s),
                                            int(e),
                                            order,
                                            path,
                                            created,
                                            created,
                                            client_id,
                                            bool_false,
                                        ),
                                    )
                                    order += 1
                            except Exception as _para_err:
                                logging.warning(f"Paragraph index population failed (non-fatal): {_para_err}")
                        except Exception as _si_err:
                            logging.warning(f"Structure index population failed (non-fatal): {_si_err}")
                    if chunk_options:
                        logging.info("chunk_options ignored (placeholder): %s", chunk_options)

                    return media_id, media_uuid, f"Media '{title}' added."

        except (InputError, ConflictError, sqlite3.IntegrityError) as e:
            # Catch the specific IntegrityError from the trigger and re-raise as a more descriptive error if you want
            logging.error(f"Transaction failed, rolling back: {type(e).__name__} - {e}")
            raise  # Re-raise the original exception

    # ------------------------
    # DocumentStructureIndex
    # ------------------------

    def _write_structure_index_records(self, conn, media_id: int, records: List[Dict[str, Any]]) -> int:
        """Internal: insert rows into DocumentStructureIndex for a media item.

        Expects records with keys: kind, level, title, start_char, end_char, order_index, path.
        Clears existing rows for the media_id first (soft clears by hard delete since index is derived).
        """
        try:
            # Remove previous index (derived data)
            conn.execute("DELETE FROM DocumentStructureIndex WHERE media_id = ?", (media_id,))
        except Exception as e:
            logging.warning(f"Failed to clear old structure index for media_id={media_id}: {e}")
        if not records:
            return 0
        now = self._get_current_utc_timestamp_str()
        client_id = self.client_id
        inserted = 0
        for rec in records:
            try:
                conn.execute(
                    """
                    INSERT INTO DocumentStructureIndex (
                        media_id, parent_id, kind, level, title, start_char, end_char,
                        order_index, path, created_at, last_modified, version, client_id, deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        media_id,
                        rec.get('parent_id'),
                        rec.get('kind') or 'section',
                        rec.get('level'),
                        rec.get('title'),
                        rec.get('start_char'),
                        rec.get('end_char'),
                        rec.get('order_index'),
                        rec.get('path'),
                        now,
                        now,
                        1,
                        client_id,
                        0 if self.backend_type == BackendType.SQLITE else False,
                    ),
                )
                inserted += 1
            except Exception as e:
                logging.warning(f"Skipping invalid structure record for media_id={media_id}: {e}")
        return inserted

    def write_document_structure_index(self, media_id: int, records: List[Dict[str, Any]]) -> int:
        """Public: replace DocumentStructureIndex for a media item with provided records.

        Suitable for callers that pre-compute structure externally.
        """
        if not media_id:
            raise InputError("media_id required for structure index write")
        with self.transaction() as conn:
            return self._write_structure_index_records(conn, media_id, records)

    def delete_document_structure_for_media(self, media_id: int) -> int:
        """Delete structure index rows for a given media item. Returns deleted row count."""
        if not media_id:
            return 0
        with self.transaction() as conn:
            cur = conn.execute("DELETE FROM DocumentStructureIndex WHERE media_id = ?", (media_id,))
            return int(cur.rowcount or 0)

    # =========================================================================
    # Chunking Templates Methods (moved earlier to ensure availability)
    # =========================================================================

    def create_chunking_template(self,
                                name: str,
                                template_json: str,
                                description: Optional[str] = None,
                                is_builtin: bool = False,
                                tags: Optional[List[str]] = None,
                                user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new chunking template.

        Args:
            name: Template name (must be unique among non-deleted templates)
            template_json: JSON string containing template configuration
            description: Optional template description
            is_builtin: Whether this is a built-in template (cannot be modified/deleted)
            tags: Optional list of tags for categorization
            user_id: Optional user ID for ownership tracking

        Returns:
            Dictionary containing created template information

        Raises:
            DatabaseError: If template creation fails
            InputError: If name already exists
        """
        import uuid as uuid_module

        template_uuid = str(uuid_module.uuid4())
        tags_json = json.dumps(tags) if tags else None

        try:
            json.loads(template_json)
        except json.JSONDecodeError as e:
            raise InputError(f"Invalid template JSON: {e}")

        current_time = self._get_current_utc_timestamp_str()

        with self.transaction() as conn:
            existing = self._fetchone_with_connection(
                conn,
                "SELECT 1 FROM ChunkingTemplates WHERE name = ? AND deleted = ? LIMIT 1",
                (name, False),
            )
            if existing:
                raise InputError(f"Template with name '{name}' already exists")

            insert_sql = """
                INSERT INTO ChunkingTemplates (
                    uuid, name, description, template_json, is_builtin, tags,
                    created_at, updated_at, last_modified, version, client_id,
                    user_id, deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                template_uuid,
                name,
                description,
                template_json,
                is_builtin,
                tags_json,
                current_time,
                current_time,
                current_time,
                1,
                self.client_id,
                user_id,
                False,
            )

            if self.backend_type == BackendType.POSTGRESQL:
                insert_sql += " RETURNING id"

            insert_cursor = self._execute_with_connection(conn, insert_sql, params)
            if self.backend_type == BackendType.POSTGRESQL:
                inserted_row = insert_cursor.fetchone()
                template_id = inserted_row['id'] if inserted_row else None
            else:
                template_id = insert_cursor.lastrowid

            if not template_id:
                raise DatabaseError("Failed to create chunking template.")

        logger.info(f"Created chunking template '{name}' with UUID {template_uuid}")

        return {
            'id': template_id,
            'uuid': template_uuid,
            'name': name,
            'description': description,
            'template_json': template_json,
            'is_builtin': is_builtin,
            'tags': tags,
            'user_id': user_id,
            'version': 1,
        }

    def get_chunking_template(self,
                             template_id: Optional[int] = None,
                             name: Optional[str] = None,
                             uuid: Optional[str] = None,
                             include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get a chunking template by ID, name, or UUID.

        Args:
            template_id: Template database ID
            name: Template name
            uuid: Template UUID
            include_deleted: Whether to include soft-deleted templates

        Returns:
            Template dictionary or None if not found
        """
        if not any([template_id, name, uuid]):
            raise InputError("Must provide template_id, name, or uuid")
        params: List[Any] = []
        conditions: List[str] = []

        if template_id is not None:
            conditions.append("id = ?")
            params.append(template_id)
        if name:
            conditions.append("name = ?")
            params.append(name)
        if uuid:
            conditions.append("uuid = ?")
            params.append(uuid)

        query = f"SELECT * FROM ChunkingTemplates WHERE ({' OR '.join(conditions)})"
        if not include_deleted:
            query += " AND deleted = ?"
            params.append(False)

        cursor = self.execute_query(query, tuple(params))
        row = cursor.fetchone()

        if not row:
            return None

        return {
            'id': row['id'],
            'uuid': row['uuid'],
            'name': row['name'],
            'description': row['description'],
            'template_json': row['template_json'],
            'is_builtin': bool(row['is_builtin']),
            'tags': json.loads(row['tags']) if row['tags'] else [],
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'version': row['version'],
            'user_id': row['user_id'],
            'deleted': bool(row['deleted']),
        }

    def list_chunking_templates(self,
                               include_builtin: bool = True,
                               include_custom: bool = True,
                               tags: Optional[List[str]] = None,
                               user_id: Optional[str] = None,
                               include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        List all chunking templates with optional filtering.

        Args:
            include_builtin: Include built-in templates
            include_custom: Include custom templates
            tags: Filter by tags (templates must have at least one matching tag)
            user_id: Filter by user ID
            include_deleted: Include soft-deleted templates

        Returns:
            List of template dictionaries
        """
        if not include_builtin and not include_custom:
            return []

        conditions: List[str] = []
        params: List[Any] = []

        if not include_deleted:
            conditions.append("deleted = ?")
            params.append(False)

        if include_builtin != include_custom:
            conditions.append("is_builtin = ?")
            params.append(include_builtin)

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        query = "SELECT * FROM ChunkingTemplates"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY is_builtin DESC, name ASC"

        cursor = self.execute_query(query, tuple(params))
        rows = cursor.fetchall()

        templates = []
        for row in rows:
            template = {
                'id': row['id'],
                'uuid': row['uuid'],
                'name': row['name'],
                'description': row['description'],
                'template_json': row['template_json'],
                'is_builtin': bool(row['is_builtin']),
                'tags': json.loads(row['tags']) if row['tags'] else [],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'version': row['version'],
                'user_id': row['user_id'],
            }

            if tags and not any(tag in template['tags'] for tag in tags):
                continue

            templates.append(template)

        return templates

    def update_chunking_template(self,
                                template_id: Optional[int] = None,
                                name: Optional[str] = None,
                                uuid: Optional[str] = None,
                                template_json: Optional[str] = None,
                                description: Optional[str] = None,
                                tags: Optional[List[str]] = None) -> bool:
        """
        Update a chunking template (cannot update built-in templates).

        Args:
            template_id: Template ID to update
            name: Template name to update
            uuid: Template UUID to update
            template_json: New template JSON configuration
            description: New description
            tags: New tags list

        Returns:
            True if updated, False if not found or is built-in

        Raises:
            InputError: If trying to update a built-in template
            DatabaseError: If update fails
        """
        # Get existing template
        template = self.get_chunking_template(
            template_id=template_id,
            name=name,
            uuid=uuid
        )

        if not template:
            return False

        if template['is_builtin']:
            raise InputError("Cannot modify built-in templates")

        # Validate new JSON if provided
        if template_json:
            try:
                json.loads(template_json)
            except json.JSONDecodeError as e:
                raise InputError(f"Invalid template JSON: {e}")

        updates: List[str] = []
        params: List[Any] = []

        if template_json is not None:
            updates.append("template_json = ?")
            params.append(template_json)

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))

        if not updates:
            return False

        current_time = self._get_current_utc_timestamp_str()
        updates.extend([
            "updated_at = ?",
            "last_modified = ?",
            "version = version + 1",
            "client_id = ?",
        ])
        params.extend([current_time, current_time, self.client_id, template['id'], False])

        update_sql = f"""
            UPDATE ChunkingTemplates
            SET {', '.join(updates)}
            WHERE id = ? AND deleted = ?
        """

        with self.transaction() as conn:
            cursor = self._execute_with_connection(conn, update_sql, tuple(params))
            if cursor.rowcount == 0:
                return False

        logger.info(f"Updated chunking template ID {template['id']}")
        return True

    def delete_chunking_template(self,
                                template_id: Optional[int] = None,
                                name: Optional[str] = None,
                                uuid: Optional[str] = None,
                                hard_delete: bool = False) -> bool:
        """
        Delete a chunking template (soft delete by default).

        Args:
            template_id: Template ID to delete
            name: Template name to delete
            uuid: Template UUID to delete
            hard_delete: Permanently delete instead of soft delete

        Returns:
            True if deleted, False if not found

        Raises:
            InputError: If trying to delete a built-in template
        """
        # Get existing template
        template = self.get_chunking_template(
            template_id=template_id,
            name=name,
            uuid=uuid
        )

        if not template:
            return False

        if template['is_builtin']:
            raise InputError("Cannot delete built-in templates")

        deleted_rows = 0

        with self.transaction() as conn:
            if hard_delete:
                delete_cursor = self._execute_with_connection(
                    conn,
                    "DELETE FROM ChunkingTemplates WHERE id = ?",
                    (template['id'],),
                )
                deleted_rows = delete_cursor.rowcount
                logger.info(f"Hard deleted chunking template ID {template['id']}")
            else:
                current_time = self._get_current_utc_timestamp_str()
                update_cursor = self._execute_with_connection(
                    conn,
                    """
                    UPDATE ChunkingTemplates
                    SET deleted = ?,
                        updated_at = ?,
                        last_modified = ?,
                        client_id = ?
                    WHERE id = ?
                    """,
                    (True, current_time, current_time, self.client_id, template['id']),
                )
                deleted_rows = update_cursor.rowcount
                logger.info(f"Soft deleted chunking template ID {template['id']}")

        return deleted_rows > 0

    def seed_builtin_templates(self, templates: List[Dict[str, Any]]) -> int:
        """
        Seed built-in templates into the database.

        Args:
            templates: List of template dictionaries to seed

        Returns:
            Number of templates seeded
        """
        count = 0

        for template in templates:
            # Check if template already exists
            existing = self.get_chunking_template(
                name=template['name'],
                include_deleted=True
            )

            if not existing:
                try:
                    self.create_chunking_template(
                        name=template['name'],
                        template_json=json.dumps(template.get('template', template)),
                        description=template.get('description', ''),
                        is_builtin=True,
                        tags=template.get('tags', [])
                    )
                    count += 1
                    logger.info(f"Seeded built-in template: {template['name']}")
                except Exception as e:
                    logger.error(f"Failed to seed template {template['name']}: {e}")
            elif existing['deleted']:
                # Restore deleted built-in template
                current_time = self._get_current_utc_timestamp_str()
                with self.transaction() as conn:
                    self._execute_with_connection(
                        conn,
                        """
                        UPDATE ChunkingTemplates
                        SET deleted = ?,
                            template_json = ?,
                            description = ?,
                            tags = ?,
                            updated_at = ?,
                            last_modified = ?,
                            version = version + 1,
                            client_id = ?
                        WHERE id = ?
                        """,
                        (
                            False,
                            json.dumps(template.get('template', template)),
                            template.get('description', ''),
                            json.dumps(template.get('tags', [])),
                            current_time,
                            current_time,
                            self.client_id,
                            existing['id'],
                        ),
                    )
                count += 1
                logger.info(f"Restored built-in template: {template['name']}")

        return count

    def lookup_section_for_offset(self, media_id: int, char_offset: int) -> Optional[Dict[str, Any]]:
        """Return the most specific section covering char_offset for media_id."""
        if media_id is None or char_offset is None:
            return None
        query = (
            "SELECT id, title, level, start_char, end_char FROM DocumentStructureIndex "
            "WHERE media_id = ? AND deleted = 0 AND kind IN ('section','header') "
            "AND start_char <= ? AND end_char > ? ORDER BY COALESCE(level, 0) DESC, start_char DESC LIMIT 1"
        )
        try:
            with self.transaction() as conn:
                cur = conn.execute(query, (media_id, char_offset, char_offset))
                row = cur.fetchone()
        except Exception:
            return None
        if not row:
            return None
        if isinstance(row, dict):
            return row
        return {"id": row["id"], "title": row["title"], "level": row["level"], "start_char": row["start_char"], "end_char": row["end_char"]}

    def lookup_section_by_heading(self, media_id: int, heading: str) -> Optional[Tuple[int, int, str]]:
        """Best-effort lookup of a section by case-insensitive title match."""
        if not media_id or not heading:
            return None
        try:
            pattern = f"%{heading.strip()}%"
            with self.transaction() as conn:
                cur = conn.execute(
                    "SELECT start_char, end_char, title FROM DocumentStructureIndex "
                    "WHERE media_id = ? AND deleted = 0 AND kind IN ('section','header') AND LOWER(title) LIKE LOWER(?) "
                    "ORDER BY COALESCE(level,0) DESC, (end_char - start_char) DESC LIMIT 1",
                    (media_id, pattern),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return (int(row["start_char"]), int(row["end_char"]), str(row["title"]))
        except Exception:
            return None
        except Exception as exc:
            logging.error(f"Unexpected error in transaction: {type(exc).__name__} - {exc}")
            raise DatabaseError(f"Unexpected error processing media: {exc}") from exc


    def create_document_version(self, media_id: int, content: str, prompt: Optional[str] = None, analysis_content: Optional[str] = None, safe_metadata: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a new version entry in the DocumentVersions table.

        Assigns the next available `version_number` for the given `media_id`.
        Generates a UUID for the version, sets timestamps, and logs a 'create'
        sync event for the `DocumentVersions` entity.

        This method assumes it's called within an existing transaction context
        (e.g., initiated by `add_media_with_keywords` or `rollback_to_version`).

        Args:
            media_id (int): The ID of the parent Media item.
            content (str): The content for this document version. Required.
            prompt (Optional[str]): The prompt associated with this version, if any.
            analysis_content (Optional[str]): Analysis or summary for this version.

        Returns:
            Dict[str, Any]: A dictionary containing the new version's 'id', 'uuid',
                            'media_id', and 'version_number'.

        Raises:
            InputError: If `content` is None or the parent `media_id` does not exist
                        or is deleted.
            DatabaseError: For database errors during insert or sync logging.
        """
        if content is None:
            raise InputError("Content is required for a document version.")
        current_time = self._get_current_utc_timestamp_str()   # Get time
        client_id = self.client_id
        new_uuid = self._generate_uuid()
        new_version = 1  # Sync version for the DocumentVersion entity itself

        # Assumes called within an existing transaction (e.g., from add_media_with_keywords)
        conn = self.get_connection()
        try:
            def _exec(query: str, params: Optional[Union[Tuple, List, Dict]] = None):
                return self._execute_with_connection(conn, query, params)

            def _fetchone(query: str, params: Optional[Union[Tuple, List, Dict]] = None):
                return self._fetchone_with_connection(conn, query, params)

            media_info = _fetchone(
                "SELECT uuid FROM Media WHERE id = ? AND deleted = 0",
                (media_id,),
            )
            if not media_info:
                raise InputError(f"Parent Media ID {media_id} not found or deleted.")
            media_uuid = media_info['uuid']

            next_version_row = _fetchone(
                'SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM DocumentVersions WHERE media_id = ?',
                (media_id,),
            )
            local_version_number = next_version_row['next_version'] if next_version_row else 1
            logger.debug(f"Creating document version {local_version_number} for media ID {media_id}, UUID {new_uuid}")

            insert_data = {  # Prepare dict for easier payload generation
                'media_id': media_id, 'version_number': local_version_number, 'content': content, 'prompt': prompt,
                'analysis_content': analysis_content,
                'safe_metadata': safe_metadata,
                'created_at': current_time,  # Set created_at
                'uuid': new_uuid,
                'last_modified': current_time,  # Set last_modified
                'version': new_version, 'client_id': client_id, 'deleted': 0,
                'media_uuid': media_uuid  # Add parent uuid for context in payload
            }
            try:
                insert_sql = """
                    INSERT INTO DocumentVersions (
                        media_id, version_number, content, prompt, analysis_content, safe_metadata, created_at,
                        uuid, last_modified, version, client_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                insert_params = (
                    insert_data['media_id'],
                    insert_data['version_number'],
                    insert_data['content'],
                    insert_data['prompt'],
                    insert_data['analysis_content'],
                    insert_data['safe_metadata'],
                    insert_data['created_at'],
                    insert_data['uuid'],
                    insert_data['last_modified'],
                    insert_data['version'],
                    insert_data['client_id'],
                )
                if self.backend_type == BackendType.POSTGRESQL:
                    insert_sql += " RETURNING id"
                insert_cursor = _exec(insert_sql, insert_params)
            except DatabaseError as oe:
                message = str(oe).lower()
                if "safe_metadata" in message and "no column" in message:
                    insert_sql = """
                        INSERT INTO DocumentVersions (
                            media_id, version_number, content, prompt, analysis_content, created_at,
                            uuid, last_modified, version, client_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    insert_params = (
                        insert_data['media_id'],
                        insert_data['version_number'],
                        insert_data['content'],
                        insert_data['prompt'],
                        insert_data['analysis_content'],
                        insert_data['created_at'],
                        insert_data['uuid'],
                        insert_data['last_modified'],
                        insert_data['version'],
                        insert_data['client_id'],
                    )
                    insert_data['safe_metadata'] = None
                    if self.backend_type == BackendType.POSTGRESQL:
                        insert_sql += " RETURNING id"
                    insert_cursor = _exec(insert_sql, insert_params)
                else:
                    raise
            if self.backend_type == BackendType.POSTGRESQL:
                inserted_row = insert_cursor.fetchone()
                version_id = inserted_row['id'] if inserted_row else None
            else:
                version_id = insert_cursor.lastrowid
            if not version_id:
                raise DatabaseError("Failed to get last row ID for new document version.")

            # Populate identifiers table if present
            try:
                if insert_data.get('safe_metadata'):
                    import json as _json
                    try:
                        smd = _json.loads(insert_data['safe_metadata']) if isinstance(insert_data['safe_metadata'], str) else insert_data['safe_metadata']
                    except Exception:
                        smd = None
                    if isinstance(smd, dict):
                        doi = smd.get('doi') or smd.get('DOI')
                        pmid = smd.get('pmid') or smd.get('PMID')
                        pmcid = smd.get('pmcid') or smd.get('PMCID')
                        arxiv_id = smd.get('arxiv_id') or smd.get('arxiv') or smd.get('ArXiv')
                        s2id = smd.get('s2_paper_id') or smd.get('paperId')
                        try:
                            if self.backend_type == BackendType.POSTGRESQL:
                                ident_sql = (
                                    "INSERT INTO DocumentVersionIdentifiers (dv_id, doi, pmid, pmcid, arxiv_id, s2_paper_id) "
                                    "VALUES (?, ?, ?, ?, ?, ?) "
                                    "ON CONFLICT (dv_id) DO UPDATE SET "
                                    "doi = EXCLUDED.doi, pmid = EXCLUDED.pmid, pmcid = EXCLUDED.pmcid, "
                                    "arxiv_id = EXCLUDED.arxiv_id, s2_paper_id = EXCLUDED.s2_paper_id"
                                )
                            else:
                                ident_sql = (
                                    "INSERT OR REPLACE INTO DocumentVersionIdentifiers (dv_id, doi, pmid, pmcid, arxiv_id, s2_paper_id) "
                                    "VALUES (?, ?, ?, ?, ?, ?)"
                                )
                            _exec(
                                ident_sql,
                                (version_id, doi, pmid, pmcid, arxiv_id, s2id),
                            )
                        except DatabaseError:
                            # Table may not exist; ignore
                            pass
            except Exception as _ident_ex:
                logging.warning(f"Could not populate identifiers for version_id={version_id}: {_ident_ex}")

            self._log_sync_event(conn, 'DocumentVersions', new_uuid, 'create', new_version, insert_data)
            return {'id': version_id, 'uuid': new_uuid, 'media_id': media_id, 'version_number': local_version_number}
        except (InputError, DatabaseError, sqlite3.Error) as e:
            if "foreign key constraint failed" in str(e).lower():
                logger.error(f"Failed create document version: Media ID {media_id} not found.", exc_info=False)
                raise InputError(f"Cannot create document version: Media ID {media_id} not found.") from e
            logger.error(f"DB error creating document version media {media_id}: {e}", exc_info=True)
            if isinstance(e, (InputError, DatabaseError)):
                raise e
            else:
                raise DatabaseError(f"Failed create document version: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating document version media {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error creating document version: {e}") from e

    def update_keywords_for_media(
        self,
        media_id: int,
        keywords: List[str],
        conn: Optional[Any] = None,
    ):
        """
        Synchronizes the keywords linked to a specific media item.

        Compares the provided list of keywords with the currently linked active
        keywords. Adds missing links (calling `add_keyword` if needed for the
        keyword itself) and removes outdated links. Logs 'link' and 'unlink'
        sync events for changes in the `MediaKeywords` junction table.

        Assumes it's called within an existing transaction context.

        Args:
            media_id (int): The ID of the Media item whose keywords to update.
            keywords (List[str]): The desired list of keyword strings for the media item.
                                  Empty list removes all keywords.

        Returns:
            bool: True if the operation completed (even if no changes were needed).

        Raises:
            InputError: If the parent `media_id` does not exist or is deleted.
            DatabaseError: For underlying database errors, issues adding keywords,
                           or sync logging failures.
            ConflictError: If `add_keyword` encounters a conflict during undelete.
        """
        valid_keywords = sorted(list(set([k.strip().lower() for k in keywords if k and k.strip()])))
        # Assumes called within an existing transaction
        connection = conn or self.get_connection()
        try:
            media_info = self._fetchone_with_connection(
                connection,
                "SELECT uuid FROM Media WHERE id = ? AND deleted = 0",
                (media_id,),
            )
            if not media_info:
                raise InputError(f"Cannot update keywords: Media ID {media_id} not found or deleted.")
            media_uuid = media_info['uuid']

            current_rows = self._fetchall_with_connection(
                connection,
                "SELECT mk.keyword_id, k.uuid AS keyword_uuid "
                "FROM MediaKeywords mk JOIN Keywords k ON k.id = mk.keyword_id "
                "WHERE mk.media_id = ? AND k.deleted = 0",
                (media_id,),
            )
            current_links = {row['keyword_id']: row['keyword_uuid'] for row in current_rows}
            current_keyword_ids = set(current_links.keys())

            target_keyword_data = {}
            if valid_keywords:
                for kw_text in valid_keywords:
                    # Use per-keyword transaction to match legacy behavior and tests
                    # When called inside an outer transaction, this nests without starting a new BEGIN
                    kw_id, kw_uuid = self.add_keyword(kw_text)  # Handles create/undelete/logging/FTS
                    if kw_id and kw_uuid:
                        target_keyword_data[kw_id] = kw_uuid
                    else:
                        raise DatabaseError(f"Failed get/add keyword '{kw_text}'")

            target_keyword_ids = set(target_keyword_data.keys())
            ids_to_add = target_keyword_ids - current_keyword_ids
            ids_to_remove = current_keyword_ids - target_keyword_ids
            link_sync_version = 1

            if ids_to_remove:
                remove_placeholders = ','.join('?' * len(ids_to_remove))
                params = (media_id, *list(ids_to_remove))
                self._execute_with_connection(
                    connection,
                    f"DELETE FROM MediaKeywords WHERE media_id = ? AND keyword_id IN ({remove_placeholders})",
                    params,
                )
                for removed_id in ids_to_remove:
                    keyword_uuid = current_links.get(removed_id)
                    if keyword_uuid:
                        link_uuid = f"{media_uuid}_{keyword_uuid}"
                        payload = {'media_uuid': media_uuid, 'keyword_uuid': keyword_uuid}
                        self._log_sync_event(connection, 'MediaKeywords', link_uuid, 'unlink', link_sync_version, payload)

            if ids_to_add:
                insert_params = [(media_id, kid) for kid in ids_to_add]
                insert_sql = "INSERT INTO MediaKeywords (media_id, keyword_id) VALUES (?, ?)"
                if self.backend_type == BackendType.POSTGRESQL:
                    insert_sql += " ON CONFLICT DO NOTHING"
                self._executemany_with_connection(connection, insert_sql, insert_params)
                # Log links - Note: IGNORE means we might log links that weren't actually inserted if race condition. Robust check is complex.
                for added_id in ids_to_add:
                    keyword_uuid = target_keyword_data.get(added_id)
                    if keyword_uuid:
                        link_uuid = f"{media_uuid}_{keyword_uuid}"
                        payload = {'media_uuid': media_uuid, 'keyword_uuid': keyword_uuid}
                        self._log_sync_event(connection, 'MediaKeywords', link_uuid, 'link', link_sync_version, payload)

            if ids_to_add or ids_to_remove:
                logger.debug(f"Keywords updated media {media_id}. Added: {len(ids_to_add)}, Removed: {len(ids_to_remove)}.")
            else:
                logger.debug(f"No keyword changes media {media_id}.")
            return True
        except (InputError, ConflictError, DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error updating keywords media {media_id}: {e}", exc_info=True)
            if isinstance(e, (InputError, ConflictError, DatabaseError)):
                raise e
            else:
                raise DatabaseError(f"Keyword update failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected keywords error media {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected keyword update error: {e}") from e

    def soft_delete_keyword(self, keyword: str) -> bool:
        """
        Soft deletes a keyword by setting its 'deleted' flag to 1.

        Handles case-insensitivity. Increments the version number, updates
        `last_modified`, logs a 'delete' sync event for the Keyword, and removes
        its FTS entry. It also removes all links between this keyword and any
        media items in the `MediaKeywords` table, logging 'unlink' events for each.

        Args:
            keyword (str): The keyword text to soft delete (case-insensitive).

        Returns:
            bool: True if the keyword was successfully soft-deleted,
                  False if the keyword was not found or already deleted.

        Raises:
            InputError: If the keyword string is empty or whitespace only.
            ConflictError: If the keyword's version has changed since being read.
            DatabaseError: For other database errors or sync logging failures.
        """
        if not keyword or not keyword.strip():
            raise InputError("Keyword cannot be empty.")
        keyword = keyword.strip().lower()
        current_time = self._get_current_utc_timestamp_str()  # Get time
        client_id = self.client_id

        try:
            with self.transaction() as conn:
                keyword_info = self._fetchone_with_connection(
                    conn,
                    "SELECT id, uuid, version FROM Keywords WHERE keyword = ? AND deleted = 0",
                    (keyword,),
                )
                if not keyword_info:
                    logger.warning(f"Keyword '{keyword}' not found/deleted.")
                    return False

                keyword_id = keyword_info['id']
                keyword_uuid = keyword_info['uuid']
                current_version = keyword_info['version']
                new_version = current_version + 1

                logger.info(f"Soft deleting keyword '{keyword}' (ID: {keyword_id}). New ver: {new_version}")
                update_cursor = self._execute_with_connection(
                    conn,
                    "UPDATE Keywords SET deleted=1, last_modified=?, version=?, client_id=? WHERE id=? AND version=?",
                    (current_time, new_version, client_id, keyword_id, current_version),
                )
                if getattr(update_cursor, "rowcount", 0) == 0:
                    raise ConflictError("Keywords", keyword_id)

                delete_payload = {
                    'uuid': keyword_uuid,
                    'last_modified': current_time,
                    'version': new_version,
                    'client_id': client_id,
                    'deleted': 1,
                }
                self._log_sync_event(conn, 'Keywords', keyword_uuid, 'delete', new_version, delete_payload)
                self._delete_fts_keyword(conn, keyword_id)

                linked_cursor = self._execute_with_connection(
                    conn,
                    "SELECT mk.media_id, m.uuid AS media_uuid FROM MediaKeywords mk JOIN Media m ON mk.media_id = m.id WHERE mk.keyword_id = ? AND m.deleted = 0",
                    (keyword_id,),
                )
                media_to_unlink = linked_cursor.fetchall()
                if media_to_unlink:
                    media_mappings: List[Dict[str, Any]] = []
                    for record in media_to_unlink:
                        if isinstance(record, dict):
                            media_mappings.append(record)
                            continue
                        try:
                            media_mappings.append(dict(record))
                        except Exception:
                            try:
                                media_id_val = record[0]
                            except Exception:
                                media_id_val = None
                            media_uuid_val = None
                            try:
                                media_uuid_val = record[1]
                            except Exception:
                                pass
                            media_mappings.append(
                                {
                                    "media_id": media_id_val,
                                    "media_uuid": media_uuid_val,
                                }
                            )

                    media_ids = [mapping["media_id"] for mapping in media_mappings if mapping.get("media_id") is not None]
                    if media_ids:
                        placeholders = ",".join("?" for _ in media_ids)
                        delete_cursor = self._execute_with_connection(
                            conn,
                            f"DELETE FROM MediaKeywords WHERE keyword_id = ? AND media_id IN ({placeholders})",
                            (keyword_id, *media_ids),
                        )
                        deleted_link_count = getattr(delete_cursor, "rowcount", 0) or 0
                        unlink_version = 1
                        for mapping in media_mappings:
                            media_uuid_val = mapping.get("media_uuid")
                            link_uuid = f"{media_uuid_val}_{keyword_uuid}"
                            unlink_payload = {
                                'media_uuid': media_uuid_val,
                                'keyword_uuid': keyword_uuid,
                            }
                            self._log_sync_event(conn, 'MediaKeywords', link_uuid, 'unlink', unlink_version, unlink_payload)
                        logger.info(f"Unlinked keyword '{keyword}' from {deleted_link_count} items.")
            return True
        except (InputError, ConflictError, DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error soft delete keyword '{keyword}': {e}", exc_info=True)
            if isinstance(e, (InputError, ConflictError, DatabaseError)):
                raise e
            else:
                raise DatabaseError(f"Failed soft delete keyword: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected soft delete keyword error '{keyword}': {e}", exc_info=True)
            raise DatabaseError(f"Unexpected soft delete keyword error: {e}") from e

    def soft_delete_document_version(self, version_uuid: str) -> bool:
        """
        Soft deletes a specific DocumentVersion by its UUID.

        Prevents deletion if it's the last remaining active version for the media item.
        Increments the sync version, updates `last_modified`, and logs a 'delete'
        sync event for the `DocumentVersions` entity.

        Args:
            version_uuid (str): The UUID of the DocumentVersion to soft delete.

        Returns:
            bool: True if successfully soft-deleted, False if not found, already
                  deleted, or if it's the last active version.

        Raises:
            InputError: If `version_uuid` is empty or None.
            ConflictError: If the version's sync version has changed concurrently.
            DatabaseError: For other database errors or sync logging failures.
        """
        if not version_uuid:
            raise InputError("Version UUID required.")
        current_time = self._get_current_utc_timestamp_str()  # Get time
        client_id = self.client_id
        logger.debug(f"Attempting soft delete DocVersion UUID: {version_uuid}")
        try:
            with self.transaction() as conn:
                version_info = self._fetchone_with_connection(
                    conn,
                    "SELECT dv.id, dv.media_id, dv.version, m.uuid as media_uuid "
                    "FROM DocumentVersions dv "
                    "JOIN Media m ON dv.media_id = m.id "
                    "WHERE dv.uuid = ? AND dv.deleted = 0",
                    (version_uuid,),
                )
                if not version_info:
                    logger.warning(f"DocVersion UUID {version_uuid} not found/deleted.")
                    return False
                version_id = version_info['id']
                media_id = version_info['media_id']
                current_sync_version = version_info['version']
                media_uuid = version_info['media_uuid']
                new_sync_version = current_sync_version + 1

                active_row = self._fetchone_with_connection(
                    conn,
                    "SELECT COUNT(*) AS active_count FROM DocumentVersions WHERE media_id = ? AND deleted = 0",
                    (media_id,),
                )
                active_count = int((active_row or {}).get('active_count', 0))
                if active_count <= 1:
                    logger.warning(f"Cannot delete DocVersion UUID {version_uuid} - last active.")
                    return False

                update_cursor = self._execute_with_connection(
                    conn,
                    "UPDATE DocumentVersions SET deleted=1, last_modified=?, version=?, client_id=? WHERE id=? AND version=?",
                    (current_time, new_sync_version, client_id, version_id, current_sync_version),
                )
                if getattr(update_cursor, "rowcount", 0) == 0:
                    raise ConflictError("DocumentVersions", version_id)

                delete_payload = {
                    'uuid': version_uuid,
                    'media_uuid': media_uuid,
                    'last_modified': current_time,
                    'version': new_sync_version,
                    'client_id': client_id,
                    'deleted': 1,
                }
                self._log_sync_event(conn, 'DocumentVersions', version_uuid, 'delete', new_sync_version, delete_payload)
                logger.info(f"Soft deleted DocVersion UUID {version_uuid}. New ver: {new_sync_version}")
                return True
        except (InputError, ConflictError, DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error soft delete DocVersion UUID {version_uuid}: {e}", exc_info=True)
            if isinstance(e, (InputError, ConflictError, DatabaseError)):
                raise e
            else:
                raise DatabaseError(f"Failed soft delete doc version: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected soft delete DocVersion error UUID {version_uuid}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected version soft delete error: {e}") from e

    def mark_as_trash(self, media_id: int) -> bool:
        """
        Marks a media item as 'trash' (is_trash=1) without soft deleting it.

        Sets the `trash_date`, updates `last_modified`, increments the sync version,
        and logs an 'update' sync event for the Media item. Does not affect FTS.

        Args:
            media_id (int): The ID of the Media item to move to trash.

        Returns:
            bool: True if successfully marked as trash, False if not found, deleted,
                  or already in trash.

        Raises:
            ConflictError: If the media item's version has changed concurrently.
            DatabaseError: For other database errors or sync logging failures.
        """
        current_time = self._get_current_utc_timestamp_str()  # Get time
        client_id = self.client_id
        logger.debug(f"Marking media {media_id} as trash.")
        try:
            with self.transaction() as conn:
                media_info = self._fetchone_with_connection(
                    conn,
                    "SELECT uuid, version, is_trash FROM Media WHERE id = ? AND deleted = 0",
                    (media_id,),
                )
                if not media_info:
                    logger.warning(f"Cannot trash: Media {media_id} not found/deleted.")
                    return False
                if media_info['is_trash']:
                    logger.warning(f"Media {media_id} already in trash.")
                    return False  # No change needed
                media_uuid, current_version = media_info['uuid'], media_info['version']
                new_version = current_version + 1

                # Pass current_time for both trash_date and last_modified
                update_cursor = self._execute_with_connection(
                    conn,
                    "UPDATE Media SET is_trash=1, trash_date=?, last_modified=?, version=?, client_id=? WHERE id=? AND version=?",
                    (current_time, current_time, new_version, client_id, media_id, current_version),
                )
                if update_cursor.rowcount == 0:
                    raise ConflictError("Media", media_id)

                sync_payload = self._fetchone_with_connection(
                    conn,
                    "SELECT * FROM Media WHERE id = ?",
                    (media_id,),
                ) or {}
                self._log_sync_event(conn, 'Media', media_uuid, 'update', new_version, sync_payload)
                # No FTS change needed for trash status itself
                logger.info(f"Media {media_id} marked as trash. New ver: {new_version}")
                return True
        except (ConflictError, DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error marking media {media_id} as trash: {e}", exc_info=True)
            if isinstance(e, (ConflictError, DatabaseError)):
                raise e
            else:
                raise DatabaseError(f"Failed mark as trash: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error marking media {media_id} trash: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected mark trash error: {e}") from e

    def restore_from_trash(self, media_id: int) -> bool:
        """
        Restores a media item from 'trash' (sets is_trash=0, trash_date=NULL).

        Updates `last_modified`, increments the sync version, and logs an 'update'
        sync event for the Media item. Does not affect FTS.

        Args:
            media_id (int): The ID of the Media item to restore.

        Returns:
            bool: True if successfully restored, False if not found, deleted,
                  or not currently in trash.

        Raises:
            ConflictError: If the media item's version has changed concurrently.
            DatabaseError: For other database errors or sync logging failures.
        """
        current_time = self._get_current_utc_timestamp_str()  # Get time
        client_id = self.client_id
        logger.debug(f"Restoring media {media_id} from trash.")
        try:
            with self.transaction() as conn:
                media_info = self._fetchone_with_connection(
                    conn,
                    "SELECT uuid, version, is_trash FROM Media WHERE id = ? AND deleted = 0",
                    (media_id,),
                )
                if not media_info:
                    logger.warning(f"Cannot restore: Media {media_id} not found/deleted.")
                    return False
                if not media_info['is_trash']:
                    logger.warning(f"Cannot restore: Media {media_id} not in trash.")
                    return False  # No change needed
                media_uuid, current_version = media_info['uuid'], media_info['version']
                new_version = current_version + 1

                # Pass current_time for last_modified, set trash_date to NULL
                update_cursor = self._execute_with_connection(
                    conn,
                    "UPDATE Media SET is_trash=0, trash_date=NULL, last_modified=?, version=?, client_id=? WHERE id=? AND version=?",
                    (current_time, new_version, client_id, media_id, current_version),
                )
                if update_cursor.rowcount == 0:
                    raise ConflictError("Media", media_id)

                sync_payload = self._fetchone_with_connection(
                    conn,
                    "SELECT * FROM Media WHERE id = ?",
                    (media_id,),
                ) or {}
                self._log_sync_event(conn, 'Media', media_uuid, 'update', new_version, sync_payload)
                # No FTS change needed
                logger.info(f"Media {media_id} restored from trash. New ver: {new_version}")
                return True
        except (ConflictError, DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error restoring media {media_id} trash: {e}", exc_info=True)
            if isinstance(e, (ConflictError, DatabaseError)):
                raise e
            else:
                raise DatabaseError(f"Failed restore trash: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error restoring media {media_id} trash: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected restore trash error: {e}") from e

    def rollback_to_version(self, media_id: int, target_version_number: int) -> Dict[str, Any]:
        """
        Rolls back the main Media content to a previous DocumentVersion state.

        This involves:
        1. Fetching the content from the specified target `DocumentVersion`.
        2. Creating a *new* `DocumentVersion` entry containing this rolled-back content.
        3. Updating the main `Media` record's content, content_hash, `last_modified`,
           and incrementing its sync version.
        4. Logging 'create' for the new DocumentVersion and 'update' for the Media item.
        5. Updating the `media_fts` table with the rolled-back content.

        Prevents rolling back to the absolute latest version number.

        Args:
            media_id (int): The ID of the Media item to roll back.
            target_version_number (int): The `version_number` of the DocumentVersion
                                         to roll back to. Must be a positive integer.

        Returns:
            Dict[str, Any]: A dictionary containing either:
                - {'success': message, 'new_document_version_number': int,
                   'new_document_version_uuid': str, 'new_media_version': int}
                - {'error': message} if the rollback failed (e.g., version not found,
                  media not found, target is latest version).

        Raises:
            ValueError: If `target_version_number` is invalid.
            InputError: If underlying `create_document_version` fails input checks.
            ConflictError: If the Media item's version changed concurrently during update.
            DatabaseError: For other database errors or sync/FTS logging issues.
        """
        if not isinstance(target_version_number, int) or target_version_number < 1:
            raise ValueError("Target version invalid.")
        client_id = self.client_id
        current_time = self._get_current_utc_timestamp_str()  # Get time
        logger.debug(f"Rolling back media {media_id} to doc version {target_version_number}.")
        try:
            with self.transaction() as conn:
                # Get current media info
                media_info = self._fetchone_with_connection(
                    conn,
                    "SELECT uuid, version, title FROM Media WHERE id = ? AND deleted = 0",
                    (media_id,),
                )
                if not media_info:
                    return {'error': f'Media {media_id} not found or deleted.'}
                media_uuid, current_media_version, current_title = media_info['uuid'], media_info['version'], media_info['title']
                new_media_version = current_media_version + 1

                # Get target document version data (using standalone function)
                target_version_data = get_document_version(self, media_id, target_version_number, True)
                if target_version_data is None:
                    return {'error': f'Rollback target version {target_version_number} not found or inactive.'}

                # Prevent rolling back to the absolute latest version number
                latest_vn_row = self._fetchone_with_connection(
                    conn,
                    "SELECT MAX(version_number) AS latest_vn FROM DocumentVersions WHERE media_id=? AND deleted=0",
                    (media_id,),
                )
                latest_vn = latest_vn_row['latest_vn'] if latest_vn_row else None
                if latest_vn is not None and target_version_number == latest_vn:
                    return {'error': 'Cannot rollback to the current latest version number.'}

                target_content = target_version_data.get('content')
                target_prompt = target_version_data.get('prompt')
                target_analysis = target_version_data.get('analysis_content')
                if target_content is None:
                    return {'error': f'Version {target_version_number} has no content.'}

                # 1. Create new doc version representing the rollback state (handles its own logging & timestamps)
                new_doc_version_info = self.create_document_version(media_id=media_id, content=target_content, prompt=target_prompt, analysis_content=target_analysis)
                new_doc_version_number = new_doc_version_info.get('version_number')
                new_doc_version_uuid = new_doc_version_info.get('uuid')

                # 2. Update the Media table with the rolled-back content and new hash/timestamp
                new_content_hash = hashlib.sha256(target_content.encode()).hexdigest()
                # Pass current_time for last_modified
                update_cursor = self._execute_with_connection(
                    conn,
                    """UPDATE Media SET content=?, content_hash=?, last_modified=?, version=?, client_id=?,
                       chunking_status='pending', vector_processing=0 WHERE id=? AND version=?""",
                    (target_content, new_content_hash, current_time, new_media_version, client_id, media_id, current_media_version),
                )
                if update_cursor.rowcount == 0:
                    raise ConflictError("Media", media_id)

                # 3. Log the Media update sync event
                updated_media_data = self._fetchone_with_connection(
                    conn,
                    "SELECT * FROM Media WHERE id = ?",
                    (media_id,),
                ) or {}
                # Add context about the rollback to the payload (optional but helpful)
                updated_media_data['rolled_back_to_doc_ver_uuid'] = new_doc_version_uuid
                updated_media_data['rolled_back_to_doc_ver_num'] = new_doc_version_number
                self._log_sync_event(conn, 'Media', media_uuid, 'update', new_media_version, updated_media_data)

                # 4. Update FTS for the Media item
                self._update_fts_media(conn, media_id, current_title, target_content)  # Use original title, new content

            logger.info(f"Rolled back media {media_id} to state of doc ver {target_version_number}. New DocVer: {new_doc_version_number}, New MediaVer: {new_media_version}")
            # Re-anchoring: mark reading highlights stale after rollback content change
            try:
                if _CollectionsDB is not None and client_id is not None:
                    _CollectionsDB.from_backend(user_id=str(client_id), backend=self.backend).mark_highlights_stale_if_content_changed(media_id, new_content_hash)
            except Exception as _anch_err:
                logging.debug(f"Highlight re-anchoring hook (rollback) failed: {_anch_err}")
            # Invalidate agentic intra-doc vectors after content rollback
            try:
                from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import invalidate_intra_doc_vectors  # lazy import
                invalidate_intra_doc_vectors(str(media_id))
            except Exception:
                pass
            return {'success': f'Rolled back to version {target_version_number}. State saved as new version {new_doc_version_number}.',
                    'new_document_version_number': new_doc_version_number,
                    'new_document_version_uuid': new_doc_version_uuid,
                    'new_media_version': new_media_version}
        except (InputError, ValueError, ConflictError, DatabaseError, sqlite3.Error, TypeError) as e:
            logger.error(f"Rollback error media {media_id}: {e}", exc_info=True)
            if isinstance(e, (InputError, ValueError, ConflictError, DatabaseError, TypeError)):
                raise e
            else:
                raise DatabaseError(f"DB error during rollback: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected rollback error media {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected rollback error: {e}") from e

    def get_all_document_versions(
        self,  # Add self as the first parameter
        media_id: int,
        include_content: bool = False,
        include_deleted: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = 0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all document versions for an active media item with pagination.

        Filters results to only include versions where the parent Media item is active
        (`Media.deleted = 0`). By default, only active document versions
        (`DocumentVersions.deleted = 0`) are returned, unless `include_deleted` is True.

        Includes standard V2 sync metadata columns (uuid, version, last_modified, client_id).

        Args:
            media_id (int): The ID of the parent Media item.
            include_content (bool): Whether to include the 'content' field. Defaults to False.
            include_deleted (bool): If True, include versions marked as soft-deleted
                                    (`deleted = 1`). Defaults to False.
            limit (Optional[int]): Maximum number of versions to return. None for no limit.
                                   Defaults to None.
            offset (Optional[int]): Number of versions to skip (for pagination).
                                    Defaults to 0.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a document
                                  version matching the criteria. Returns an empty list
                                  if none found.

        Raises:
            TypeError: If input arguments have wrong types.
            ValueError: If limit or offset are invalid.
            DatabaseError: For database query errors.
        """
        # --- Input Validation ---
        # No need to validate self
        if not isinstance(media_id, int):
            raise TypeError("media_id must be an integer.")
        if not isinstance(include_content, bool):
            raise TypeError("include_content must be a boolean.")
        if not isinstance(include_deleted, bool):
            raise TypeError("include_deleted must be a boolean.")
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise ValueError("Limit must be a positive integer.")
        if offset is not None and (not isinstance(offset, int) or offset < 0):
            raise ValueError("Offset must be a non-negative integer.")

        # --- Logging ---
        # Use self.db_path_str for logging context
        log_msg = (f"Getting {'all' if include_deleted else 'active'} versions for media_id={media_id} "
                   f"(Limit={limit}, Offset={offset}, Content={include_content}) "
                   f"from DB: {self.db_path_str}")  # Use self.db_path_str
        logger.debug(log_msg)

        # --- Query Construction ---
        try:
            # Select all relevant columns from DocumentVersions
            select_cols_list = [
                "dv.id", "dv.uuid", "dv.media_id", "dv.version_number", "dv.created_at",
                "dv.prompt", "dv.analysis_content", "dv.last_modified", "dv.version",
                "dv.client_id", "dv.deleted"
            ]
            if include_content:
                select_cols_list.append("dv.content")
            select_clause = ", ".join(select_cols_list)

            params = [media_id]
            where_conditions = ["dv.media_id = ?", "m.deleted = 0"]  # Always filter by active parent

            if not include_deleted:
                where_conditions.append("dv.deleted = 0")

            where_clause = " AND ".join(where_conditions)

            limit_offset_clause = ""
            if limit is not None:
                limit_offset_clause += " LIMIT ?"
                params.append(limit)
                if offset is not None and offset > 0:
                    limit_offset_clause += " OFFSET ?"
                    params.append(offset)

            final_query = f"""
                SELECT {select_clause}
                FROM DocumentVersions dv
                JOIN Media m ON dv.media_id = m.id
                WHERE {where_clause}
                ORDER BY dv.version_number DESC
                {limit_offset_clause}
            """

            # --- Execution ---
            logging.debug(f"Executing get_all_document_versions query | Params: {params}")
            # Use self.execute_query
            cursor = self.execute_query(final_query, tuple(params))
            results_raw = cursor.fetchall()

            versions_list = [dict(row) for row in results_raw]

            logging.debug(f"Found {len(versions_list)} versions for media_id={media_id}")
            return versions_list

        # --- Error Handling ---
        except sqlite3.Error as e:
            # Use self.db_path_str
            logging.error(f"SQLite error retrieving versions for media_id {media_id} from {self.db_path_str}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to retrieve document versions: {e}") from e
        except Exception as e:
            # Use self.db_path_str
            logging.error(f"Unexpected error retrieving versions for media_id {media_id} from {self.db_path_str}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred: {e}") from e

    def process_unvectorized_chunks(self, media_id: int, chunks: List[Dict[str, Any]], batch_size: int = 100):
        """
        Adds a batch of unvectorized chunk records to the database.

        Inserts records into the `UnvectorizedMediaChunks` table in batches.
        Generates a UUID, sets timestamps, and logs a 'create' sync event
        for each chunk added. Assumes parent media item exists and is active.

        Args:
            media_id (int): The ID of the parent Media item for these chunks.
            chunks (List[Dict[str, Any]]): A list of dictionaries, each representing
                a chunk. Expected keys include 'chunk_text' (or 'text'),
                'chunk_index'. Optional keys: 'start_char', 'end_char',
                'chunk_type', 'creation_date', 'last_modified_orig',
                'is_processed', 'metadata'.
            batch_size (int): Number of chunks to insert per database transaction batch.
                              Defaults to 100.

        Raises:
            InputError: If the parent `media_id` does not exist or is deleted, or if
                        essential chunk data ('chunk_text', 'chunk_index') is missing.
            DatabaseError: For database errors during insertion or sync logging.
            TypeError: If 'metadata' is provided but cannot be JSON serialized.
        """
        if not chunks:
            logger.warning(f"process_unvectorized_chunks empty list for media {media_id}.")
            return
        client_id = self.client_id
        start_time = time.time()
        total_chunks = len(chunks)
        processed_count = 0
        logger.info(f"Processing {total_chunks} unvectorized chunks for media {media_id}.")
        try:
            # Use standalone check function (assumed to exist and work)
            if not check_media_exists(self, media_id=media_id):
                raise InputError(f"Cannot add chunks: Parent Media {media_id} not found or deleted.")
            with self.transaction() as conn:
                media_info = self._fetchone_with_connection(
                    conn,
                    "SELECT uuid FROM Media WHERE id = ? AND deleted = 0",
                    (media_id,),
                )
                if not media_info:
                    raise InputError(f"Cannot add chunks: Parent Media ID {media_id} UUID not found.")
                media_uuid = media_info['uuid']

                for i in range(0, total_chunks, batch_size):
                    batch = chunks[i:i + batch_size]
                    chunk_params = []
                    log_events_data = []
                    current_time = self._get_current_utc_timestamp_str()  # Get time for the batch
                    for chunk_dict in batch:
                        chunk_uuid = self._generate_uuid()
                        chunk_text = chunk_dict.get('chunk_text', chunk_dict.get('text'))
                        chunk_index = chunk_dict.get('chunk_index')
                        if chunk_text is None or chunk_index is None:
                            logger.warning(f"Skipping chunk missing text/index media {media_id}")
                            continue

                        new_sync_version = 1
                        insert_data = {  # Match table schema
                            'media_id': media_id, 'chunk_text': chunk_text, 'chunk_index': chunk_index,
                            'start_char': chunk_dict.get('start_char'), 'end_char': chunk_dict.get('end_char'),
                            'chunk_type': chunk_dict.get('chunk_type'),
                            # Use current_time if not provided in chunk_dict
                            'creation_date': chunk_dict.get('creation_date') or current_time,
                            'last_modified_orig': chunk_dict.get('last_modified_orig') or current_time,
                            'is_processed': chunk_dict.get('is_processed', False),
                            # Ensure metadata is JSON string
                            'metadata': json.dumps(chunk_dict.get('metadata')) if chunk_dict.get('metadata') else None,
                            'uuid': chunk_uuid,
                            'last_modified': current_time,  # Set sync last_modified
                            'version': new_sync_version, 'client_id': client_id, 'deleted': 0,
                            'media_uuid': media_uuid  # for payload context
                        }
                        params = (  # Order must match SQL query
                            insert_data['media_id'], insert_data['chunk_text'], insert_data['chunk_index'],
                            insert_data['start_char'], insert_data['end_char'], insert_data['chunk_type'],
                            insert_data['creation_date'],  # Pass creation_date
                            insert_data['last_modified_orig'],  # Pass last_modified_orig
                            insert_data['is_processed'], insert_data['metadata'], insert_data['uuid'],
                            insert_data['last_modified'],  # Pass sync last_modified
                            insert_data['version'], insert_data['client_id'], insert_data['deleted']
                        )
                        chunk_params.append(params)
                        # Pass the full insert_data as payload
                        log_events_data.append((chunk_uuid, new_sync_version, insert_data))

                    if not chunk_params:
                        continue
                    # Ensure columns match params order
                    sql = """INSERT INTO UnvectorizedMediaChunks (media_id, chunk_text, chunk_index, start_char, end_char, chunk_type,
                               creation_date, last_modified_orig, is_processed, metadata, uuid,
                               last_modified, version, client_id, deleted) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                    self._executemany_with_connection(conn, sql, chunk_params)
                    actual_inserted = len(chunk_params)  # executemany doesn't give reliable rowcount

                    for chunk_uuid_log, version_log, payload_log in log_events_data:
                        self._log_sync_event(conn, 'UnvectorizedMediaChunks', chunk_uuid_log, 'create', version_log, payload_log)
                    processed_count += actual_inserted
                    logger.debug(f"Processed batch {i//batch_size+1}: Inserted {actual_inserted} chunks for media {media_id}.")
            duration = time.time() - start_time
            logger.info(f"Finished processing {processed_count} unvectorized chunks media {media_id}. Duration: {duration:.4f}s")
        except (InputError, DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error processing unvectorized chunks media {media_id}: {e}", exc_info=True)
            if isinstance(e, (InputError, DatabaseError)):
                raise e
            else:
                raise DatabaseError(f"Failed process chunks: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected chunk processing error media {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected chunk error: {e}") from e

    # --- Read Methods (Ensure they filter by deleted=0) ---
    def fetch_all_keywords(self) -> List[str]:
        """
        Fetches all *active* (non-deleted) keywords from the database.

        Returns:
            List[str]: A sorted list of active keyword strings (lowercase).
                       Returns an empty list if no active keywords are found.

        Raises:
            DatabaseError: If the database query fails.
        """
        try:
            order_expr = self._keyword_order_expression("keyword")
            query = f"SELECT keyword FROM Keywords WHERE deleted = ? ORDER BY {order_expr}"
            cursor = self.execute_query(query, (False,))
            return [row['keyword'] for row in cursor.fetchall()]
        except DatabaseError as e:
            logger.error(f"Error fetching keywords: {e}")
            raise

    def get_paginated_media_list(self, page: int = 1, results_per_page: int = 10) -> Tuple[
        List[Dict[str, Any]], int, int, int]:
        """
        Fetches a paginated list of active media items (id, title, type, uuid)
        for the media listing endpoint.

        Filters for items where deleted = 0 and is_trash = 0.
        Returns data suitable for constructing MediaListItem objects.

        Args:
            page (int): The page number (1-based).
            results_per_page (int): Number of items per page.

        Returns:
            Tuple[List[Dict[str, Any]], int, int, int]:
                - results (List[Dict]): List of dictionaries for the current page.
                                       Each dict contains 'id', 'title', 'type', 'uuid'.
                - total_pages (int): Total number of pages.
                - current_page (int): The requested page number.
                - total_items (int): Total number of active items.

        Raises:
            ValueError: If page or results_per_page are invalid.
            DatabaseError: If a database query fails.
        """
        if page < 1:
            raise ValueError("Page number must be 1 or greater.")
        if results_per_page < 1:
            raise ValueError("Results per page must be 1 or greater.")

        logging.debug(
            f"DB: Fetching paginated media list: page={page}, rpp={results_per_page} from {self.db_path_str}"
        )
        offset = (page - 1) * results_per_page

        try:
            count_cursor = self.execute_query(
                "SELECT COUNT(*) AS total_items FROM Media WHERE deleted = 0 AND is_trash = 0"
            )
            count_row = count_cursor.fetchone()
            total_items = count_row['total_items'] if count_row else 0

            results_data: List[Dict[str, Any]] = []
            if total_items > 0:
                items_cursor = self.execute_query(
                    """
                    SELECT id, title, type, uuid
                    FROM Media
                    WHERE deleted = 0
                      AND is_trash = 0
                    ORDER BY last_modified DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (results_per_page, offset),
                )
                results_data = [dict(row) for row in items_cursor.fetchall()]

            total_pages = ceil(total_items / results_per_page) if total_items > 0 else 0
            if page > total_pages and total_pages == 0:
                results_data = []

            return results_data, total_pages, page, total_items

        except DatabaseError:
            raise
        except sqlite3.Error as e:
            logging.error(f"SQLite error during DB pagination: {e}", exc_info=True)
            raise DatabaseError(f"Failed DB pagination query: {e}") from e
        except Exception as e:
            logging.error(f"Unexpected error during DB pagination: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error during DB pagination: {e}") from e

    def get_media_by_id(self, media_id: int, include_deleted=False, include_trash=False) -> Optional[Dict]:
        """
        Retrieves a single media item by its primary key (ID).

        By default, only returns active (non-deleted, non-trash) items.

        Args:
            media_id (int): The integer ID of the media item.
            include_deleted (bool): If True, include items marked as soft-deleted
                                    (`deleted = 1`). Defaults to False.
            include_trash (bool): If True, include items marked as trash
                                  (`is_trash = 1`), provided they are not also
                                  soft-deleted (unless `include_deleted` is True).
                                  Defaults to False.

        Returns:
            Optional[Dict[str, Any]]: A dictionary representing the media item if found
                                      matching the criteria, otherwise None.

        Raises:
            InputError: If `media_id` is not an integer.
            DatabaseError: If a database query error occurs.
        """
        if not isinstance(media_id, int):
            raise InputError("media_id must be an integer.")

        query = "SELECT * FROM Media WHERE id = ?"
        params = [media_id]

        if not include_deleted:
            query += " AND deleted = 0"
        if not include_trash:
            query += " AND is_trash = 0"

        try:
            cursor = self.execute_query(query, tuple(params))
            result = cursor.fetchone()
            return dict(result) if result else None
        except sqlite3.Error as e:
            logger.error(f"Error fetching media by ID {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch media by ID: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching media by ID {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error fetching media by ID: {e}") from e

    # ------------------------------------------------------------------------
    # Unvectorized chunk helpers (read-only)
    # ------------------------------------------------------------------------
    def has_unvectorized_chunks(self, media_id: int) -> bool:
        """Return True if UnvectorizedMediaChunks exist for the media item."""
        try:
            cur = self.execute_query(
                "SELECT 1 FROM UnvectorizedMediaChunks WHERE media_id = ? AND deleted = 0 LIMIT 1",
                (media_id,),
            )
            return cur.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking unvectorized chunks for media {media_id}: {e}")
            return False

    def get_unvectorized_anchor_index_for_offset(self, media_id: int, approx_offset: int) -> Optional[int]:
        """
        Best-effort mapping from an approximate character offset in the full
        content to a prechunked chunk_index using UnvectorizedMediaChunks.

        Prefers ranges where start_char/end_char are present. Returns None when
        mapping can't be determined.
        """
        try:
            # Prefer explicit start/end range match
            cur = self.execute_query(
                """
                SELECT chunk_index
                FROM UnvectorizedMediaChunks
                WHERE media_id = ? AND deleted = 0 AND start_char IS NOT NULL AND end_char IS NOT NULL
                  AND start_char <= ? AND end_char > ?
                ORDER BY chunk_index ASC
                LIMIT 1
                """,
                (media_id, approx_offset, approx_offset),
            )
            row = cur.fetchone()
            if row:
                return int(row["chunk_index"]) if isinstance(row, dict) else int(row[0])
            return None
        except sqlite3.Error as e:
            logger.error(f"Error locating anchor chunk for media {media_id} at offset {approx_offset}: {e}")
            return None

    def get_unvectorized_chunk_index_by_uuid(self, media_id: int, chunk_uuid: str) -> Optional[int]:
        """Return chunk_index for a given chunk UUID if present."""
        try:
            cur = self.execute_query(
                "SELECT chunk_index FROM UnvectorizedMediaChunks WHERE media_id = ? AND uuid = ? AND deleted = 0",
                (media_id, chunk_uuid),
            )
            row = cur.fetchone()
            if not row:
                return None
            return int(row["chunk_index"]) if isinstance(row, dict) else int(row[0])
        except sqlite3.Error as e:
            logger.error(f"Error fetching chunk_index by UUID for media {media_id}: {e}")
            return None

    def get_unvectorized_chunks_in_range(self, media_id: int, start_index: int, end_index: int) -> List[Dict[str, Any]]:
        """
        Fetch a range of chunks [start_index, end_index] (inclusive) ordered by chunk_index.
        Returns dicts with keys: chunk_index, uuid, chunk_text, start_char, end_char, chunk_type.
        """
        if end_index < start_index:
            start_index, end_index = end_index, start_index
        try:
            cur = self.execute_query(
                """
                SELECT chunk_index, uuid, chunk_text, start_char, end_char, chunk_type
                FROM UnvectorizedMediaChunks
                WHERE media_id = ? AND deleted = 0 AND chunk_index BETWEEN ? AND ?
                ORDER BY chunk_index ASC
                """,
                (media_id, start_index, end_index),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as e:
            logger.error(
                f"Error fetching chunk range [{start_index},{end_index}] for media {media_id}: {e}")
            return []


# ----------------------------------------------------------------------------
# Composite helper: Full media details (active-only)
# ----------------------------------------------------------------------------
def get_full_media_details(db_instance: MediaDatabase, media_id: int, *, include_content: bool = True) -> Optional[Dict[str, Any]]:
    """
    Return a consolidated view of an active media item:
      - media: full Media row
      - latest_version: latest active DocumentVersion (content optionally included)
      - keywords: list[str] of active keywords

    Args:
      db_instance: MediaDatabase instance
      media_id: target media id
      include_content: include latest version content

    Returns: dict or None when media not found/active.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    # Media row (active-only)
    media = db_instance.get_media_by_id(media_id, include_deleted=False, include_trash=False)
    if not media:
        return None
    # Latest doc version
    latest = get_document_version(db_instance, media_id=media_id, version_number=None, include_content=include_content)
    # Keywords
    try:
        keywords = fetch_keywords_for_media(media_id=media_id, db_instance=db_instance)
    except Exception:
        keywords = []

    return {
        "media": media,
        "latest_version": latest,
        "keywords": keywords,
    }


def get_full_media_details_rich(
    db_instance: MediaDatabase,
    media_id: int,
    *,
    include_content: bool = True,
    include_versions: bool = True,
    include_version_content: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Build a response-shaped dictionary aligned with MediaDetailResponse for an active media item.

    Returns None when media is not active or not found.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")

    media = db_instance.get_media_by_id(media_id, include_deleted=False, include_trash=False)
    if not media:
        return None

    # Latest doc version (for prompt/analysis/safe_metadata)
    latest = get_document_version(db_instance, media_id=media_id, version_number=None, include_content=False)
    prompt = (latest or {}).get("prompt")
    analysis = (latest or {}).get("analysis_content")
    safe_metadata_raw = (latest or {}).get("safe_metadata")
    safe_metadata = None
    if isinstance(safe_metadata_raw, str):
        try:
            import json as _json
            safe_metadata = _json.loads(safe_metadata_raw)
        except Exception:
            safe_metadata = None
    elif isinstance(safe_metadata_raw, dict):
        safe_metadata = safe_metadata_raw

    # Keywords
    try:
        keywords = fetch_keywords_for_media(media_id=media_id, db_instance=db_instance)
    except Exception:
        keywords = []

    # Content and metadata parsing
    content_text = media.get("content") or ""
    content_meta: Dict[str, Any] = {}
    mtype = media.get("type")
    if mtype in ("video", "audio") and content_text:
        try:
            parts = content_text.split("\n\n", 1)
            if len(parts) == 2:
                import json as _json
                possible_json_str, remaining_text = parts[0], parts[1]
                try:
                    parsed = _json.loads(possible_json_str)
                    if isinstance(parsed, dict):
                        content_meta = parsed
                        content_text = remaining_text
                except Exception:
                    pass
        except Exception:
            pass
    word_count = len(content_text.split()) if content_text else 0

    # Versions list (lightweight by default - no content)
    versions_list: List[Dict[str, Any]] = []
    if include_versions:
        try:
            rows = db_instance.get_all_document_versions(
                media_id=media_id,
                include_content=include_version_content,
                include_deleted=False,
            )
            for rv in rows or []:
                safe_md = rv.get("safe_metadata")
                if isinstance(safe_md, str):
                    try:
                        import json as _json
                        safe_md = _json.loads(safe_md)
                    except Exception:
                        safe_md = None
                versions_list.append({
                    "uuid": rv.get("uuid"),
                    "media_id": rv.get("media_id"),
                    "version_number": rv.get("version_number"),
                    "created_at": rv.get("created_at"),
                    "prompt": rv.get("prompt"),
                    "analysis_content": rv.get("analysis_content"),
                    "safe_metadata": safe_md,
                    "content": rv.get("content") if include_version_content else None,
                })
        except Exception:
            versions_list = []

    # Build response dict matching MediaDetailResponse structure
    return {
        "media_id": media_id,
        "source": {
            "url": media.get("url"),
            "title": media.get("title"),
            "duration": media.get("duration"),
            "type": mtype,
        },
        "processing": {
            "prompt": prompt,
            "analysis": analysis,
            "safe_metadata": safe_metadata,
            "model": media.get("transcription_model"),
            "timestamp_option": media.get("timestamp_option"),
        },
        "content": {
            "metadata": content_meta,
            "text": content_text if include_content else "",
            "word_count": word_count,
        },
        "keywords": keywords,
        "timestamps": media.get("timestamps", []) or [],
        "versions": versions_list,
    }

# Add similar get_media_by_uuid, get_media_by_url, get_media_by_hash, get_media_by_title
# Ensure they include the include_deleted and include_trash filters correctly.
def get_media_by_uuid(self, media_uuid: str, include_deleted=False, include_trash=False) -> Optional[Dict]:
    """
    Retrieves a single media item by its UUID.

    By default, only returns active (non-deleted, non-trash) items. UUIDs are unique.

    Args:
        media_uuid (str): The UUID string of the media item.
        include_deleted (bool): If True, include soft-deleted items. Defaults to False.
        include_trash (bool): If True, include trashed items. Defaults to False.

    Returns:
        Optional[Dict[str, Any]]: A dictionary representing the media item if found,
                                  otherwise None.

    Raises:
        InputError: If `media_uuid` is empty or None.
        DatabaseError: If a database query error occurs.
    """
    if not media_uuid:
        raise InputError("media_uuid cannot be empty.")
    query = "SELECT * FROM Media WHERE uuid = ?"
    params = [media_uuid]
    if not include_deleted:
        query += " AND deleted = 0"
    if not include_trash:
        query += " AND is_trash = 0"
    try:
        cursor = self.execute_query(query, tuple(params))
        result = cursor.fetchone()
        return dict(result) if result else None
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error fetching media by UUID {media_uuid}: {e}")
        raise DatabaseError(f"Failed fetch media by UUID: {e}") from e

def get_media_by_url(self, url: str, include_deleted=False, include_trash=False) -> Optional[Dict]:
    """
    Retrieves a single media item by its URL.

    By default, only returns active (non-deleted, non-trash) items. URLs are unique.

    Args:
        url (str): The URL string of the media item.
        include_deleted (bool): If True, include soft-deleted items. Defaults to False.
        include_trash (bool): If True, include trashed items. Defaults to False.

    Returns:
        Optional[Dict[str, Any]]: A dictionary representing the media item if found,
                                  otherwise None.

    Raises:
        InputError: If `url` is empty or None.
        DatabaseError: If a database query error occurs.
    """
    if not url:
        raise InputError("url cannot be empty or None.")

    query = "SELECT * FROM Media WHERE url = ?"
    params = [url]

    if not include_deleted:
        query += " AND deleted = 0"
    if not include_trash:
        query += " AND is_trash = 0"

    # URLs are unique, so LIMIT 1 is implicit but doesn't hurt
    query += " LIMIT 1"

    try:
        cursor = self.execute_query(query, tuple(params))
        result = cursor.fetchone()
        return dict(result) if result else None
    except sqlite3.Error as e:
        logger.error(f"Error fetching media by URL '{url}': {e}", exc_info=True)
        raise DatabaseError(f"Failed to fetch media by URL: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error fetching media by URL '{url}': {e}", exc_info=True)
        raise DatabaseError(f"Unexpected error fetching media by URL: {e}") from e

def get_media_by_hash(self, content_hash: str, include_deleted=False, include_trash=False) -> Optional[Dict]:
    """
    Retrieves a single media item by its content hash (SHA256).

    By default, only returns active (non-deleted, non-trash) items. Hashes are unique.

    Args:
        content_hash (str): The SHA256 hash string of the media content.
        include_deleted (bool): If True, include soft-deleted items. Defaults to False.
        include_trash (bool): If True, include trashed items. Defaults to False.

    Returns:
        Optional[Dict[str, Any]]: A dictionary representing the media item if found,
                                  otherwise None.

    Raises:
        InputError: If `content_hash` is empty or None.
        DatabaseError: If a database query error occurs.
    """
    if not content_hash:
        raise InputError("content_hash cannot be empty or None.")

    query = "SELECT * FROM Media WHERE content_hash = ?"
    params = [content_hash]

    if not include_deleted:
        query += " AND deleted = 0"
    if not include_trash:
        query += " AND is_trash = 0"

    # Hashes are unique, so LIMIT 1 is implicit
    query += " LIMIT 1"

    try:
        cursor = self.execute_query(query, tuple(params))
        result = cursor.fetchone()
        return dict(result) if result else None
    except sqlite3.Error as e:
        logger.error(f"Error fetching media by hash '{content_hash[:10]}...': {e}", exc_info=True)
        raise DatabaseError(f"Failed to fetch media by hash: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error fetching media by hash '{content_hash[:10]}...': {e}", exc_info=True)
        raise DatabaseError(f"Unexpected error fetching media by hash: {e}") from e

def get_media_by_title(self, title: str, include_deleted=False, include_trash=False) -> Optional[Dict]:
    """
    Retrieves the *first* media item matching a given title (case-sensitive).

    Note: Titles are not guaranteed to be unique. This returns the most recently
    modified match if multiple exist. By default, only returns active items.

    Args:
        title (str): The title string of the media item.
        include_deleted (bool): If True, include soft-deleted items. Defaults to False.
        include_trash (bool): If True, include trashed items. Defaults to False.

    Returns:
        Optional[Dict[str, Any]]: A dictionary representing the first matching media
                                  item (ordered by last_modified DESC), or None.

    Raises:
        InputError: If `title` is empty or None.
        DatabaseError: If a database query error occurs.
    """
    if not title:
        raise InputError("title cannot be empty or None.")

    query = "SELECT * FROM Media WHERE title = ?"
    params = [title]

    if not include_deleted:
        query += " AND deleted = 0"
    if not include_trash:
        query += " AND is_trash = 0"

    # Order by last_modified to get potentially the most relevant if duplicates exist
    query += " ORDER BY last_modified DESC LIMIT 1"

    try:
        cursor = self.execute_query(query, tuple(params))
        result = cursor.fetchone()
        return dict(result) if result else None
    except sqlite3.Error as e:
        logger.error(f"Error fetching media by title '{title}': {e}", exc_info=True)
        raise DatabaseError(f"Failed to fetch media by title: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error fetching media by title '{title}': {e}", exc_info=True)
        raise DatabaseError(f"Unexpected error fetching media by title: {e}") from e

def get_paginated_files(self, page: int = 1, results_per_page: int = 50) -> Tuple[List[sqlite3.Row], int, int, int]:
    """
    Fetches a paginated list of active media items (id, title, type) from this database instance.

    Filters for items where `deleted = 0` and `is_trash = 0`.

    Args:
        page (int): The page number (1-based). Defaults to 1.
        results_per_page (int): The number of items per page. Defaults to 50.

    Returns:
        A tuple containing:
            - results (List[sqlite3.Row]): List of Row objects for the current page.
                                           Each row contains 'id', 'title', 'type'.
            - total_pages (int): Total number of pages for active items.
            - current_page (int): The requested page number.
            - total_items (int): The total number of active items matching the criteria.

    Raises:
        ValueError: If page or results_per_page are invalid.
        DatabaseError: If a database query fails.
    """
    # No need to check self type, it's guaranteed by method call
    if page < 1:
        raise ValueError("Page number must be 1 or greater.")
    if results_per_page < 1:
        raise ValueError("Results per page must be 1 or greater.")

    # Use self.db_path_str for logging context
    logging.debug(
        f"Fetching paginated files: page={page}, results_per_page={results_per_page} from DB: {self.db_path_str} (Active Only)")

    offset = (page - 1) * results_per_page
    total_items = 0
    results: List[sqlite3.Row] = []  # Type hint for clarity

    try:
        # Query 1: Get total count of active items
        count_query = "SELECT COUNT(*) AS total_items FROM Media WHERE deleted = 0 AND is_trash = 0"
        # Use self.execute_query
        count_cursor = self.execute_query(count_query)
        count_result = count_cursor.fetchone()
        total_items = count_result['total_items'] if count_result else 0

        # Query 2: Get paginated items if count > 0
        if total_items > 0:
            # Order by most recently modified, then ID for stable pagination
            items_query = """
                          SELECT id, title, type
                          FROM Media
                          WHERE deleted = 0
                            AND is_trash = 0
                          ORDER BY last_modified DESC, id DESC LIMIT ?
                          OFFSET ?
                          """
            # Use self.execute_query
            items_cursor = self.execute_query(items_query, (results_per_page, offset))
            # Fetchall returns a list of Row objects (if row_factory is sqlite3.Row)
            results = items_cursor.fetchall()

        # Calculate total pages
        total_pages = ceil(total_items / results_per_page) if results_per_page > 0 and total_items > 0 else 0

        return results, total_pages, page, total_items

    # Catch DatabaseError potentially raised by self.execute_query
    except DatabaseError as e:
        logging.error(f"Database error in get_paginated_files for DB {self.db_path_str}: {e}", exc_info=True)
        # Re-raise the specific error for the caller to handle
        raise
    # Catch potential underlying SQLite errors if not wrapped by execute_query
    except sqlite3.Error as e:
        logging.error(f"SQLite error during pagination query in {self.db_path_str}: {e}", exc_info=True)
        raise DatabaseError(f"Failed pagination query: {e}") from e
    # Catch unexpected errors
    except Exception as e:
        logging.error(f"Unexpected error in get_paginated_files for DB {self.db_path_str}: {e}", exc_info=True)
        # Wrap unexpected errors in DatabaseError
        raise DatabaseError(f"Unexpected error during pagination: {e}") from e

def backup_database(self, backup_file_path: str) -> bool | None:
    """
    Creates a backup of the current database to the specified file path.

    Args:
        backup_file_path (str): The path to save the backup database file.

    Returns:
        bool: True if the backup was successful, False otherwise.
    """
    logger.info(f"Starting database backup from '{self.db_path_str}' to '{backup_file_path}'")

    if self.backend_type != BackendType.SQLITE:
        return self._backup_non_sqlite_database(backup_file_path)

    src_conn = None
    backup_conn = None
    try:
        if not self.is_memory_db and Path(self.db_path_str).resolve() == Path(backup_file_path).resolve():
            logger.error("Backup path cannot be the same as the source database path.")
            raise ValueError("Backup path cannot be the same as the source database path.")

        src_conn = self.get_connection()

        backup_db_path = Path(backup_file_path)
        backup_db_path.parent.mkdir(parents=True, exist_ok=True)

        backup_conn = sqlite3.connect(backup_file_path)

        logger.debug(f"Source DB connection: {src_conn}")
        logger.debug(f"Backup DB connection: {backup_conn} to file {backup_file_path}")

        src_conn.backup(backup_conn, pages=0, progress=None)

        logger.info(f"Database backup successful from '{self.db_path_str}' to '{backup_file_path}'")
        return True
    except sqlite3.Error as e:
        logger.error(f"SQLite error during database backup: {e}", exc_info=True)
        return False
    except ValueError as ve:
        logger.error(f"ValueError during database backup: {ve}", exc_info=True)
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
        # Do not close src_conn here if it's managed by _get_thread_connection / close_connection
        # self.close_connection() might close the main connection pool which might not be desired.
        # The source connection is managed by the class's connection pooling.
        # If this backup is a one-off, the connection will be closed when the thread context ends
        # or if explicitly closed by the caller of this instance.
        # For safety, if this method obtained a new connection not from the pool, it should close it.
        # However, self.get_connection() reuses pooled connections.

def _backup_non_sqlite_database(self, backup_file_path: str) -> bool:
    """Best-effort handler for backends without native SQLite backup support."""
    if self.backend_type == BackendType.POSTGRESQL:
        logging.warning(
            "Automatic backups are not implemented inside MediaDatabase for PostgreSQL. "
            "Use DB_Backups.create_postgres_backup(backend, backup_dir) to invoke pg_dump. Target requested: %s",
            backup_file_path,
        )
        return False

    logging.warning(
        "Automatic backups are only supported for SQLite. Backend %s is not handled (target: %s).",
        self.backend_type,
        backup_file_path,
    )
    return False


setattr(MediaDatabase, "backup_database", backup_database)
setattr(MediaDatabase, "_backup_non_sqlite_database", _backup_non_sqlite_database)


def get_distinct_media_types(self, include_deleted=False, include_trash=False) -> List[str]:
    """
    Retrieves a list of all distinct, non-null media types present in the Media table.

    Args:
        include_deleted (bool): If True, consider types from soft-deleted media items.
        include_trash (bool): If True, consider types from trashed media items.

    Returns:
        List[str]: A sorted list of unique media type strings.
                   Returns an empty list if no types are found or in case of error.

    Raises:
        DatabaseError: If a database query error occurs.
    """
    logger.debug(
        f"Fetching distinct media types from DB: {self.db_path_str} (deleted={include_deleted}, trash={include_trash})")
    conditions = ["type IS NOT NULL AND type != ''"]
    if not include_deleted:
        conditions.append("deleted = 0")
    if not include_trash:
        conditions.append("is_trash = 0")

    where_clause = " AND ".join(conditions)

    query = f"SELECT DISTINCT type FROM Media WHERE {where_clause} ORDER BY type ASC"
    try:
        cursor = self.execute_query(query)
        results = [row['type'] for row in cursor.fetchall() if row['type']]
        logger.info(f"Found {len(results)} distinct media types: {results}")
        return results
    except sqlite3.Error as e:
        logger.error(f"Error fetching distinct media types from DB {self.db_path_str}: {e}", exc_info=True)
        raise DatabaseError(f"Failed to fetch distinct media types: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error fetching distinct media types from DB {self.db_path_str}: {e}",
                     exc_info=True)
        raise DatabaseError(f"An unexpected error occurred while fetching distinct media types: {e}") from e

def add_media_chunk(self, media_id: int, chunk_text: str, start_index: int, end_index: int, chunk_id: str) -> Optional[Dict]:
    """
    Adds a single chunk record to the MediaChunks table for an active media item.

    Handles transaction, generates UUID, sets sync metadata, and logs a 'create' sync event.
    This is an instance method operating on the specific user's database.

    Args:
        media_id (int): The ID of the parent Media item.
        chunk_text (str): The text content of the chunk.
        start_index (int): Starting character index within the original content.
        end_index (int): Ending character index within the original content.
        chunk_id (str): The application-specific unique ID for this chunk within the media item.

    Returns:
        Optional[Dict]: A dictionary containing the new chunk's database 'id' and 'uuid'
                        on success, otherwise None or raises an exception.

    Raises:
        InputError: If media_id doesn't exist/is inactive, or chunk_text is empty.
        DatabaseError: For database errors during insertion or sync logging, including IntegrityErrors.
    """
    if not chunk_text:
        raise InputError("Chunk text cannot be empty.")

    logger.debug(f"Adding chunk for media_id {media_id}, chunk_id {chunk_id} using client {self.client_id}")

    # Prepare sync/metadata fields using instance attributes/methods
    client_id = self.client_id
    current_time = self._get_current_utc_timestamp_str()  # Use internal helper
    new_uuid = self._generate_uuid()  # Use internal helper
    new_sync_version = 1  # Initial version for a new chunk record

    try:
        # Use instance transaction method
        with self.transaction() as conn:
            media_info = self._fetchone_with_connection(
                conn,
                "SELECT uuid FROM Media WHERE id = ? AND deleted = 0",
                (media_id,),
            )
            if not media_info:
                raise InputError(f"Cannot add chunk: Parent Media ID {media_id} not found or deleted.")
            media_uuid = media_info['uuid']  # Get parent UUID for context if needed

            # Prepare data for insert statement
            insert_data = {
                'media_id': media_id,
                'chunk_text': chunk_text,
                'start_index': start_index,
                'end_index': end_index,
                'chunk_id': chunk_id,  # Keep the original chunk_id column
                'uuid': new_uuid,  # Add the new UUID column
                'last_modified': current_time,
                'version': new_sync_version,
                'client_id': client_id,
                'deleted': 0,
                'media_uuid': media_uuid  # For sync payload context
            }

            # Execute INSERT
            sql = """
                  INSERT INTO MediaChunks
                  (media_id, chunk_text, start_index, end_index, chunk_id, uuid, last_modified, version, client_id, \
                   deleted)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) \
                  """
            if self.backend_type == BackendType.POSTGRESQL:
                sql += " RETURNING id"
            params = (
                insert_data['media_id'], insert_data['chunk_text'], insert_data['start_index'],
                insert_data['end_index'], insert_data['chunk_id'], insert_data['uuid'],
                insert_data['last_modified'], insert_data['version'], insert_data['client_id'],
                insert_data['deleted']
            )
            cursor_insert = self._execute_with_connection(conn, sql, params)
            if self.backend_type == BackendType.POSTGRESQL:
                inserted_row = cursor_insert.fetchone()
                chunk_pk_id = inserted_row['id'] if inserted_row else None
            else:
                chunk_pk_id = cursor_insert.lastrowid

            if not chunk_pk_id:
                raise DatabaseError("Failed to get last row ID for new media chunk.")

            # Log sync event using instance method (passing connection)
            self._log_sync_event(conn, 'MediaChunks', new_uuid, 'create', new_sync_version, insert_data)

            logger.info(f"Successfully added chunk ID {chunk_pk_id} (UUID: {new_uuid}) for media {media_id}.")
            return {'id': chunk_pk_id, 'uuid': new_uuid}

    except sqlite3.IntegrityError as ie:
        logger.error(f"Integrity error adding chunk for media {media_id}: {ie}", exc_info=True)
        raise DatabaseError(f"Failed to add chunk due to constraint violation: {ie}") from ie
    except (InputError, DatabaseError) as e:
        logger.error(f"Error adding chunk for media {media_id}: {e}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error adding chunk for media {media_id}: {e}", exc_info=True)
        raise DatabaseError(f"An unexpected error occurred while adding media chunk: {e}") from e

def add_media_chunks_in_batches(self, media_id: int, chunks_to_add: List[Dict[str, Any]],
                                batch_size: int = 100) -> int:
    """
    Processes a list of chunk dictionaries and adds them to the MediaChunks table in batches.
    This method adapts the input chunk format for the internal self.batch_insert_chunks method.
    It preserves the batching and logging behavior of the original standalone process_chunks function.

    Args:
        media_id (int): ID of the media these chunks belong to.
        chunks_to_add (List[Dict[str, Any]]): List of chunk dictionaries. Each dictionary must have
                                              'text', 'start_index', and 'end_index' keys.
                                              Example: [{'text': 'chunk1', 'start_index': 0, 'end_index': 10}, ...]
        batch_size (int): Number of chunks to process and pass to self.batch_insert_chunks in each iteration.

    Returns:
        int: The total number of chunks successfully processed and attempted for insertion.

    Raises:
        InputError: If essential keys are missing in `chunks_to_add` items, or if `media_id` is invalid
                    (this error would be propagated from the underlying `self.batch_insert_chunks` call).
        DatabaseError: For database errors during insertion (propagated from `self.batch_insert_chunks`).
        Exception: For other unexpected errors during the process.
    """
    # These log_counter and log_histogram calls assume they are available in the global scope
    # or otherwise accessible, as per the original function's structure.
    # If not, they would need to be passed to this method or the Database instance.
    log_counter("add_media_chunks_in_batches_attempt", labels={"media_id": media_id})
    start_time = time.time()
    total_chunks_in_input = len(chunks_to_add)
    successfully_processed_count = 0

    # Parent media_id validity will be checked within self.batch_insert_chunks.
    # If media_id is invalid, self.batch_insert_chunks will raise an InputError.

    try:
        for i in range(0, total_chunks_in_input, batch_size):
            current_batch_from_input = chunks_to_add[i:i + batch_size]

            # Adapt batch to the format expected by self.batch_insert_chunks:
            # [{'text': ..., 'metadata': {'start_index': ..., 'end_index': ...}}]
            adapted_batch_for_internal_method = []
            for chunk_item in current_batch_from_input:
                try:
                    # Ensure 'text', 'start_index', 'end_index' are present
                    # The self.batch_insert_chunks method expects 'text' (or 'chunk_text')
                    # and 'metadata' containing 'start_index' and 'end_index'.
                    text_content = chunk_item['text']
                    start_idx = chunk_item['start_index']
                    end_idx = chunk_item['end_index']

                    adapted_chunk = {
                        'text': text_content,
                        'metadata': {
                            'start_index': start_idx,
                            'end_index': end_idx
                        }
                    }
                    adapted_batch_for_internal_method.append(adapted_chunk)
                except KeyError as e:
                    # Using global 'logging' as per the style in Database class and original function
                    logging.error(
                        f"Media ID {media_id}: Skipping chunk due to missing key {e} in input data: {chunk_item}")
                    log_counter("add_media_chunks_in_batches_item_skip_key_error",
                                labels={"media_id": media_id, "key": str(e)})
                    continue  # Skip this malformed chunk_item

            if not adapted_batch_for_internal_method:
                if current_batch_from_input:  # Original batch had items, but all were malformed or skipped
                    logging.warning(
                        f"Media ID {media_id}: Batch starting at index {i} resulted in no valid chunks to process.")
                continue  # Move to the next batch

            try:
                # self.batch_insert_chunks is an existing method in your Database class.
                # It handles its own transaction, generates UUIDs, sets sync metadata (version, client_id, etc.),
                # and logs sync events for each chunk.
                # It returns the number of chunks it prepared/attempted from the adapted_batch.
                num_inserted_this_batch = self.batch_insert_chunks(media_id, adapted_batch_for_internal_method)

                successfully_processed_count += num_inserted_this_batch
                logging.info(
                    f"Media ID {media_id}: Processed {successfully_processed_count}/{total_chunks_in_input} chunks so far. Current batch (size {len(adapted_batch_for_internal_method)}) resulted in {num_inserted_this_batch} items attempted.")
                log_counter("add_media_chunks_in_batches_batch_success", labels={"media_id": media_id})

            # Catch specific errors that self.batch_insert_chunks might raise
            except InputError as e:  # e.g., if media_id is invalid, or chunk structure within adapted_batch is wrong
                logging.error(f"Media ID {media_id}: Input error during an internal batch insertion: {e}")
                log_counter("add_media_chunks_in_batches_batch_error",
                            labels={"media_id": media_id, "error_type": "InputError"})
                raise  # Re-raise to halt the entire operation
            except DatabaseError as e:  # For other database-related errors from self.batch_insert_chunks
                logging.error(f"Media ID {media_id}: Database error during an internal batch insertion: {e}")
                log_counter("add_media_chunks_in_batches_batch_error",
                            labels={"media_id": media_id, "error_type": "DatabaseError"})
                raise  # Re-raise
            except Exception as e:  # Catch any other unexpected errors from self.batch_insert_chunks
                logging.error(f"Media ID {media_id}: Unexpected error during an internal batch insertion: {e}",
                              exc_info=True)
                log_counter("add_media_chunks_in_batches_batch_error",
                            labels={"media_id": media_id, "error_type": type(e).__name__})
                raise  # Re-raise

        logging.info(
            f"Media ID {media_id}: Finished processing chunk list. Total chunks from input: {total_chunks_in_input}. Successfully processed and attempted for insertion: {successfully_processed_count}.")
        duration = time.time() - start_time
        log_histogram("add_media_chunks_in_batches_duration", duration, labels={"media_id": media_id})
        log_counter("add_media_chunks_in_batches_success_overall", labels={"media_id": media_id})
        return successfully_processed_count

    except Exception as e:  # Catches errors from the outer loop logic or re-raised errors from the inner try-except block
        duration = time.time() - start_time
        # Log duration even if the overall process failed
        log_histogram("add_media_chunks_in_batches_duration", duration, labels={"media_id": media_id})
        log_counter("add_media_chunks_in_batches_error_overall",
                    labels={"media_id": media_id, "error_type": type(e).__name__})
        logging.error(f"Media ID {media_id}: Error processing the list of chunks: {e}", exc_info=True)
        raise  # Re-raise the caught exception to inform the caller

def batch_insert_chunks(self, media_id: int, chunks: List[Dict]) -> int:
    """
    Inserts a batch of chunk records into the MediaChunks table for an active media item.

    Uses executemany for efficiency within a single transaction.
    Generates UUIDs, sets sync metadata, and logs a 'create' sync event for EACH chunk.
    This is an instance method operating on the specific user's database.

    Args:
        media_id (int): The ID of the parent Media item.
        chunks (List[Dict]): A list of dictionaries, where each dictionary represents a chunk.
                             Expected keys in each dict: 'text' (or 'chunk_text'), and
                             'metadata' dict containing 'start_index', 'end_index'.

    Returns:
        int: The number of chunks successfully prepared for insertion.

    Raises:
        InputError: If media_id doesn't exist/is inactive, or the chunks list is empty or invalid.
        DatabaseError: For database errors during insertion or sync logging, including IntegrityErrors.
        KeyError: If expected keys ('text', 'metadata', 'start_index', 'end_index') are missing in chunk dicts.
    """
    if not chunks:
        logger.warning(f"batch_insert_chunks called with empty list for media {media_id}.")
        return 0

    logger.info(f"Batch inserting {len(chunks)} chunks for media_id {media_id} using client {self.client_id}.")

    client_id = self.client_id
    current_time = self._get_current_utc_timestamp_str()

    try:
        with self.transaction() as conn:
            parent_exists = self._fetchone_with_connection(
                conn,
                "SELECT 1 FROM Media WHERE id = ? AND deleted = 0",
                (media_id,),
            )
            if not parent_exists:
                raise InputError(f"Cannot batch insert chunks: Parent Media ID {media_id} not found or deleted.")

            base_index_row = self._fetchone_with_connection(
                conn,
                "SELECT COUNT(*) AS chunk_count FROM MediaChunks WHERE media_id = ?",
                (media_id,),
            )
            base_index = int((base_index_row or {}).get('chunk_count', 0))

            params_list: List[tuple] = []
            sync_log_data: List[tuple] = []
            running_index = 0

            for chunk_dict in chunks:
                chunk_text = chunk_dict.get('text', chunk_dict.get('chunk_text'))
                metadata = chunk_dict.get('metadata') or {}
                start_index = metadata.get('start_index')
                end_index = metadata.get('end_index')
                if chunk_text is None or start_index is None or end_index is None:
                    logger.warning("Skipping chunk for media %s due to missing text/start/end metadata.", media_id)
                    continue

                provided_chunk_id = chunk_dict.get('chunk_id') or metadata.get('chunk_id')
                if provided_chunk_id:
                    chunk_id = str(provided_chunk_id)
                else:
                    running_index += 1
                    chunk_id = f"{media_id}_chunk_{base_index + running_index}"

                new_uuid = self._generate_uuid()
                new_sync_version = 1

                params_list.append(
                    (
                        media_id,
                        chunk_text,
                        start_index,
                        end_index,
                        chunk_id,
                        new_uuid,
                        current_time,
                        new_sync_version,
                        client_id,
                        0,
                    )
                )

                sync_log_data.append(
                    (
                        new_uuid,
                        new_sync_version,
                        {
                            'media_id': media_id,
                            'chunk_text': chunk_text,
                            'start_index': start_index,
                            'end_index': end_index,
                            'chunk_id': chunk_id,
                            'uuid': new_uuid,
                            'last_modified': current_time,
                            'version': new_sync_version,
                            'client_id': client_id,
                            'deleted': 0,
                        },
                    )
                )

            if not params_list:
                logger.warning("No valid chunks prepared for batch insert media %s.", media_id)
                return 0

            self._executemany_with_connection(
                conn,
                """
                INSERT INTO MediaChunks
                (media_id, chunk_text, start_index, end_index, chunk_id, uuid, last_modified, version, client_id, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params_list,
            )

            for chunk_uuid_log, version_log, payload_log in sync_log_data:
                self._log_sync_event(conn, 'MediaChunks', chunk_uuid_log, 'create', version_log, payload_log)

            inserted_count = len(params_list)
        logger.info(f"Successfully batch inserted {inserted_count} chunks for media {media_id}.")
        return inserted_count

    except sqlite3.IntegrityError as ie:
        logger.error(f"Integrity error batch inserting chunks for media {media_id}: {ie}", exc_info=True)
        raise DatabaseError(f"Failed to batch insert chunks due to constraint violation: {ie}") from ie
    except (InputError, DatabaseError, KeyError) as e:
        logger.error(f"Error batch inserting chunks for media {media_id}: {e}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error batch inserting chunks for media {media_id}: {e}", exc_info=True)
        raise DatabaseError(f"An unexpected error occurred during batch chunk insertion: {e}") from e

def process_chunks(self, media_id: int, chunks: List[Dict[str, Any]], batch_size: int = 100):
    """
    Process chunks in batches and insert them into the MediaChunks table.

    This method is part of the Database class and works with the V2 schema
    for MediaChunks. It generates necessary IDs (a UUID for 'chunk_id' and
    another for 'uuid') and sync metadata for each chunk.

    Args:
        media_id (int): ID of the media these chunks belong to.
        chunks (List[Dict[str, Any]]): List of chunk dictionaries. Each dictionary is
                                       expected to have 'text', 'start_index',
                                       and 'end_index' keys.
        batch_size (int): Number of chunks to process in each database transaction.

    Raises:
        InputError: If the parent media_id is not found or is deleted, or if
                    a chunk dictionary is missing required keys.
        DatabaseError: If there's an error during database operations (e.g.,
                       integrity constraints) or sync logging.
        Exception: For other unexpected errors during processing.
    """
    log_counter("process_chunks_attempt", labels={"media_id": media_id})
    start_time = time.time()
    total_chunks_to_process = len(chunks)
    successfully_inserted_chunks = 0

    # Initial check for parent media_id existence and active status.
    # This uses a direct query. An alternative is self.get_media_by_id(media_id).
    conn_for_check = self.get_connection()
    parent_exists = self._fetchone_with_connection(
        conn_for_check,
        "SELECT 1 FROM Media WHERE id = ? AND deleted = 0",
        (media_id,),
    )
    if not parent_exists:
        logging.error(f"Parent Media ID {media_id} not found or is deleted. Cannot process chunks.")
        log_counter("process_chunks_error", labels={"media_id": media_id, "error_type": "ParentMediaNotFound"})
        duration = time.time() - start_time  # Log duration even for this early exit
        log_histogram("process_chunks_duration", duration, labels={"media_id": media_id})
        raise InputError(f"Parent Media ID {media_id} not found or is deleted.")

    try:
        for i in range(0, total_chunks_to_process, batch_size):
            batch_of_input_chunks = chunks[i:i + batch_size]

            db_insert_params_list = []
            # Store tuples of (entity_uuid, version, payload) for logging after successful insert
            sync_log_data_for_batch = []

            current_timestamp = self._get_current_utc_timestamp_str()
            # Assumes self.client_id is available from the Database instance
            client_id = self.client_id

            for input_chunk_dict in batch_of_input_chunks:
                try:
                    chunk_text = input_chunk_dict['text']
                    start_index = input_chunk_dict['start_index']
                    end_index = input_chunk_dict['end_index']
                except KeyError as e:
                    logging.warning(
                        f"Skipping chunk for media_id {media_id} due to missing key '{e}': {str(input_chunk_dict)[:100]}")
                    log_counter("process_chunks_item_skipped",
                                labels={"media_id": media_id, "reason": "missing_key", "key": str(e)})
                    continue  # Skip this malformed chunk

                # Generate fields required by the MediaChunks schema.
                # MediaChunks.chunk_id has a TEXT UNIQUE constraint. We generate a UUID for it.
                generated_chunk_id_for_db = self._generate_uuid()
                # MediaChunks.uuid also has a TEXT UNIQUE NOT NULL constraint.
                generated_uuid_for_db = self._generate_uuid()

                chunk_version = 1  # Initial sync version for new records
                deleted_status = 0  # New chunks are not deleted

                # Parameters order must match the INSERT statement columns
                params_tuple = (
                    media_id,
                    chunk_text,
                    start_index,
                    end_index,
                    generated_chunk_id_for_db,  # value for 'chunk_id' column
                    generated_uuid_for_db,  # value for 'uuid' column
                    current_timestamp,  # last_modified
                    chunk_version,  # version
                    client_id,  # client_id
                    deleted_status  # deleted
                )
                db_insert_params_list.append(params_tuple)

                # Prepare data for sync logging (payload should reflect the inserted row)
                sync_payload = {
                    'media_id': media_id,
                    'chunk_text': chunk_text,
                    'start_index': start_index,
                    'end_index': end_index,
                    'chunk_id': generated_chunk_id_for_db,
                    'uuid': generated_uuid_for_db,
                    'last_modified': current_timestamp,
                    'version': chunk_version,
                    'client_id': client_id,
                    'deleted': deleted_status
                    # prev_version and merge_parent_uuid are typically NULL/None on creation
                }
                # Store data needed for _log_sync_event: (entity_uuid, version, payload_dict)
                sync_log_data_for_batch.append((generated_uuid_for_db, chunk_version, sync_payload))

            if not db_insert_params_list:  # If all chunks in the current batch were skipped
                logging.info(
                    f"Batch starting at index {i} for media_id {media_id} resulted in no valid chunks to insert.")
                continue

            try:
                # Each batch is processed in its own transaction for atomicity of that batch
                with self.transaction() as conn:  # `conn` is yielded by the transaction context manager
                    insert_sql = """
                                 INSERT INTO MediaChunks
                                 (media_id, chunk_text, start_index, end_index, chunk_id, uuid,
                                  last_modified, version, client_id, deleted)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) \
                                 """
                    # self.execute_many is called within the transaction.
                    # The default commit=False for execute_many is correct here.
                    self.execute_many(insert_sql, db_insert_params_list, connection=conn)

                    # If execute_many succeeded, log sync events for this batch
                    for entity_uuid, version_val, payload_dict in sync_log_data_for_batch:
                        self._log_sync_event(
                            conn=conn,  # Pass the connection from the transaction
                            entity="MediaChunks",
                            entity_uuid=entity_uuid,  # The UUID of the MediaChunk record
                            operation="create",
                            version=version_val,  # The sync version of the MediaChunk
                            payload=payload_dict
                        )

                successfully_inserted_chunks += len(db_insert_params_list)
                logging.info(
                    f"Successfully processed batch for media_id {media_id}. Total inserted so far: {successfully_inserted_chunks}/{total_chunks_to_process}")
                log_counter("process_chunks_batch_success", labels={"media_id": media_id})

            except sqlite3.IntegrityError as e:
                # This could be a FOREIGN KEY constraint failure if media_id became invalid
                # or a UNIQUE constraint failure.
                logging.error(f"Database integrity error inserting chunk batch for media_id {media_id}: {e}")
                log_counter("process_chunks_batch_error",
                            labels={"media_id": media_id, "error_type": "IntegrityError"})
                # Re-raise to stop processing further batches, as this indicates a critical issue.
                raise DatabaseError(
                    f"Integrity error during chunk batch insertion for media_id {media_id}: {e}") from e
            except Exception as e:  # Catch other errors from DB operation or sync logging
                logging.error(f"Error processing chunk batch for media_id {media_id}: {e}", exc_info=True)
                log_counter("process_chunks_batch_error",
                            labels={"media_id": media_id, "error_type": type(e).__name__})
                raise  # Re-raise to be caught by the outer try-except, stopping further processing.

        logging.info(
            f"Finished processing all chunks for media_id {media_id}. Total successfully inserted: {successfully_inserted_chunks}")
        duration = time.time() - start_time
        log_histogram("process_chunks_duration", duration, labels={"media_id": media_id})
        log_counter("process_chunks_success", labels={"media_id": media_id})
        # No explicit return value, matching the original function's behavior.

    except Exception as e:  # Catches errors from loop setup or re-raised errors from batch processing
        duration = time.time() - start_time
        # Log duration even if the overall process failed or exited early
        log_histogram("process_chunks_duration", duration, labels={"media_id": media_id})
        log_counter("process_chunks_error", labels={"media_id": media_id, "error_type": type(e).__name__})
        logging.error(f"Overall error processing chunks for media_id {media_id}: {e}", exc_info=True)

        # Re-raise the exception so the caller is aware of the failure.
        # Wrap in DatabaseError if it's not already one of our specific DB errors.
        if not isinstance(e, (DatabaseError, InputError)):  # Check if e is already a known custom error
            raise DatabaseError(
                f"An unexpected error occurred while processing chunks for media_id {media_id}: {e}") from e
        else:
            raise


setattr(MediaDatabase, "add_media_chunks_in_batches", add_media_chunks_in_batches)
setattr(MediaDatabase, "batch_insert_chunks", batch_insert_chunks)
setattr(MediaDatabase, "process_chunks", process_chunks)

# =========================================================================
# Standalone Functions (REQUIRE db_instance passed explicitly)
# =========================================================================
# These generally call instance methods now, which handle logging/FTS internally.


def get_document_version(db_instance: MediaDatabase, media_id: int, version_number: Optional[int] = None, include_content: bool = True) -> Optional[Dict[str, Any]]:
    """
    Gets a specific document version or the latest active one for an active media item.

    Filters results to only include versions where both the DocumentVersion itself
    and the parent Media item are not soft-deleted (`deleted = 0`).

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        media_id (int): The ID of the parent Media item.
        version_number (Optional[int]): The specific `version_number` to retrieve.
            If None, retrieves the latest (highest `version_number`) active version.
            Must be a positive integer if provided. Defaults to None.
        include_content (bool): Whether to include the 'content' field in the
                                result. Defaults to True.

    Returns:
        Optional[Dict[str, Any]]: A dictionary representing the document version
                                  if found and active, otherwise None.

    Raises:
        TypeError: If `db_instance` is not a Database object or `media_id` is not int.
        ValueError: If `version_number` is provided but is not a positive integer.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance must be a Database object.")
    if not isinstance(media_id, int):
        raise TypeError("media_id must be an integer.")
    if version_number is not None and (not isinstance(version_number, int) or version_number < 1):
        raise ValueError("Version number must be a positive integer.")
    log_msg = f"Getting {'latest' if version_number is None else f'version {version_number}'} for media_id={media_id}"
    logger.debug(f"{log_msg} (active only) from DB: {db_instance.db_path_str}")
    try:
        select_cols_list = ["dv.id", "dv.uuid", "dv.media_id", "dv.version_number", "dv.created_at",
                           "dv.prompt", "dv.analysis_content", "dv.safe_metadata", "dv.last_modified", "dv.version",
                           "dv.client_id", "dv.deleted"]
        if include_content:
            select_cols_list.append("dv.content")
        select_cols = ", ".join(select_cols_list)
        params = [media_id]
        query_base = "FROM DocumentVersions dv JOIN Media m ON dv.media_id = m.id WHERE dv.media_id = ? AND dv.deleted = 0 AND m.deleted = 0"
        order_limit = ""
        if version_number is None:
            order_limit = "ORDER BY dv.version_number DESC LIMIT 1"
        else:
            query_base += " AND dv.version_number = ?"
            params.append(version_number)
        final_query = f"SELECT {select_cols} {query_base} {order_limit}"
        cursor = db_instance.execute_query(final_query, tuple(params))
        result = cursor.fetchone()
        if not result:
            logger.warning(f"Active doc version {version_number or 'latest'} not found for active media {media_id}")
            return None
        return dict(result)
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error retrieving {log_msg} DB '{db_instance.db_path_str}': {e}", exc_info=True)
        raise DatabaseError(f"DB error retrieving version: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error retrieving {log_msg} DB '{db_instance.db_path_str}': {e}", exc_info=True)
        raise DatabaseError(f"Unexpected error retrieving version: {e}") from e


# Backup functions remain placeholders or need proper implementation
def create_incremental_backup(db_path, backup_dir):
    """Create an incremental backup using the DB_Backups helper.

    Returns a status message string.
    """
    try:
        from tldw_Server_API.app.core.DB_Management.DB_Backups import (
            create_incremental_backup as _inc,
        )
        return _inc(db_path, backup_dir, "media")
    except Exception as e:
        logger.error(f"create_incremental_backup failed: {e}")
        return f"Failed to create incremental backup: {e}"


def create_automated_backup(db_path, backup_dir):
    """Create a full backup using the DB_Backups helper.

    Returns a status message string.
    """
    try:
        from tldw_Server_API.app.core.DB_Management.DB_Backups import create_backup as _full
        return _full(db_path, backup_dir, "media")
    except Exception as e:
        logger.error(f"create_automated_backup failed: {e}")
        return f"Failed to create backup: {e}"


def rotate_backups(backup_dir, max_backups=10):
    """Rotate backup files in a directory, keeping the newest max_backups entries.

    Considers files ending with .db or .sqlib. Returns a status message string.
    """
    try:
        p = Path(backup_dir)
        if not p.exists():
            return "No rotation needed."
        files = [f for f in p.iterdir() if f.is_file() and f.suffix in {".db", ".sqlib"}]
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        if len(files) <= max_backups:
            return "No rotation needed."
        to_remove = files[max_backups:]
        removed = 0
        for f in to_remove:
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
        return f"Removed {removed} old backups."
    except Exception as e:
        logger.error(f"rotate_backups failed: {e}")
        return f"Failed to rotate backups: {e}"


def check_database_integrity(db_path): # Standalone check is fine
    """
    Performs an integrity check on the specified SQLite database file.

    Connects in read-only mode and executes `PRAGMA integrity_check`.

    Args:
        db_path (str): The path to the SQLite database file.

    Returns:
        bool: True if the integrity check returns 'ok', False otherwise, or if
              an error occurs during the check.
    """
    logger.info(f"Checking integrity of database: {db_path}")
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) # Read-only mode
        cursor = conn.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result and result[0].lower() == 'ok':
            logger.info(f"Integrity check PASSED for {db_path}")
            return True
        else: logger.error(f"Integrity check FAILED for {db_path}: {result}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Error during integrity check for {db_path}: {e}", exc_info=True)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"Failed to close sqlite connection after integrity check: error={e}")


# Utility Checks
def is_valid_date(date_string: str) -> bool:
    """
    Checks if a string is a valid date in 'YYYY-MM-DD' format.

    Args:
        date_string (Optional[str]): The string to validate.

    Returns:
        bool: True if the string is a valid 'YYYY-MM-DD' date, False otherwise.
    """
    if not date_string:
        return False
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except (ValueError, TypeError):
        return False


def check_media_exists(db_instance: MediaDatabase, media_id: Optional[int] = None, url: Optional[str] = None, content_hash: Optional[str] = None) -> Optional[int]:
    """
    Checks if an *active* (non-deleted) media item exists using ID, URL, or hash.

    Requires at least one identifier (media_id, url, or content_hash).
    Returns the ID of the first matching active media item found.

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        media_id (Optional[int]): The media ID to check.
        url (Optional[str]): The media URL to check.
        content_hash (Optional[str]): The media content hash to check.

    Returns:
        Optional[int]: The integer ID of the existing active media item if found,
                       otherwise None.

    Raises:
        TypeError: If `db_instance` is not a Database object.
        ValueError: If none of `media_id`, `url`, or `content_hash` are provided.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    query_parts = []
    params = []
    if media_id is not None:
        query_parts.append("id = ?")
        params.append(media_id)
    if url:
        query_parts.append("url = ?")
        params.append(url)
    if content_hash:
        query_parts.append("content_hash = ?")
        params.append(content_hash)
    if not query_parts:
        raise ValueError("Must provide id, url, or content_hash to check.")
    query = f"SELECT id FROM Media WHERE ({' OR '.join(query_parts)}) AND deleted = 0 LIMIT 1"
    try:
        cursor = db_instance.execute_query(query, tuple(params))
        result = cursor.fetchone()
        return result['id'] if result else None
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error checking media existence DB '{db_instance.db_path_str}': {e}")
        raise DatabaseError(f"Failed check media existence: {e}") from e


def empty_trash(db_instance: MediaDatabase, days_threshold: int) -> Tuple[int, int]:
    """
    Permanently removes items from the trash that are older than a threshold.

    Finds Media items where `is_trash = 1`, `deleted = 0`, and `trash_date`
    is older than `days_threshold` days ago. For each such item found, it calls
    `db_instance.soft_delete_media(media_id, cascade=True)` to perform the
    soft delete, log sync events, update FTS, and handle cascades.

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        days_threshold (int): The minimum number of days an item must have been
                              in the trash (based on `trash_date`) to be emptied.
                              Must be a non-negative integer.

    Returns:
        Tuple[int, int]: A tuple containing:
            - processed_count (int): Number of items successfully moved from trash
                                     to the soft-deleted state.
            - remaining_count (int): Number of items still in the UI trash
                                     (`is_trash = 1`, `deleted = 0`) after the operation.
                                     Returns -1 for remaining_count if an error occurred
                                     during the final count query.

    Raises:
        TypeError: If `db_instance` is not a Database object.
        ValueError: If `days_threshold` is not a non-negative integer.
        DatabaseError: Can be raised by the underlying `soft_delete_media` calls if
                       they encounter issues beyond ConflictError. Errors during the
                       initial query or final count also raise DatabaseError.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    if not isinstance(days_threshold, int) or days_threshold < 0:
        raise ValueError("Days must be non-negative int.")
    threshold_date_str = (datetime.now(timezone.utc) - timedelta(days=days_threshold)).strftime('%Y-%m-%dT%H:%M:%SZ')  # ISO Format
    processed_count = 0
    logger.info(f"Emptying trash older than {days_threshold} days ({threshold_date_str}) on DB {db_instance.db_path_str}")
    try:
        cursor_find = db_instance.execute_query("SELECT id, title FROM Media WHERE is_trash = 1 AND deleted = 0 AND trash_date <= ?", (threshold_date_str,))
        items_to_process = cursor_find.fetchall()
        if not items_to_process:
            logger.info("No items found in trash older than threshold.")
        else:
            logger.info(f"Found {len(items_to_process)} items to process.")
            for item in items_to_process:
                media_id, title = item['id'], item['title']
                logger.debug(f"Processing item ID {media_id} ('{title}') for sync delete from trash.")
                try:
                    success = db_instance.soft_delete_media(media_id=media_id, cascade=True)  # Instance method handles logging/FTS
                    if success:
                        processed_count += 1
                    else:
                        logger.warning(f"Failed process item ID {media_id} during trash emptying.")
                except ConflictError as e:
                    logger.warning(f"Conflict processing item ID {media_id} during trash emptying: {e}")
                except DatabaseError as e:
                    logger.error(f"DB error processing item ID {media_id} during trash emptying: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error processing item ID {media_id} during trash emptying: {e}", exc_info=True)
        cursor_remain = db_instance.execute_query(
            "SELECT COUNT(*) AS trash_remaining FROM Media WHERE is_trash = 1 AND deleted = 0"
        )
        remain_row = cursor_remain.fetchone()
        remaining_count = remain_row['trash_remaining'] if remain_row else 0
        logger.info(f"Trash emptying complete. Processed (sync deleted): {processed_count}. Remaining in UI trash: {remaining_count}.")
        return processed_count, remaining_count
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error emptying trash DB '{db_instance.db_path_str}': {e}", exc_info=True)
        return 0, -1
    except Exception as e:
        logger.error(f"Unexpected error emptying trash DB '{db_instance.db_path_str}': {e}", exc_info=True)
        return 0, -1

# Deprecated check
def check_media_and_whisper_model(*args, **kwargs):
    logger.warning("check_media_and_whisper_model is deprecated.")
    return True, "Deprecated"

# Media processing state functions (unchanged logic, rely on DB fields)
def get_unprocessed_media(db_instance: MediaDatabase) -> List[Dict]:
    """
    Retrieves media items marked as needing vector processing.

    Fetches active, non-trashed media items where `vector_processing = 0`.
    Returns a list of dictionaries containing basic info (id, uuid, content, type, title).

    Args:
        db_instance (MediaDatabase): An initialized Database instance.

    Returns:
        List[Dict[str, Any]]: A list of media items needing processing. Empty if none.

    Raises:
        TypeError: If `db_instance` is not a Database object.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    try:
        query = "SELECT id, uuid, content, type, title FROM Media WHERE vector_processing = 0 AND deleted = 0 AND is_trash = 0 ORDER BY id"
        cursor = db_instance.execute_query(query)
        return [dict(row) for row in cursor.fetchall()]
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error getting unprocessed media DB '{db_instance.db_path_str}': {e}")
        raise DatabaseError("Failed get unprocessed media") from e


def mark_media_as_processed(db_instance: MediaDatabase, media_id: int):
    """
    Marks a media item's vector processing status as complete (`vector_processing = 1`).

    Important: This function ONLY updates the `vector_processing` flag. It DOES NOT
    update the `last_modified` timestamp, increment the sync `version`, or log a
    sync event. It's intended for internal state tracking after a potentially long
    vector processing task, assuming a separate mechanism handles the main media
    updates and sync logging if content/vectors were added.

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        media_id (int): The ID of the media item to mark as processed.

    Raises:
        TypeError: If `db_instance` is not a Database object.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    logger.debug(f"Marking media {media_id} vector_processing=1 on DB '{db_instance.db_path_str}'.")
    try:
        cursor = db_instance.execute_query("UPDATE Media SET vector_processing = 1 WHERE id = ? AND deleted = 0", (media_id,), commit=True)
        if cursor.rowcount == 0:
            logger.warning(f"Attempted mark media {media_id} processed, but not found/deleted.")
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error marking media {media_id} processed '{db_instance.db_path_str}': {e}")
        raise DatabaseError(f"Failed mark media {media_id} processed") from e

# Ingestion wrappers call instance methods
def ingest_article_to_db_new(db_instance: MediaDatabase, *,
                             url: str, title: str,
                             content: str,
                             author: Optional[str] = None,
                             keywords: Optional[List[str]] = None,
                             summary: Optional[str] = None,
                             ingestion_date: Optional[str] = None,
                             custom_prompt: Optional[str] = None,
                             overwrite: bool = False) -> Tuple[Optional[int],
                            Optional[str], str]:
    """
    Wrapper function to add or update an article using `add_media_with_keywords`.

    Sets `media_type` to 'article'. Uses `summary` as `analysis_content` and
    `custom_prompt` as `prompt` for the initial document version.

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        url (str): The URL of the article. Required.
        title (str): The title of the article. Required.
        content (str): The main content of the article. Required.
        author (Optional[str]): Author of the article.
        keywords (Optional[List[str]]): Keywords associated with the article.
        summary (Optional[str]): A summary or analysis of the article.
        ingestion_date (Optional[str]): ISO 8601 UTC timestamp string. Defaults to now.
        custom_prompt (Optional[str]): A prompt related to the article/summary.
        overwrite (bool): If True, update if article exists. Defaults to False.

    Returns:
        Tuple[Optional[int], Optional[str], str]: Result from `add_media_with_keywords`:
            (media_id, media_uuid, message).

    Raises:
        TypeError: If `db_instance` is not a Database object.
        InputError: If required fields (url, title, content) are missing/invalid.
        ConflictError: If overwrite=True and update fails due to version conflict.
        DatabaseError: For underlying database or sync/FTS errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    if not url or not title or content is None:
        raise InputError("URL, Title, and Content are required.")
    return db_instance.add_media_with_keywords(
        url=url,
        title=title,
        media_type='article',
        content=content,
        keywords=keywords,
        prompt=custom_prompt,
        analysis_content=summary,
        author=author,
        ingestion_date=ingestion_date,
        overwrite=overwrite
    )


def import_obsidian_note_to_db(db_instance: MediaDatabase, note_data: Dict[str, Any]) -> Tuple[Optional[int], Optional[str], str]:
    """
    Wrapper function to add or update an Obsidian note using `add_media_with_keywords`.

    Extracts relevant fields from the `note_data` dictionary. Uses Obsidian tags
    as keywords and YAML frontmatter (if present and valid) as `analysis_content`.
    Constructs a default URL like 'obsidian://note/TITLE'.

    Requires `pyyaml` to be installed to parse frontmatter.

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        note_data (Dict[str, Any]): A dictionary containing note information.
            Expected keys: 'title' (str, required), 'content' (str, required).
            Optional keys: 'tags' (List[str|int]), 'frontmatter' (Dict),
            'file_created_date' (str, ISO 8601 UTC), 'overwrite' (bool).

    Returns:
        Tuple[Optional[int], Optional[str], str]: Result from `add_media_with_keywords`:
            (media_id, media_uuid, message).

    Raises:
        TypeError: If `db_instance` is not a Database object or `note_data` is not a dict.
        InputError: If required keys ('title', 'content') are missing or invalid in `note_data`.
        ConflictError: If overwrite=True and update fails due to version conflict.
        DatabaseError: For underlying database or sync/FTS errors.
        ImportError: If `yaml` library is needed but not installed.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    required = ['title', 'content']
    missing = [k for k in required if k not in note_data or note_data[k] is None]
    if missing:
        raise InputError(f"Obsidian note missing required keys: {missing}")
    url_id = f"obsidian://note/{note_data['title']}"
    kw = note_data.get('tags', [])
    kw = [str(k) for k in kw if isinstance(k, (str, int))]
    fm_str = None
    fm = note_data.get('frontmatter')
    author = None
    if isinstance(fm, dict):
        author = fm.get('author')
        try:
            fm_str = yaml.dump(fm, default_flow_style=False)
        except Exception as e:
            logger.error(f"Error dumping frontmatter: {e}")
    return db_instance.add_media_with_keywords(url=url_id, title=note_data['title'], media_type='obsidian_note', content=note_data['content'], keywords=kw, author=author, prompt="Obsidian Frontmatter" if fm_str else None, analysis_content=fm_str, ingestion_date=note_data.get('file_created_date'), overwrite=note_data.get('overwrite', False))


# Read functions call instance methods or query directly with filters
def get_media_transcripts(db_instance: MediaDatabase, media_id: int) -> List[Dict]:
    """
    Retrieves all active transcripts associated with an active media item.

    Filters results to only include transcripts where both the Transcript itself
    and the parent Media item are not soft-deleted (`deleted = 0`).
    Results are ordered by creation date descending (newest first).

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        media_id (int): The ID of the parent Media item.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each representing an active
                              transcript. Returns an empty list if none are found.

    Raises:
        TypeError: If `db_instance` is not a Database object or `media_id` is not int.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    logger.debug(f"Fetching transcripts for media_id={media_id} DB: {db_instance.db_path_str}")
    try:
        query = (
            "SELECT t.* FROM Transcripts t "
            "JOIN Media m ON t.media_id = m.id "
            "WHERE t.media_id = ? AND t.deleted = 0 AND m.deleted = 0 "
            "ORDER BY t.created_at DESC"
        )
        with db_instance.transaction() as conn:
            rows = db_instance._fetchall_with_connection(conn, query, (media_id,))
        return rows
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error getting transcripts media {media_id} '{db_instance.db_path_str}': {e}")
        raise DatabaseError(f"Failed get transcripts {media_id}") from e


def get_latest_transcription(db_instance: MediaDatabase, media_id: int) -> Optional[str]:
    """
    Retrieves the text content of the latest active transcript for an active media item.

    Filters for active transcripts and media, orders by creation date descending,
    and returns only the `transcription` field of the newest one.

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        media_id (int): The ID of the parent Media item.

    Returns:
        Optional[str]: The transcription text if found, otherwise None.

    Raises:
        TypeError: If `db_instance` is not a Database object or `media_id` is not int.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    try:
        query = (
            "SELECT t.transcription FROM Transcripts t "
            "JOIN Media m ON t.media_id = m.id "
            "WHERE t.media_id = ? AND t.deleted = 0 AND m.deleted = 0 "
            "ORDER BY t.created_at DESC LIMIT 1"
        )
        with db_instance.transaction() as conn:
            result = db_instance._fetchone_with_connection(conn, query, (media_id,))
        return (result or {}).get('transcription')
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error get latest transcript {media_id} '{db_instance.db_path_str}': {e}")
        raise DatabaseError(f"Failed get latest transcript {media_id}") from e


def get_specific_transcript(db_instance: MediaDatabase, transcript_uuid: str) -> Optional[Dict]:
    """
    Retrieves a specific active transcript by its UUID, ensuring parent media is active.

    Filters results to only include the transcript if both it and its parent
    Media item are not soft-deleted (`deleted = 0`).

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        transcript_uuid (str): The UUID of the transcript to retrieve.

    Returns:
        Optional[Dict[str, Any]]: A dictionary representing the transcript if found
                                   and active, otherwise None.

    Raises:
        TypeError: If `db_instance` is not Database object or `transcript_uuid` not str.
        InputError: If `transcript_uuid` is empty.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    try:
        query = (
            "SELECT t.* FROM Transcripts t "
            "JOIN Media m ON t.media_id = m.id "
            "WHERE t.uuid = ? AND t.deleted = 0 AND m.deleted = 0"
        )
        with db_instance.transaction() as conn:
            result = db_instance._fetchone_with_connection(conn, query, (transcript_uuid,))
        return result
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error get transcript UUID {transcript_uuid} '{db_instance.db_path_str}': {e}")
        raise DatabaseError(f"Failed get transcript {transcript_uuid}") from e


def get_specific_analysis(db_instance: MediaDatabase, version_uuid: str) -> Optional[str]:
    """
    Retrieves the `analysis_content` from a specific active DocumentVersion.

    Ensures both the DocumentVersion and its parent Media item are active (`deleted=0`).

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        version_uuid (str): The UUID of the DocumentVersion.

    Returns:
        Optional[str]: The analysis content string if found and active, otherwise None.

    Raises:
        TypeError: If `db_instance` is not Database object or `version_uuid` not str.
        InputError: If `version_uuid` is empty.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    try:
        query = (
            "SELECT dv.analysis_content FROM DocumentVersions dv "
            "JOIN Media m ON dv.media_id = m.id "
            "WHERE dv.uuid = ? AND dv.deleted = 0 AND m.deleted = 0"
        )
        with db_instance.transaction() as conn:
            result = db_instance._fetchone_with_connection(conn, query, (version_uuid,))
        return (result or {}).get('analysis_content')
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error get analysis UUID {version_uuid} '{db_instance.db_path_str}': {e}")
        raise DatabaseError(f"Failed get analysis {version_uuid}") from e


def get_media_prompts(db_instance: MediaDatabase, media_id: int) -> List[Dict]:
    """
    Retrieves all non-empty prompts from active DocumentVersions for an active media item.

    Filters for active versions and media, excludes rows where `prompt` is NULL or empty,
    and orders by version number descending (newest first).

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        media_id (int): The ID of the parent Media item.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing 'id', 'uuid',
                              'content' (the prompt text), 'created_at', and
                              'version_number' for matching prompts. Empty list if none.

    Raises:
        TypeError: If `db_instance` is not Database object or `media_id` not int.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    try:
        query = (
            "SELECT dv.id, dv.uuid, dv.prompt, dv.created_at, dv.version_number "
            "FROM DocumentVersions dv JOIN Media m ON dv.media_id = m.id "
            "WHERE dv.media_id = ? AND dv.deleted = 0 AND m.deleted = 0 "
            "AND dv.prompt IS NOT NULL AND dv.prompt != '' "
            "ORDER BY dv.version_number DESC"
        )
        with db_instance.transaction() as conn:
            rows = db_instance._fetchall_with_connection(conn, query, (media_id,))
        return [
            {
                'id': r['id'],
                'uuid': r['uuid'],
                'content': r['prompt'],
                'created_at': r['created_at'],
                'version_number': r['version_number'],
            }
            for r in rows
        ]
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error get prompts media {media_id} '{db_instance.db_path_str}': {e}")
        raise DatabaseError(f"Failed get prompts {media_id}") from e


def get_specific_prompt(db_instance: MediaDatabase, version_uuid: str) -> Optional[str]:
    """
    Retrieves the `prompt` text from a specific active DocumentVersion.

    Ensures both the DocumentVersion and its parent Media item are active (`deleted=0`).

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        version_uuid (str): The UUID of the DocumentVersion.

    Returns:
        Optional[str]: The prompt string if found and active, otherwise None.

    Raises:
        TypeError: If `db_instance` is not Database object or `version_uuid` not str.
        InputError: If `version_uuid` is empty.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    try:
        query = (
            "SELECT dv.prompt FROM DocumentVersions dv "
            "JOIN Media m ON dv.media_id = m.id "
            "WHERE dv.uuid = ? AND dv.deleted = 0 AND m.deleted = 0"
        )
        with db_instance.transaction() as conn:
            result = db_instance._fetchone_with_connection(conn, query, (version_uuid,))
        return (result or {}).get('prompt')
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error get prompt UUID {version_uuid} '{db_instance.db_path_str}': {e}")
        raise DatabaseError(f"Failed get prompt {version_uuid}") from e


# Specific deletes call instance methods
def soft_delete_transcript(db_instance: MediaDatabase, transcript_uuid: str) -> bool:
    """
    Soft deletes a specific transcript by its UUID.

    Sets `deleted=1`, updates `last_modified`, increments sync `version`, and
    logs a 'delete' sync event for the `Transcripts` entity. Ensures the
    parent Media item is active before proceeding.

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        transcript_uuid (str): The UUID of the transcript to soft delete.

    Returns:
        bool: True if successfully soft-deleted, False if not found or already deleted.

    Raises:
        TypeError: If `db_instance` is not a Database object.
        InputError: If `transcript_uuid` is empty or None.
        ConflictError: If the transcript's version changed concurrently.
        DatabaseError: For other database errors or sync logging failures.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    if not transcript_uuid:
        raise InputError("Transcript UUID required.")

    current_time = db_instance._get_current_utc_timestamp_str()  # Get time via instance
    client_id = db_instance.client_id
    logger.debug(f"Attempting soft delete Transcript UUID: {transcript_uuid}")
    try:
        with db_instance.transaction() as conn:
            info = db_instance._fetchone_with_connection(
                conn,
                "SELECT t.id, t.version, m.uuid as media_uuid FROM Transcripts t JOIN Media m ON t.media_id = m.id "
                "WHERE t.uuid = ? AND t.deleted = 0",
                (transcript_uuid,),
            )
            if not info:
                logger.warning(f"Transcript UUID {transcript_uuid} not found or already deleted.")
                return False
            t_id, current_version, media_uuid = info['id'], info['version'], info['media_uuid']
            new_version = current_version + 1

            # Pass current_time for last_modified
            update_cursor = db_instance._execute_with_connection(
                conn,
                "UPDATE Transcripts SET deleted=1, last_modified=?, version=?, client_id=? WHERE id=? AND version=?",
                (current_time, new_version, client_id, t_id, current_version),
            )
            if update_cursor.rowcount == 0:
                raise ConflictError("Transcripts", t_id)

            # Payload reflects the state *after* the update
            payload = {'uuid': transcript_uuid, 'media_uuid': media_uuid, 'last_modified': current_time, 'version': new_version, 'client_id': client_id, 'deleted': 1}
            db_instance._log_sync_event(conn, 'Transcripts', transcript_uuid, 'delete', new_version, payload)  # Call instance method for logging
            logger.info(f"Soft deleted Transcript UUID {transcript_uuid}. New ver: {new_version}")
            return True
    except (InputError, ConflictError, DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error soft delete Transcript UUID {transcript_uuid}: {e}", exc_info=True)
        # Re-raise specific errors, wrap general DB errors
        if isinstance(e, (InputError, ConflictError, DatabaseError)):
            raise e
        else:
            raise DatabaseError(f"Failed soft delete transcript: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected soft delete Transcript error UUID {transcript_uuid}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected transcript soft delete error: {e}") from e


# Transcript write/update helper (backend-aware)
def upsert_transcript(
    db_instance: MediaDatabase,
    media_id: int,
    transcription: str,
    whisper_model: str,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Insert or update a transcript for a media item keyed by (media_id, whisper_model).

    - On existing row: updates transcription, bumps version, updates last_modified/client_id.
    - On missing row: inserts new transcript with version=1.

    Returns a dict with id, uuid, version, media_id, whisper_model, last_modified.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    if not isinstance(media_id, int):
        raise TypeError("media_id must be int")
    if not transcription:
        raise InputError("transcription text required")
    if not whisper_model:
        raise InputError("whisper_model required")

    now = db_instance._get_current_utc_timestamp_str()
    created_val = created_at or now
    client_id = db_instance.client_id

    try:
        with db_instance.transaction() as conn:
            # Check if transcript exists
            info = db_instance._fetchone_with_connection(
                conn,
                "SELECT id, uuid, version FROM Transcripts WHERE media_id = ? AND whisper_model = ? AND deleted = 0",
                (media_id, whisper_model),
            )

            if info:
                t_id, t_uuid, cur_ver = info.get('id'), info.get('uuid'), int(info.get('version') or 1)
                new_ver = cur_ver + 1
                upd = db_instance._execute_with_connection(
                    conn,
                    (
                        "UPDATE Transcripts SET transcription = ?, last_modified = ?, version = ?, client_id = ? "
                        "WHERE id = ? AND version = ?"
                    ),
                    (transcription, now, new_ver, client_id, t_id, cur_ver),
                )
                if upd.rowcount == 0:
                    raise ConflictError("Transcripts", t_id)
                payload = {
                    'id': t_id,
                    'uuid': t_uuid,
                    'version': new_ver,
                    'media_id': media_id,
                    'whisper_model': whisper_model,
                    'last_modified': now,
                }
                db_instance._log_sync_event(conn, 'Transcripts', t_uuid, 'update', new_ver, payload)
                return payload

            # Insert new transcript
            new_uuid = str(uuid.uuid4())
            if db_instance.backend_type == BackendType.POSTGRESQL:
                insert_sql = (
                    "INSERT INTO Transcripts (media_id, whisper_model, transcription, created_at, uuid, last_modified, version, client_id, deleted) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, ?, 0) RETURNING id, version"
                )
                cur = db_instance._execute_with_connection(
                    conn,
                    insert_sql,
                    (media_id, whisper_model, transcription, created_val, new_uuid, now, client_id),
                )
                row = cur.fetchone()
                new_id = row['id'] if row else None
                new_ver = row['version'] if row else 1
            else:
                insert_sql = (
                    "INSERT INTO Transcripts (media_id, whisper_model, transcription, created_at, uuid, last_modified, version, client_id, deleted) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, ?, 0)"
                )
                cur = db_instance._execute_with_connection(
                    conn,
                    insert_sql,
                    (media_id, whisper_model, transcription, created_val, new_uuid, now, client_id),
                )
                new_id = cur.lastrowid
                new_ver = 1

            payload = {
                'id': new_id,
                'uuid': new_uuid,
                'version': new_ver,
                'media_id': media_id,
                'whisper_model': whisper_model,
                'last_modified': now,
            }
            db_instance._log_sync_event(conn, 'Transcripts', new_uuid, 'create', new_ver, payload)
            return payload
    except (InputError, ConflictError, DatabaseError, sqlite3.Error) as e:
        if isinstance(e, (InputError, ConflictError, DatabaseError)):
            raise e
        raise DatabaseError(f"Failed upsert transcript: {e}") from e
    except Exception as e:
        raise DatabaseError(f"Unexpected upsert transcript error: {e}") from e

# clear_specific_analysis/prompt call instance methods implicitly via update logic
def clear_specific_analysis(db_instance: MediaDatabase, version_uuid: str) -> bool:
    """
    Clears the `analysis_content` field (sets to NULL) for a specific active DocumentVersion.

    Updates `last_modified`, increments sync `version`, and logs an 'update'
    sync event for the `DocumentVersions` entity. Ensures the version is active.

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        version_uuid (str): The UUID of the DocumentVersion whose analysis to clear.

    Returns:
        bool: True if analysis was successfully cleared, False if version not found/deleted.

    Raises:
        TypeError: If `db_instance` is not a Database object.
        InputError: If `version_uuid` is empty or None.
        ConflictError: If the version's sync version changed concurrently.
        DatabaseError: For other database errors or sync logging failures.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    if not version_uuid:
        raise InputError("Version UUID required.")

    current_time = db_instance._get_current_utc_timestamp_str()  # Get time via instance
    client_id = db_instance.client_id
    logger.debug(f"Clearing analysis for DocVersion UUID: {version_uuid}")
    try:
        with db_instance.transaction() as conn:
            info = db_instance._fetchone_with_connection(
                conn,
                "SELECT id, version FROM DocumentVersions WHERE uuid = ? AND deleted = 0",
                (version_uuid,),
            )
            if not info:
                logger.warning(f"DocVersion UUID {version_uuid} not found or already deleted.")
                return False
            v_id, current_version = info['id'], info['version']
            new_version = current_version + 1

            # Pass current_time for last_modified
            update_cursor = db_instance._execute_with_connection(
                conn,
                "UPDATE DocumentVersions SET analysis_content=NULL, last_modified=?, version=?, client_id=? WHERE id=? AND version=?",
                (current_time, new_version, client_id, v_id, current_version),
            )
            if update_cursor.rowcount == 0:
                raise ConflictError("DocumentVersions", v_id)

            # Fetch full data for payload AFTER update
            payload = db_instance._fetchone_with_connection(
                conn,
                "SELECT dv.*, m.uuid as media_uuid FROM DocumentVersions dv JOIN Media m ON dv.media_id = m.id WHERE dv.id = ?",
                (v_id,),
            ) or {}
            db_instance._log_sync_event(conn, 'DocumentVersions', version_uuid, 'update', new_version, payload)  # Call instance method for logging
            logger.info(f"Cleared analysis for DocVersion UUID {version_uuid}. New ver: {new_version}")
            return True
    except (InputError, ConflictError, DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error clearing analysis UUID {version_uuid}: {e}", exc_info=True)
        if isinstance(e, (InputError, ConflictError, DatabaseError)):
            raise e
        else:
            raise DatabaseError(f"Failed clear analysis: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error clearing analysis UUID {version_uuid}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected clear analysis error: {e}") from e


def clear_specific_prompt(db_instance: MediaDatabase, version_uuid: str) -> bool:
    """
    Clears the `prompt` field (sets to NULL) for a specific active DocumentVersion.

    Updates `last_modified`, increments sync `version`, and logs an 'update'
    sync event for the `DocumentVersions` entity. Ensures the version is active.

    Args:
        db_instance (MediaDatabase): An initialized Database instance.
        version_uuid (str): The UUID of the DocumentVersion whose prompt to clear.

    Returns:
        bool: True if prompt was successfully cleared, False if version not found/deleted.

    Raises:
        TypeError: If `db_instance` is not a Database object.
        InputError: If `version_uuid` is empty or None.
        ConflictError: If the version's sync version changed concurrently.
        DatabaseError: For other database errors or sync logging failures.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    if not version_uuid:
        raise InputError("Version UUID required.")

    current_time = db_instance._get_current_utc_timestamp_str()  # Get time via instance
    client_id = db_instance.client_id
    logger.debug(f"Clearing prompt for DocVersion UUID: {version_uuid}")
    try:
        with db_instance.transaction() as conn:
            info = db_instance._fetchone_with_connection(
                conn,
                "SELECT id, version FROM DocumentVersions WHERE uuid = ? AND deleted = 0",
                (version_uuid,),
            )
            if not info:
                logger.warning(f"DocVersion UUID {version_uuid} not found or already deleted.")
                return False
            v_id, current_version = info['id'], info['version']
            new_version = current_version + 1

            # Pass current_time for last_modified
            update_cursor = db_instance._execute_with_connection(
                conn,
                "UPDATE DocumentVersions SET prompt=NULL, last_modified=?, version=?, client_id=? WHERE id=? AND version=?",
                (current_time, new_version, client_id, v_id, current_version),
            )
            if update_cursor.rowcount == 0:
                raise ConflictError("DocumentVersions", v_id)

            # Fetch full data for payload AFTER update
            payload = db_instance._fetchone_with_connection(
                conn,
                "SELECT dv.*, m.uuid as media_uuid FROM DocumentVersions dv JOIN Media m ON dv.media_id = m.id WHERE dv.id = ?",
                (v_id,),
            ) or {}
            db_instance._log_sync_event(conn, 'DocumentVersions', version_uuid, 'update', new_version, payload)  # Call instance method for logging
            logger.info(f"Cleared prompt for DocVersion UUID {version_uuid}. New ver: {new_version}")
            return True
    except (InputError, ConflictError, DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error clearing prompt UUID {version_uuid}: {e}", exc_info=True)
        if isinstance(e, (InputError, ConflictError, DatabaseError)):
            raise e
        else:
            raise DatabaseError(f"Failed clear prompt: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error clearing prompt UUID {version_uuid}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected clear prompt error: {e}") from e


# Other remaining functions
def get_chunk_text(db_instance: MediaDatabase, chunk_uuid: str) -> Optional[str]:
    """
    Retrieves the text content (`chunk_text`) of a specific active chunk.

    Currently queries `UnvectorizedMediaChunks`. Ensures both the chunk and its
    parent Media item are active (`deleted=0`).

    Args:
     db_instance (MediaDatabase): An initialized Database instance.
     chunk_uuid (str): The UUID of the chunk (from UnvectorizedMediaChunks).

    Returns:
     Optional[str]: The chunk text if found and active, otherwise None.

    Raises:
     TypeError: If `db_instance` is not Database object or `chunk_uuid` not str.
     InputError: If `chunk_uuid` is empty.
     DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    target_table = "UnvectorizedMediaChunks"  # Assuming this table for text
    try:
        query = f"SELECT c.chunk_text FROM {target_table} c JOIN Media m ON c.media_id = m.id WHERE c.uuid = ? AND c.deleted = 0 AND m.deleted = 0"
        cursor = db_instance.execute_query(query, (chunk_uuid,))
        result = cursor.fetchone()
        return result['chunk_text'] if result else None
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error get chunk text UUID {chunk_uuid} '{db_instance.db_path_str}': {e}")
        raise DatabaseError(f"Failed get chunk text {chunk_uuid}") from e


def get_all_content_from_database(db_instance: MediaDatabase) -> List[Dict[str, Any]]:
    """
    Retrieves basic identifying information for all active, non-trashed media items.

    Fetches `id`, `uuid`, `content`, `title`, `author`, `type`, `url`,
    `ingestion_date`, `last_modified` for items where `deleted = 0` and `is_trash = 0`.
    Ordered by `last_modified` descending.

    Args:
        db_instance (MediaDatabase): An initialized Database instance.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each representing an active
                              media item. Empty list if none found.

    Raises:
        TypeError: If `db_instance` is not a Database object.
        DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    try:
        cursor = db_instance.execute_query("SELECT id, uuid, content, title, author, type, url, ingestion_date, last_modified FROM Media WHERE deleted = 0 AND is_trash = 0 ORDER BY last_modified DESC")
        return [dict(item) for item in cursor.fetchall()]
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error retrieving all content DB '{db_instance.db_path_str}': {e}")
        raise DatabaseError("Error retrieving all content") from e


def permanently_delete_item(db_instance: MediaDatabase, media_id: int) -> bool:
    """
        Performs a HARD delete of a media item and its related data via cascades.

        **DANGER:** This operation bypasses the soft delete mechanism and the sync log.
        It physically removes the row from the `Media` table. Foreign key constraints
        with `ON DELETE CASCADE` should automatically delete related rows in child
        tables (`Transcripts`, `MediaKeywords`, `DocumentVersions`, etc.). It also
        explicitly removes the corresponding FTS entry. Use with extreme caution,
        especially in synchronized environments, as this change will not be propagated
        through the sync log. Primarily intended for cleanup or specific admin tasks.

        Args:
            db_instance (MediaDatabase): An initialized Database instance.
            media_id (int): The ID of the Media item to permanently delete.

        Returns:
            bool: True if the item was found and deleted, False otherwise.

        Raises:
            TypeError: If `db_instance` is not a Database object.
            DatabaseError: For database errors during deletion.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    logger.warning(f"!!! PERMANENT DELETE initiated Media ID: {media_id} DB {db_instance.db_path_str}. NOT SYNCED !!!")
    try:
        with db_instance.transaction() as conn:
            # Existence check (backend-aware placeholders handled by execute_query)
            sel_cur = db_instance.execute_query("SELECT 1 AS one FROM Media WHERE id = ?", (media_id,))
            row = sel_cur.fetchone()
            if not row:
                logger.warning(f"Permanent delete failed: Media {media_id} not found.")
                return False

            # Hard delete - Cascades should handle children via FKs
            del_cur = db_instance.execute_query("DELETE FROM Media WHERE id = ?", (media_id,), commit=False)
            deleted_count = getattr(del_cur, "rowcount", 0) or 0

            # Manually clear/update FTS vectors as a belt-and-suspenders
            try:
                db_instance._delete_fts_media(conn, media_id)
            except Exception as _fts_exc:
                logger.debug(f"FTS cleanup during permanent delete skipped/failed: {_fts_exc}")

        if int(deleted_count) > 0:
            logger.info(f"Permanently deleted Media ID: {media_id}. NO sync log generated.")
            # Invalidate agentic intra-doc vectors
            try:
                from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import invalidate_intra_doc_vectors  # lazy import
                invalidate_intra_doc_vectors(str(media_id))
            except Exception:
                pass
            return True
        logger.error(f"Permanent delete failed unexpectedly Media {media_id}.")
        return False
    except sqlite3.Error as e:
        logger.error(f"Error permanently deleting Media {media_id}: {e}", exc_info=True)
        raise DatabaseError(f"Failed permanently delete item: {e}") from e
    except Exception as e:
        (logger.error(f"Unexpected error permanently deleting Media {media_id}: {e}", exc_info=True))
        raise DatabaseError(f"Unexpected permanent delete error: {e}") from e


# Keyword read functions use instance methods or query directly
def fetch_keywords_for_media(media_id: int, db_instance: MediaDatabase) -> List[str]:
    """
       Fetches all active keywords associated with a specific active media item.

       Filters results to only include keywords where both the Keyword itself and
       the parent Media item are not soft-deleted (`deleted = 0`).
       Results are sorted alphabetically (case-insensitive).

       Args:
           media_id (int): The ID of the Media item.
           db_instance (MediaDatabase): An initialized Database instance.

       Returns:
           List[str]: A sorted list of active keyword strings linked to the media item.
                      Returns an empty list if none are found or if the media item
                      is inactive.

       Raises:
           TypeError: If `db_instance` is not Database object or `media_id` not int.
           DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    logger.debug(f"Fetching keywords media_id={media_id} DB: {db_instance.db_path_str}")
    try:
        order_expr = db_instance._keyword_order_expression("k.keyword")  # type: ignore[attr-defined]
        query = (
            f"SELECT k.keyword FROM Keywords k "
            "JOIN MediaKeywords mk ON k.id = mk.keyword_id "
            "JOIN Media m ON mk.media_id = m.id "
            "WHERE mk.media_id = ? AND k.deleted = ? AND m.deleted = ? "
            f"ORDER BY {order_expr}"
        )
        cursor = db_instance.execute_query(query, (media_id, False, False))
        return [row['keyword'] for row in cursor.fetchall()]
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Error fetching keywords media_id {media_id} '{db_instance.db_path_str}': {e}", exc_info=True)
        raise DatabaseError(f"Failed fetch keywords {media_id}") from e


def fetch_keywords_for_media_batch(media_ids: List[int], db_instance: MediaDatabase) -> Dict[int, List[str]]:
    """
       Fetches active keywords for multiple active media items in a single query.

       Returns a dictionary mapping each requested `media_id` to a sorted list of
       its associated active keyword strings. Only includes media IDs that were
       found and are active.

       Args:
           media_ids (List[int]): A list of Media item IDs.
           db_instance (MediaDatabase): An initialized Database instance.

       Returns:
           Dict[int, List[str]]: A dictionary where keys are the input `media_id`s
                                 (that are active and have keywords) and values are sorted
                                 lists of their active keyword strings. IDs not found,
                                 inactive, or without keywords will be omitted.

       Raises:
           TypeError: If `db_instance` is not Database object or `media_ids` not list.
           InputError: If `media_ids` contains non-integer values.
           DatabaseError: For database query errors.
    """
    if not isinstance(db_instance, MediaDatabase):
        raise TypeError("db_instance required.")
    if not media_ids:
        return {}
    try:
        safe_media_ids = [int(mid) for mid in media_ids]
    except (ValueError, TypeError) as e:
        raise InputError(f"media_ids must be list of integers: {e}")
    if not safe_media_ids:
        return {}
    keywords_map = {media_id: [] for media_id in safe_media_ids}
    placeholders = ','.join('?' * len(safe_media_ids))
    order_expr = db_instance._keyword_order_expression("k.keyword")  # type: ignore[attr-defined]
    query = (
        f"SELECT mk.media_id, k.keyword FROM MediaKeywords mk "
        "JOIN Keywords k ON mk.keyword_id = k.id "
        "JOIN Media m ON mk.media_id = m.id "
        f"WHERE mk.media_id IN ({placeholders}) AND k.deleted = ? AND m.deleted = ? "
        f"ORDER BY mk.media_id, {order_expr}"
    )
    params = tuple(safe_media_ids + [False, False])
    try:
        cursor = db_instance.execute_query(query, params)
        for row in cursor.fetchall():
            if row['media_id'] in keywords_map:
                keywords_map[row['media_id']].append(row['keyword'])
        return keywords_map
    except (DatabaseError, sqlite3.Error) as e:
        logger.error(f"Failed fetch keywords batch '{db_instance.db_path_str}': {e}", exc_info=True)
        raise DatabaseError("Failed fetch keywords batch") from e


# Runtime compatibility patch: ensure get_media_by_title exists on MediaDatabase
try:
    _ = getattr(MediaDatabase, "get_media_by_title")
except Exception:
    _ = None
if not _:
    def _get_media_by_title(self, title: str, include_deleted: bool = False, include_trash: bool = False) -> Optional[Dict]:
        """Fetch the most recently modified active media by exact title.

        Mirrors other getter helpers. Ordered by last_modified DESC to prefer latest.
        """
        if not title:
            raise InputError("title cannot be empty or None.")

        query = "SELECT * FROM Media WHERE title = ?"
        params = [title]

        if not include_deleted:
            query += " AND deleted = 0"
        if not include_trash:
            query += " AND is_trash = 0"

        query += " ORDER BY last_modified DESC LIMIT 1"

        try:
            cursor = self.execute_query(query, tuple(params))
            result = cursor.fetchone()
            return dict(result) if result else None
        except sqlite3.Error as e:
            logger.error(f"Error fetching media by title '{title}': {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch media by title: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching media by title '{title}': {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error fetching media by title: {e}") from e

    setattr(MediaDatabase, "get_media_by_title", _get_media_by_title)

#
# End of Media_DB_v2.py
#######################################################################################################################
