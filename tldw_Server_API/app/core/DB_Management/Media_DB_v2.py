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
import shlex
import sqlite3
import threading
import time
import uuid  # For UUID generation
from configparser import ConfigParser
from contextlib import contextmanager, nullcontext, suppress
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone  # Use timezone-aware UTC
from email.utils import getaddresses, parsedate_to_datetime
from math import ceil, isfinite
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
except ImportError:  # pragma: no cover - defensive fallback
    import logging as _stdlib_logging
    logger = _stdlib_logging.getLogger("Media_DB_v2")
    logging = logger

import yaml

from tldw_Server_API.app.core.DB_Management.db_migration import DatabaseMigrator, MigrationError
from tldw_Server_API.app.core.DB_Management.sqlite_policy import (
    begin_immediate_if_needed,
    configure_sqlite_connection,
)
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter, log_histogram

from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseBackend,
    DatabaseConfig,
    QueryResult,
)
from tldw_Server_API.app.core.DB_Management.backends.base import (
    DatabaseError as BackendDatabaseError,
)
from tldw_Server_API.app.core.DB_Management.media_db.errors import (
    ConflictError,
    DatabaseError,
    InputError,
    SchemaError,
)
from tldw_Server_API.app.core.DB_Management.media_db.dedupe_urls import (
    media_dedupe_url_candidates,
    normalize_media_dedupe_url,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.rows import (
    BackendCursorAdapter,
    RowAdapter,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.execution import (
    close_sqlite_ephemeral,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_wrappers import (
    get_document_version,
    import_obsidian_note_to_db,
    ingest_article_to_db_new,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_reads import (
    get_latest_transcription,
    get_media_prompts,
    get_media_transcripts,
    get_specific_prompt,
    get_specific_transcript,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_state import (
    check_media_exists,
    get_unprocessed_media,
    mark_media_as_processed,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_document_artifacts import (
    clear_specific_analysis,
    clear_specific_prompt,
    get_chunk_text,
    get_specific_analysis,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_content_queries import (
    fetch_keywords_for_media as _fetch_keywords_for_media,
    get_all_content_from_database,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_media_details import (
    get_full_media_details,
    get_full_media_details_rich,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_backup import (
    create_automated_backup,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_maintenance import (
    permanently_delete_item as _permanently_delete_item,
)
from tldw_Server_API.app.core.DB_Management.media_db.schema.bootstrap import (
    ensure_media_schema,
)
from tldw_Server_API.app.core.DB_Management.media_db.schema.features.core_media import (
    apply_postgres_core_media_schema,
    apply_sqlite_core_media_schema,
)
from tldw_Server_API.app.core.DB_Management.media_db.schema.features.fts import (
    ensure_postgres_fts,
    ensure_sqlite_fts_structures,
)
from tldw_Server_API.app.core.DB_Management.media_db.schema.features.policies import (
    ensure_postgres_policies,
)
from tldw_Server_API.app.core.DB_Management.media_db.schema.migrations import (
    get_postgres_migrations,
    run_postgres_migrations,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.collections import (
    load_collections_database_cls,
)
from tldw_Server_API.app.core.DB_Management.media_db.repositories import (
    ChunksRepository,
    DocumentVersionsRepository,
    KeywordsRepository,
    MediaRepository,
    MediaFilesRepository,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.backends.query_utils import (
    convert_sqlite_placeholders_to_postgres,
    normalise_params,
    prepare_backend_many_statement,
    prepare_backend_statement,
)
from tldw_Server_API.app.core.DB_Management.content_backend import get_content_backend, load_content_db_settings
from tldw_Server_API.app.core.DB_Management.scope_context import get_scope
from tldw_Server_API.app.core.testing import is_test_mode

# Use application-wide logging configuration; avoid configuring here.

_CollectionsDB = load_collections_database_cls()
_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def _coerce_email_metric_label(value: Any, *, default: str = "unknown") -> str:
    raw = str(value or "").strip().lower()
    return raw or default


def _emit_email_metric_counter(
    metric_name: str,
    *,
    labels: dict[str, Any] | None = None,
) -> None:
    with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
        safe_labels = (
            {str(k): _coerce_email_metric_label(v, default="none") for k, v in labels.items()}
            if labels
            else None
        )
        log_counter(metric_name, labels=safe_labels)


def _emit_email_metric_histogram(
    metric_name: str,
    value: float,
    *,
    labels: dict[str, Any] | None = None,
) -> None:
    with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
        safe_labels = (
            {str(k): _coerce_email_metric_label(v, default="none") for k, v in labels.items()}
            if labels
            else None
        )
        safe_value = max(0.0, float(value))
        log_histogram(metric_name, safe_value, labels=safe_labels)


_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DATA_TABLES_UNSET = object()


_RowAdapter = RowAdapter


# --- Database Class ---
class MediaDatabase:
    """
    Manages SQLite connection and operations for a specific database file,
    handling sync metadata and FTS updates internally via Python code.
    Requires client_id on initialization. Includes schema versioning.
    """
    _CURRENT_SCHEMA_VERSION = 22  # Email-native schema bootstrap + lookup indexes

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
        source_hash TEXT,
        uuid TEXT UNIQUE NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        org_id INTEGER,
        team_id INTEGER,
        visibility TEXT DEFAULT 'personal' CHECK (visibility IN ('personal', 'team', 'org')),
        owner_user_id INTEGER,
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

    -- VisualDocuments Table --
    -- Stores per-media image-derived artifacts (figures, frames, screenshots) with
    -- captions/OCR and soft-delete/versioning semantics.
    CREATE TABLE IF NOT EXISTS VisualDocuments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER NOT NULL,
        location TEXT,
        page_number INTEGER,
        frame_index INTEGER,
        timestamp_seconds REAL,
        caption TEXT,
        ocr_text TEXT,
        tags TEXT,
        thumbnail_path TEXT,
        extra_metadata TEXT,
        uuid TEXT UNIQUE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT,
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
    CREATE INDEX IF NOT EXISTS idx_media_source_hash ON Media(source_hash);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_media_uuid ON Media(uuid);
    CREATE INDEX IF NOT EXISTS idx_media_last_modified ON Media(last_modified);
    CREATE INDEX IF NOT EXISTS idx_media_deleted ON Media(deleted);
    CREATE INDEX IF NOT EXISTS idx_media_prev_version ON Media(prev_version);
    CREATE INDEX IF NOT EXISTS idx_media_merge_parent_uuid ON Media(merge_parent_uuid);
    CREATE INDEX IF NOT EXISTS idx_media_org_id ON Media(org_id);
    CREATE INDEX IF NOT EXISTS idx_media_team_id ON Media(team_id);
    CREATE INDEX IF NOT EXISTS idx_media_visibility ON Media(visibility);
    CREATE INDEX IF NOT EXISTS idx_media_owner_user_id ON Media(owner_user_id);

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

    -- VisualDocuments indices --
    CREATE INDEX IF NOT EXISTS idx_visualdocs_media_id ON VisualDocuments(media_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_visualdocs_uuid ON VisualDocuments(uuid);
    CREATE INDEX IF NOT EXISTS idx_visualdocs_last_modified ON VisualDocuments(last_modified);
    CREATE INDEX IF NOT EXISTS idx_visualdocs_deleted ON VisualDocuments(deleted);
    CREATE INDEX IF NOT EXISTS idx_visualdocs_prev_version ON VisualDocuments(prev_version);
    CREATE INDEX IF NOT EXISTS idx_visualdocs_merge_parent_uuid ON VisualDocuments(merge_parent_uuid);
    CREATE INDEX IF NOT EXISTS idx_visualdocs_page_frame ON VisualDocuments(media_id, page_number, frame_index);
    CREATE INDEX IF NOT EXISTS idx_visualdocs_caption ON VisualDocuments(caption);
    CREATE INDEX IF NOT EXISTS idx_visualdocs_tags ON VisualDocuments(tags);

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
    CREATE INDEX IF NOT EXISTS idx_dsi_media_path ON DocumentStructureIndex(media_id, path);

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
    DROP TRIGGER IF EXISTS claims_ai;
    CREATE TRIGGER IF NOT EXISTS claims_ai AFTER INSERT ON Claims BEGIN
        -- Only index non-deleted claims
        INSERT INTO claims_fts(rowid, claim_text)
        SELECT NEW.id, NEW.claim_text WHERE NEW.deleted = 0;
    END;

    DROP TRIGGER IF EXISTS claims_au;
    CREATE TRIGGER IF NOT EXISTS claims_au AFTER UPDATE ON Claims BEGIN
        -- Remove previous terms then re-index when not deleted
        INSERT INTO claims_fts(claims_fts, rowid, claim_text)
        SELECT 'delete', OLD.id, OLD.claim_text WHERE OLD.deleted = 0;
        INSERT INTO claims_fts(rowid, claim_text)
        SELECT NEW.id, NEW.claim_text WHERE NEW.deleted = 0;
    END;

    DROP TRIGGER IF EXISTS claims_ad;
    CREATE TRIGGER IF NOT EXISTS claims_ad AFTER DELETE ON Claims BEGIN
        INSERT INTO claims_fts(claims_fts, rowid, claim_text)
        SELECT 'delete', OLD.id, OLD.claim_text WHERE OLD.deleted = 0;
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
        review_status TEXT NOT NULL DEFAULT 'pending',
        reviewer_id INTEGER,
        review_group TEXT,
        reviewed_at DATETIME,
        review_notes TEXT,
        review_version INTEGER NOT NULL DEFAULT 1,
        review_reason_code TEXT,
        claim_cluster_id INTEGER,
        FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_claims_media_id ON Claims(media_id);
    CREATE INDEX IF NOT EXISTS idx_claims_media_chunk ON Claims(media_id, chunk_index);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_claims_uuid ON Claims(uuid);
    CREATE INDEX IF NOT EXISTS idx_claims_deleted ON Claims(deleted);
    CREATE INDEX IF NOT EXISTS idx_claims_review_status ON Claims(review_status);
    CREATE INDEX IF NOT EXISTS idx_claims_reviewer_id ON Claims(reviewer_id);
    CREATE INDEX IF NOT EXISTS idx_claims_review_group ON Claims(review_group);
    CREATE INDEX IF NOT EXISTS idx_claims_cluster_id ON Claims(claim_cluster_id);

    CREATE TABLE IF NOT EXISTS claims_review_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_id INTEGER NOT NULL,
        old_status TEXT,
        new_status TEXT,
        old_text TEXT,
        new_text TEXT,
        reviewer_id INTEGER,
        notes TEXT,
        reason_code TEXT,
        action_ip TEXT,
        action_user_agent TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (claim_id) REFERENCES Claims(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_claims_review_log_claim ON claims_review_log(claim_id);
    CREATE INDEX IF NOT EXISTS idx_claims_review_log_reviewer ON claims_review_log(reviewer_id);
    CREATE INDEX IF NOT EXISTS idx_claims_review_log_created ON claims_review_log(created_at);

    CREATE TABLE IF NOT EXISTS claims_review_extractor_metrics_daily (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        report_date TEXT NOT NULL,
        extractor TEXT NOT NULL,
        extractor_version TEXT NOT NULL DEFAULT '',
        total_reviewed INTEGER NOT NULL DEFAULT 0,
        approved_count INTEGER NOT NULL DEFAULT 0,
        rejected_count INTEGER NOT NULL DEFAULT 0,
        flagged_count INTEGER NOT NULL DEFAULT 0,
        reassigned_count INTEGER NOT NULL DEFAULT 0,
        edited_count INTEGER NOT NULL DEFAULT 0,
        reason_code_counts_json TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, report_date, extractor, extractor_version)
    );
    CREATE INDEX IF NOT EXISTS idx_claims_review_metrics_user ON claims_review_extractor_metrics_daily(user_id);
    CREATE INDEX IF NOT EXISTS idx_claims_review_metrics_date ON claims_review_extractor_metrics_daily(report_date);
    CREATE INDEX IF NOT EXISTS idx_claims_review_metrics_extractor ON claims_review_extractor_metrics_daily(extractor);

    CREATE TABLE IF NOT EXISTS claims_review_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 0,
        predicate_json TEXT NOT NULL,
        reviewer_id INTEGER,
        review_group TEXT,
        active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_claims_review_rules_user ON claims_review_rules(user_id);
    CREATE INDEX IF NOT EXISTS idx_claims_review_rules_active ON claims_review_rules(active);

    CREATE TABLE IF NOT EXISTS claims_monitoring_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        severity TEXT,
        payload_json TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        delivered_at DATETIME
    );
    CREATE INDEX IF NOT EXISTS idx_claims_monitoring_events_user ON claims_monitoring_events(user_id);
    CREATE INDEX IF NOT EXISTS idx_claims_monitoring_events_type ON claims_monitoring_events(event_type);
    CREATE INDEX IF NOT EXISTS idx_claims_monitoring_events_delivered ON claims_monitoring_events(delivered_at);

    CREATE TABLE IF NOT EXISTS claims_monitoring_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        threshold_ratio REAL,
        baseline_ratio REAL,
        slack_webhook_url TEXT,
        webhook_url TEXT,
        email_recipients TEXT,
        enabled BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_claims_monitoring_settings_user ON claims_monitoring_settings(user_id);

    CREATE TABLE IF NOT EXISTS claims_monitoring_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        threshold_ratio REAL,
        baseline_ratio REAL,
        channels_json TEXT NOT NULL,
        slack_webhook_url TEXT,
        webhook_url TEXT,
        email_recipients TEXT,
        enabled BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_claims_monitoring_alerts_user ON claims_monitoring_alerts(user_id);

    CREATE TABLE IF NOT EXISTS claims_monitoring_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        threshold_ratio REAL,
        baseline_ratio REAL,
        slack_webhook_url TEXT,
        webhook_url TEXT,
        email_recipients TEXT,
        enabled BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_claims_monitoring_user ON claims_monitoring_config(user_id);

    CREATE TABLE IF NOT EXISTS claims_monitoring_health (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        queue_size INTEGER NOT NULL DEFAULT 0,
        worker_count INTEGER,
        last_worker_heartbeat TEXT,
        last_processed_at TEXT,
        last_failure_at TEXT,
        last_failure_reason TEXT,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_claims_monitoring_health_user ON claims_monitoring_health(user_id);

    CREATE TABLE IF NOT EXISTS claims_analytics_exports (
        export_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        format TEXT NOT NULL,
        status TEXT NOT NULL,
        payload_json TEXT,
        payload_csv TEXT,
        filters_json TEXT,
        pagination_json TEXT,
        error_message TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_claims_analytics_exports_user ON claims_analytics_exports(user_id);

    CREATE TABLE IF NOT EXISTS claims_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        target_user_id TEXT,
        target_review_group TEXT,
        resource_type TEXT,
        resource_id TEXT,
        payload_json TEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        delivered_at DATETIME
    );
    CREATE INDEX IF NOT EXISTS idx_claims_notifications_user ON claims_notifications(user_id);
    CREATE INDEX IF NOT EXISTS idx_claims_notifications_kind ON claims_notifications(kind);
    CREATE INDEX IF NOT EXISTS idx_claims_notifications_target_user ON claims_notifications(target_user_id);
    CREATE INDEX IF NOT EXISTS idx_claims_notifications_review_group ON claims_notifications(target_review_group);
    CREATE INDEX IF NOT EXISTS idx_claims_notifications_resource ON claims_notifications(resource_type, resource_id);
    CREATE INDEX IF NOT EXISTS idx_claims_notifications_delivered ON claims_notifications(delivered_at);

    CREATE TABLE IF NOT EXISTS claim_clusters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        canonical_claim_text TEXT,
        representative_claim_id INTEGER,
        summary TEXT,
        cluster_version INTEGER NOT NULL DEFAULT 1,
        watchlist_count INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_claim_clusters_user ON claim_clusters(user_id);
    CREATE INDEX IF NOT EXISTS idx_claim_clusters_updated ON claim_clusters(updated_at);

    CREATE TABLE IF NOT EXISTS claim_cluster_membership (
        cluster_id INTEGER NOT NULL,
        claim_id INTEGER NOT NULL,
        similarity_score REAL,
        cluster_joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (cluster_id, claim_id)
    );
    CREATE INDEX IF NOT EXISTS idx_claim_cluster_membership_claim ON claim_cluster_membership(claim_id);

    CREATE TABLE IF NOT EXISTS claim_cluster_links (
        parent_cluster_id INTEGER NOT NULL,
        child_cluster_id INTEGER NOT NULL,
        relation_type TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (parent_cluster_id, child_cluster_id)
    );
    """

    _MEDIA_FILES_TABLE_SQL = """
    -- MediaFiles Table --
    -- Stores original uploaded files and derived artifacts for media items.
    -- Enables PDF viewing and other original file retrieval features.
    CREATE TABLE IF NOT EXISTS MediaFiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER NOT NULL,
        file_type TEXT NOT NULL DEFAULT 'original',
        storage_path TEXT NOT NULL,
        original_filename TEXT,
        file_size INTEGER,
        mime_type TEXT,
        checksum TEXT,
        uuid TEXT UNIQUE NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT,
        FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_media_files_media_id ON MediaFiles(media_id);
    CREATE INDEX IF NOT EXISTS idx_media_files_type ON MediaFiles(file_type);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_media_files_uuid ON MediaFiles(uuid);
    CREATE INDEX IF NOT EXISTS idx_media_files_deleted ON MediaFiles(deleted);
    """

    _TTS_HISTORY_TABLE_SQL = """
    -- TTS History Table --
    CREATE TABLE IF NOT EXISTS tts_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        text TEXT,
        text_hash TEXT NOT NULL,
        text_length INTEGER,
        provider TEXT,
        model TEXT,
        voice_id TEXT,
        voice_name TEXT,
        voice_info TEXT,
        format TEXT,
        duration_ms INTEGER,
        generation_time_ms INTEGER,
        params_json TEXT,
        status TEXT,
        segments_json TEXT,
        favorite BOOLEAN NOT NULL DEFAULT 0,
        job_id INTEGER,
        output_id INTEGER,
        artifact_ids TEXT,
        artifact_deleted_at TEXT,
        error_message TEXT,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        deleted_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_tts_history_user_created ON tts_history(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_tts_history_user_favorite ON tts_history(user_id, favorite);
    CREATE INDEX IF NOT EXISTS idx_tts_history_user_provider ON tts_history(user_id, provider);
    CREATE INDEX IF NOT EXISTS idx_tts_history_user_model ON tts_history(user_id, model);
    CREATE INDEX IF NOT EXISTS idx_tts_history_user_voice_id ON tts_history(user_id, voice_id);
    CREATE INDEX IF NOT EXISTS idx_tts_history_user_text_hash ON tts_history(user_id, text_hash);
    """

    _DATA_TABLES_SQL = """
    -- Data Tables (LLM-generated structured tables) --
    CREATE TABLE IF NOT EXISTS data_tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        workspace_tag TEXT,
        prompt TEXT NOT NULL,
        column_hints_json TEXT,
        status TEXT NOT NULL DEFAULT 'queued',
        row_count INTEGER NOT NULL DEFAULT 0,
        generation_model TEXT,
        last_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_data_tables_status ON data_tables(status);
    CREATE INDEX IF NOT EXISTS idx_data_tables_updated ON data_tables(updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_data_tables_deleted ON data_tables(deleted);
    CREATE INDEX IF NOT EXISTS idx_data_tables_workspace_tag ON data_tables(workspace_tag);

    CREATE TABLE IF NOT EXISTS data_table_columns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_id INTEGER NOT NULL,
        column_id TEXT NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        description TEXT,
        format TEXT,
        position INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT,
        FOREIGN KEY (table_id) REFERENCES data_tables(id) ON DELETE CASCADE
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ux_data_table_columns_table_column ON data_table_columns(table_id, column_id);
    CREATE INDEX IF NOT EXISTS idx_data_table_columns_table_position ON data_table_columns(table_id, position);
    CREATE UNIQUE INDEX IF NOT EXISTS ux_data_table_columns_table_position_active ON data_table_columns(table_id, position, deleted);

    CREATE TABLE IF NOT EXISTS data_table_rows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_id INTEGER NOT NULL,
        row_id TEXT NOT NULL,
        row_index INTEGER NOT NULL,
        row_json TEXT NOT NULL,
        row_hash TEXT,
        created_at TEXT NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT,
        FOREIGN KEY (table_id) REFERENCES data_tables(id) ON DELETE CASCADE
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ux_data_table_rows_table_row ON data_table_rows(table_id, row_id);
    CREATE INDEX IF NOT EXISTS idx_data_table_rows_table_index ON data_table_rows(table_id, row_index);
    CREATE UNIQUE INDEX IF NOT EXISTS ux_data_table_rows_table_index_active ON data_table_rows(table_id, row_index, deleted);

    CREATE TABLE IF NOT EXISTS data_table_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_id INTEGER NOT NULL,
        source_type TEXT NOT NULL,
        source_id TEXT NOT NULL,
        title TEXT,
        snapshot_json TEXT,
        retrieval_params_json TEXT,
        created_at TEXT NOT NULL,
        last_modified DATETIME NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        client_id TEXT NOT NULL,
        deleted BOOLEAN NOT NULL DEFAULT 0,
        prev_version INTEGER,
        merge_parent_uuid TEXT,
        FOREIGN KEY (table_id) REFERENCES data_tables(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_data_table_sources_table ON data_table_sources(table_id);
    """

    _EMAIL_SCHEMA_SQL = """
    -- Email Sources --
    CREATE TABLE IF NOT EXISTS email_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        provider TEXT NOT NULL DEFAULT 'upload',
        source_key TEXT NOT NULL,
        display_name TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (tenant_id, provider, source_key)
    );

    -- Email Messages (normalized message identity + denormalized search helper columns)
    CREATE TABLE IF NOT EXISTS email_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        media_id INTEGER NOT NULL UNIQUE,
        source_id INTEGER NOT NULL,
        source_message_id TEXT,
        message_id TEXT,
        subject TEXT,
        body_text TEXT,
        internal_date DATETIME,
        from_text TEXT,
        to_text TEXT,
        cc_text TEXT,
        bcc_text TEXT,
        label_text TEXT,
        has_attachments BOOLEAN NOT NULL DEFAULT 0,
        raw_metadata_json TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE,
        FOREIGN KEY (source_id) REFERENCES email_sources(id) ON DELETE CASCADE
    );

    -- Email Participants --
    CREATE TABLE IF NOT EXISTS email_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        email_normalized TEXT NOT NULL,
        display_name TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (tenant_id, email_normalized)
    );

    -- Message <-> Participant role mapping
    CREATE TABLE IF NOT EXISTS email_message_participants (
        email_message_id INTEGER NOT NULL,
        participant_id INTEGER NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('from', 'to', 'cc', 'bcc')),
        PRIMARY KEY (email_message_id, participant_id, role),
        FOREIGN KEY (email_message_id) REFERENCES email_messages(id) ON DELETE CASCADE,
        FOREIGN KEY (participant_id) REFERENCES email_participants(id) ON DELETE CASCADE
    );

    -- Labels and message-label mappings
    CREATE TABLE IF NOT EXISTS email_labels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        label_key TEXT NOT NULL,
        label_name TEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (tenant_id, label_key)
    );

    CREATE TABLE IF NOT EXISTS email_message_labels (
        email_message_id INTEGER NOT NULL,
        label_id INTEGER NOT NULL,
        PRIMARY KEY (email_message_id, label_id),
        FOREIGN KEY (email_message_id) REFERENCES email_messages(id) ON DELETE CASCADE,
        FOREIGN KEY (label_id) REFERENCES email_labels(id) ON DELETE CASCADE
    );

    -- Attachment metadata
    CREATE TABLE IF NOT EXISTS email_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_message_id INTEGER NOT NULL,
        filename TEXT,
        content_type TEXT,
        size_bytes INTEGER,
        content_id TEXT,
        disposition TEXT,
        extracted_text_available BOOLEAN NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (email_message_id) REFERENCES email_messages(id) ON DELETE CASCADE
    );

    -- Sync cursor/checkpoint state
    CREATE TABLE IF NOT EXISTS email_sync_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        source_id INTEGER NOT NULL,
        cursor TEXT,
        last_run_at DATETIME,
        last_success_at DATETIME,
        error_state TEXT,
        retry_backoff_count INTEGER NOT NULL DEFAULT 0,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (tenant_id, source_id),
        FOREIGN KEY (source_id) REFERENCES email_sources(id) ON DELETE CASCADE
    );

    -- Legacy media -> normalized email backfill checkpoint state
    CREATE TABLE IF NOT EXISTS email_backfill_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        backfill_key TEXT NOT NULL,
        last_media_id INTEGER NOT NULL DEFAULT 0,
        processed_count INTEGER NOT NULL DEFAULT 0,
        success_count INTEGER NOT NULL DEFAULT 0,
        skipped_count INTEGER NOT NULL DEFAULT 0,
        failed_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'idle',
        last_error TEXT,
        started_at DATETIME,
        completed_at DATETIME,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (tenant_id, backfill_key)
    );
    """

    _EMAIL_INDICES_SQL = """
    CREATE INDEX IF NOT EXISTS idx_email_sources_tenant_provider ON email_sources(tenant_id, provider);
    CREATE INDEX IF NOT EXISTS idx_email_messages_tenant_date ON email_messages(tenant_id, internal_date);
    CREATE INDEX IF NOT EXISTS idx_email_messages_tenant_date_id ON email_messages(tenant_id, internal_date DESC, id DESC);
    CREATE INDEX IF NOT EXISTS idx_email_messages_tenant_has_attachments_date
        ON email_messages(tenant_id, has_attachments, internal_date DESC, id DESC);
    CREATE INDEX IF NOT EXISTS idx_email_messages_source_id ON email_messages(source_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_email_messages_tenant_source_message
        ON email_messages(tenant_id, source_id, source_message_id)
        WHERE source_message_id IS NOT NULL AND source_message_id <> '';
    CREATE UNIQUE INDEX IF NOT EXISTS idx_email_messages_tenant_message_id
        ON email_messages(tenant_id, source_id, message_id)
        WHERE message_id IS NOT NULL AND message_id <> '';
    CREATE INDEX IF NOT EXISTS idx_email_participants_tenant_email ON email_participants(tenant_id, email_normalized);
    CREATE INDEX IF NOT EXISTS idx_email_message_participants_role ON email_message_participants(role);
    CREATE INDEX IF NOT EXISTS idx_email_message_participants_message_role
        ON email_message_participants(email_message_id, role, participant_id);
    CREATE INDEX IF NOT EXISTS idx_email_labels_tenant_name ON email_labels(tenant_id, label_name);
    CREATE INDEX IF NOT EXISTS idx_email_message_labels_label ON email_message_labels(label_id);
    CREATE INDEX IF NOT EXISTS idx_email_attachments_message_id ON email_attachments(email_message_id);
    CREATE INDEX IF NOT EXISTS idx_email_sync_state_tenant_source ON email_sync_state(tenant_id, source_id);
    CREATE INDEX IF NOT EXISTS idx_email_backfill_state_status ON email_backfill_state(status);
    """

    _EMAIL_SQLITE_FTS_SQL = """
    CREATE VIRTUAL TABLE IF NOT EXISTS email_fts USING fts5(
        subject,
        body_text,
        from_text,
        to_text,
        cc_text,
        bcc_text,
        label_text,
        content='email_messages',
        content_rowid='id'
    );
    """

    def __init__(
        self,
        db_path: str | Path,
        client_id: str,
        *,
        backend: DatabaseBackend | None = None,
        config: ConfigParser | None = None,
        default_org_id: int | None = None,
        default_team_id: int | None = None,
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
        if isinstance(db_path, str) and db_path.strip() == "":
            raise ValueError("db_path cannot be an empty string; pass an explicit path or ':memory:'")  # noqa: TRY003

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
            raise ValueError("Client ID cannot be empty or None.")  # noqa: TRY003
        self.client_id = client_id

        # Ensure parent directory exists if it's a file-based DB
        if not self.is_memory_db:
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                # Catch potential errors creating the directory (e.g., permissions)
                raise DatabaseError(f"Failed to create database directory {self.db_path.parent}: {e}") from e  # noqa: TRY003

        logging.info(f"Initializing Database object for path: {self.db_path_str} [Client ID: {self.client_id}]")

        # Resolve database backend (defaults to sqlite when none configured)
        self.backend = self._resolve_backend(backend=backend, config=config)
        self.backend_type = self.backend.backend_type
        self.default_org_id = default_org_id
        self.default_team_id = default_team_id

        # Transaction-scoped connection and depth (context-local for async safety)
        self._txn_conn_var: ContextVar[Any | None] = ContextVar(
            f"media_db_txn_conn_{id(self)}",
            default=None,
        )
        self._tx_depth_var: ContextVar[int] = ContextVar(
            f"media_db_tx_depth_{id(self)}",
            default=0,
        )
        # Persistent non-transaction connection (PostgreSQL) is context-local; SQLite in-memory
        # uses a single persistent connection on the instance.
        self._persistent_conn_var: ContextVar[Any | None] = ContextVar(
            f"media_db_persistent_conn_{id(self)}",
            default=None,
        )
        self._persistent_conn = None
        # For SQLite in-memory databases, maintain a persistent connection so state persists
        if self.backend_type == BackendType.SQLITE and self.is_memory_db:
            # Use autocommit for consistency with pooled connections
            pc = sqlite3.connect(self.db_path_str, check_same_thread=False, isolation_level=None)
            try:
                pc.row_factory = sqlite3.Row
                self._apply_sqlite_connection_pragmas(pc)
            except sqlite3.Error:
                pass
            self._persistent_conn = pc
        # Add lock for media insertion to prevent race conditions in concurrent uploads
        self._media_insert_lock = threading.Lock()
        self._scope_cache: tuple[int | None, int | None] = (self.default_org_id, self.default_team_id)

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
            raise DatabaseError(f"Database initialization failed: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            # Catch any other unexpected errors during initialization
            pass
            logging.critical(f"FATAL: Unexpected error during DB Initialization for {self.db_path_str}: {e}", exc_info=True)
            # Attempt cleanup
            self.close_connection()
            # Re-raise as a DatabaseError
            raise DatabaseError(f"Unexpected database initialization error: {e}") from e  # noqa: TRY003
        finally:
            # Log completion status based on the flag
            if initialization_successful:
                logging.debug(f"Database initialization completed successfully for {self.db_path_str}")
            else:
                # This path indicates an exception was caught and raised above.
                # Logging here provides context that the __init__ block finished, albeit with failure.
                logging.error(f"Database initialization block finished for {self.db_path_str}, but failed.")

    def _resolve_scope_ids(self) -> tuple[int | None, int | None]:
        """Determine effective org/team IDs for the current execution context."""
        try:
            scope = get_scope()
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
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
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                parser = None

        backend_mode_env = (os.getenv("CONTENT_DB_MODE") or os.getenv("TLDW_CONTENT_DB_BACKEND") or "").strip().lower()
        forced_postgres = backend_mode_env in {"postgres", "postgresql"}

        if not forced_postgres and parser is not None:
            try:
                content_settings = load_content_db_settings(parser)
                forced_postgres = content_settings.backend_type == BackendType.POSTGRESQL
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                pass

        # In test contexts, honor explicit db_path to keep fixtures on SQLite.
        try:
            test_mode = (
                os.getenv("PYTEST_CURRENT_TEST") is not None
                or is_test_mode()
            )
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            test_mode = False
        if forced_postgres and test_mode and self.db_path_str and self.db_path_str != ":memory:":
            forced_postgres = False

        if forced_postgres:
            if parser is None:
                raise DatabaseError("PostgreSQL content backend requested but configuration could not be loaded")  # noqa: TRY003
            resolved_backend = get_content_backend(parser)
            if resolved_backend is None or resolved_backend.backend_type != BackendType.POSTGRESQL:
                raise DatabaseError("PostgreSQL content backend requested but could not be initialized")  # noqa: TRY003
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

        raise DatabaseError(  # noqa: TRY003
            "MediaDatabase backend could not be resolved. "
            "Pass an explicit db_path or configure the content backend."
        )

    # --- Backend Statement Preparation Helpers ---
    def _prepare_backend_statement(
        self,
        query: str,
        params: tuple | list | dict | None = None,
    ) -> tuple[str, tuple | dict | None]:
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
        params_list: list[tuple | list | dict],
    ) -> tuple[str, list[tuple | dict]]:
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
        clauses: list[str],
        params: list[Any],
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
        params: Any | None,
    ) -> tuple | dict | None:
        return normalise_params(params)

    def _convert_sqlite_placeholders_to_postgres(self, query: str) -> str:
        return convert_sqlite_placeholders_to_postgres(query)

    def _execute_with_connection(
        self,
        conn,
        query: str,
        params: tuple | list | dict | None = None,
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
                "Backend execute failed: {}... Error: {}",
                prepared_query[:200],
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Backend execute failed: {exc}") from exc  # noqa: TRY003

    def _executemany_with_connection(
        self,
        conn,
        query: str,
        params_list: list[tuple | list | dict],
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
                "Backend execute_many failed: {}... Error: {}",
                prepared_query[:200],
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Backend execute_many failed: {exc}") from exc  # noqa: TRY003

    def _fetchone_with_connection(
        self,
        conn,
        query: str,
        params: tuple | list | dict | None = None,
    ) -> dict[str, Any] | None:
        cursor = self._execute_with_connection(conn, query, params)
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def _fetchall_with_connection(
        self,
        conn,
        query: str,
        params: tuple | list | dict | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self._execute_with_connection(conn, query, params)
        rows = cursor.fetchall() or []
        return [dict(r) for r in rows]

    def _get_txn_conn(self):
        return self._txn_conn_var.get()

    def _set_txn_conn(self, conn) -> None:
        self._txn_conn_var.set(conn)

    def _get_tx_depth(self) -> int:
        return int(self._tx_depth_var.get() or 0)

    def _set_tx_depth(self, depth: int) -> None:
        self._tx_depth_var.set(int(depth))

    def _inc_tx_depth(self) -> int:
        depth = self._get_tx_depth() + 1
        self._set_tx_depth(depth)
        return depth

    def _dec_tx_depth(self) -> int:
        depth = self._get_tx_depth() - 1
        if depth < 0:
            depth = 0
        self._set_tx_depth(depth)
        return depth

    def _get_persistent_conn(self):
        if self.backend_type == BackendType.POSTGRESQL:
            return self._persistent_conn_var.get()
        return self._persistent_conn

    def _set_persistent_conn(self, conn) -> None:
        if self.backend_type == BackendType.POSTGRESQL:
            self._persistent_conn_var.set(conn)
        else:
            self._persistent_conn = conn

    # --- Connection Management ---
    def get_connection(self):
        """Compatibility shim to return a usable connection.

        - Inside transactions returns the transaction-scoped connection.
        - For SQLite, returns a pooled thread-local connection.
        - For PostgreSQL, returns a persistent connection grabbed from the pool
          on first use (released by close_connection()).
        """
        txn_conn = self._get_txn_conn()
        if txn_conn is not None:
            return txn_conn
        if self.backend_type == BackendType.SQLITE:
            if self.is_memory_db and self._persistent_conn is not None:
                return self._persistent_conn
            return self.backend.get_pool().get_connection()
        # PostgreSQL: reuse a single persistent connection outside transactions
        conn = self._get_persistent_conn()
        if conn is None:
            conn = self.backend.get_pool().get_connection()
            self._set_persistent_conn(conn)
        with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
            self.backend.apply_scope(conn)
        return conn

    def close_connection(self):
        """Release persistent non-transaction connection if present."""
        if self._get_txn_conn() is not None:
            return
        try:
            conn = self._get_persistent_conn()
            if conn is not None:
                self.backend.get_pool().return_connection(conn)
        finally:
            self._set_persistent_conn(None)

    def release_context_connection(self) -> None:
        """Return context-scoped Postgres connection to the pool (no-op for SQLite)."""
        if self.backend_type != BackendType.POSTGRESQL:
            return
        if self._get_txn_conn() is not None:
            return
        try:
            conn = self._get_persistent_conn()
            if conn is not None:
                self.backend.get_pool().return_connection(conn)
        finally:
            self._set_persistent_conn(None)

    def _ensure_sqlite_backend(self) -> None:
        if self.backend_type != BackendType.SQLITE:
            return

    def _apply_sqlite_connection_pragmas(self, conn: sqlite3.Connection) -> None:
        if self.backend_type != BackendType.SQLITE:
            return
        try:
            cfg = getattr(self.backend, "config", None)
            wal_mode = True
            foreign_keys = True
            if cfg is not None:
                wal_mode = bool(getattr(cfg, "sqlite_wal_mode", True))
                foreign_keys = bool(getattr(cfg, "sqlite_foreign_keys", True))

            configure_sqlite_connection(
                conn,
                use_wal=wal_mode,
                synchronous="NORMAL" if wal_mode else None,
                foreign_keys=foreign_keys,
                busy_timeout_ms=10000,
                cache_size=-2000,
            )
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            pass

    # --- Query Execution (Unchanged, catches IntegrityError from validation triggers) ---
    def execute_query(
        self,
        query: str,
        params: tuple | list | dict | None = None,
        *,
        commit: bool = False,
        connection: Any | None = None,
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

        eff_conn = connection or self._get_txn_conn()

        if self.backend_type == BackendType.SQLITE:
            try:
                if eff_conn is None and not self.is_memory_db:
                    eph = sqlite3.connect(self.db_path_str, check_same_thread=False)
                    cur = None
                    try:
                        eph.row_factory = sqlite3.Row
                        self._apply_sqlite_connection_pragmas(eph)
                        cur = eph.cursor()
                        cur.execute(prepared_query, prepared_params or ())
                        upper = prepared_query.strip().upper()
                        is_select = upper.startswith("SELECT")
                        has_returning = " RETURNING " in upper
                        rows = []
                        if is_select or has_returning:
                            rows = [dict(r) for r in cur.fetchall()]
                        # Auto-commit DML/DDL when using ephemeral connection
                        if commit or not is_select:
                            with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                                eph.commit()
                        result = QueryResult(rows=rows, rowcount=cur.rowcount, lastrowid=cur.lastrowid, description=cur.description)
                        return BackendCursorAdapter(result)
                    finally:
                        close_sqlite_ephemeral(cur, eph)
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
                    logging.exception("Sync Validation Failed")
                    raise
                logging.error("Integrity error executing query: {}", e, exc_info=True)
                raise DatabaseError(f"Integrity constraint violation: {e}") from e  # noqa: TRY003
            except sqlite3.Error as e:
                logging.error("SQLite query failed: {}", e, exc_info=True)
                raise DatabaseError(f"Query execution failed: {e}") from e  # noqa: TRY003

        try:
            if eff_conn is None:
                result = self.backend.execute(prepared_query, prepared_params)
            else:
                result = self.backend.execute(prepared_query, prepared_params, connection=eff_conn)
                if commit:
                    try:
                        eff_conn.commit()
                    except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
                        raise DatabaseError(f"Backend commit failed: {exc}") from exc  # noqa: TRY003
            return BackendCursorAdapter(result)
        except BackendDatabaseError as exc:
            logging.error("Backend query failed: {}", exc, exc_info=True)
            raise DatabaseError(f"Backend query execution failed: {exc}") from exc  # noqa: TRY003

    def execute_many(
        self,
        query: str,
        params_list: list[tuple | list | dict],
        *,
        commit: bool = False,
        connection: Any | None = None,
    ) -> object | None:
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
            raise TypeError("params_list must be a list of parameter iterables for execute_many().")  # noqa: TRY003
        if not params_list:
            logging.debug("execute_many received empty params_list; nothing to execute.")
            return None

        prepared_query, prepared_params_list = self._prepare_backend_many_statement(query, params_list)

        eff_conn = connection or self._get_txn_conn()

        if self.backend_type == BackendType.SQLITE:
            try:
                if eff_conn is None and not self.is_memory_db:
                    eph = sqlite3.connect(self.db_path_str, check_same_thread=False)
                    cur = None
                    try:
                        eph.row_factory = sqlite3.Row
                        self._apply_sqlite_connection_pragmas(eph)
                        cur = eph.cursor()
                        cur.executemany(prepared_query, prepared_params_list)
                        # executemany implies DML; commit when using ephemeral connection
                        with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                            eph.commit()
                        result = QueryResult(rows=[], rowcount=cur.rowcount, lastrowid=cur.lastrowid, description=cur.description)
                        return BackendCursorAdapter(result)
                    finally:
                        close_sqlite_ephemeral(cur, eph)
                else:
                    conn_use = eff_conn or self.get_connection()
                    cur = conn_use.cursor()
                    cur.executemany(prepared_query, prepared_params_list)
                    if commit and conn_use:
                        conn_use.commit()
                    result = QueryResult(rows=[], rowcount=cur.rowcount, lastrowid=cur.lastrowid, description=cur.description)
                    return BackendCursorAdapter(result)
            except sqlite3.IntegrityError as e:
                logging.error("Integrity error during execute_many: {}", e, exc_info=True)
                raise DatabaseError(f"Integrity constraint violation during batch: {e}") from e  # noqa: TRY003
            except sqlite3.Error as e:
                logging.error("SQLite execute_many failed: {}", e, exc_info=True)
                raise DatabaseError(f"Execute Many failed: {e}") from e  # noqa: TRY003
            except TypeError as te:
                logging.error("TypeError during execute_many: {}", te, exc_info=True)
                raise TypeError(f"Parameter list format error: {te}") from te  # noqa: TRY003

        try:
            if eff_conn is None:
                result = self.backend.execute_many(prepared_query, prepared_params_list)
            else:
                result = self.backend.execute_many(prepared_query, prepared_params_list, connection=eff_conn)
                if commit:
                    try:
                        eff_conn.commit()
                    except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
                        raise DatabaseError(f"Backend batch commit failed: {exc}") from exc  # noqa: TRY003
            return BackendCursorAdapter(result)
        except BackendDatabaseError as exc:
            logging.error("Backend execute_many failed: {}", exc, exc_info=True)
            raise DatabaseError(f"Backend execute_many failed: {exc}") from exc  # noqa: TRY003

    # -------------------------
    # VisualDocuments helpers
    # -------------------------
    def insert_visual_document(
        self,
        media_id: int,
        *,
        caption: str | None = None,
        ocr_text: str | None = None,
        tags: str | None = None,
        location: str | None = None,
        page_number: int | None = None,
        frame_index: int | None = None,
        timestamp_seconds: float | None = None,
        thumbnail_path: str | None = None,
        extra_metadata: str | None = None,
    ) -> str:
        """
        Insert a new VisualDocuments row for a given media item.

        Returns the generated uuid for the inserted visual document.
        """
        conn = self.get_connection()
        new_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        data: dict[str, Any] = {
            "media_id": media_id,
            "location": location,
            "page_number": page_number,
            "frame_index": frame_index,
            "timestamp_seconds": timestamp_seconds,
            "caption": caption,
            "ocr_text": ocr_text,
            "tags": tags,
            "thumbnail_path": thumbnail_path,
            "extra_metadata": extra_metadata,
            "uuid": new_uuid,
            "created_at": now,
            "last_modified": now,
            "version": 1,
            "client_id": self.client_id,
            "deleted": 0,
            "prev_version": None,
            "merge_parent_uuid": None,
        }
        placeholders = ", ".join([f":{k}" for k in data])
        columns = ", ".join(data.keys())
        sql = f"INSERT INTO VisualDocuments ({columns}) VALUES ({placeholders})"  # nosec B608
        try:
            self._execute_with_connection(conn, sql, data)
            with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                self._log_sync_event(
                    conn,
                    "VisualDocuments",
                    new_uuid,
                    "create",
                    1,
                    json.dumps(
                        {
                            "media_id": media_id,
                            "caption": caption or "",
                            "ocr_text": ocr_text or "",
                        }
                    ),
                )
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            raise DatabaseError(f"Failed to insert VisualDocument: {exc}") from exc  # noqa: TRY003
        return new_uuid

    def list_visual_documents_for_media(
        self,
        media_id: int,
        *,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Return all VisualDocuments for a media item, ordered by page/frame/timestamp.
        """
        conn = self.get_connection()
        clauses: list[str] = ["media_id = :media_id"]
        params: dict[str, Any] = {"media_id": media_id}
        if not include_deleted:
            clauses.append("deleted = 0")
        where_sql = " AND ".join(clauses)
        sql = (
            "SELECT * FROM VisualDocuments "  # nosec B608
            f"WHERE {where_sql} "
            "ORDER BY "
            "COALESCE(page_number, 0), "
            "COALESCE(frame_index, 0), "
            "COALESCE(timestamp_seconds, 0.0), "
            "id"
        )
        try:
            return self._fetchall_with_connection(conn, sql, params)
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            raise DatabaseError(f"Failed to list VisualDocuments for media_id={media_id}: {exc}") from exc  # noqa: TRY003

    def soft_delete_visual_documents_for_media(
        self,
        media_id: int,
        *,
        hard_delete: bool = False,
    ) -> None:
        """
        Soft-delete (or hard-delete when requested) all VisualDocuments for a media item.

        Soft delete marks rows as deleted=1 and logs sync events; hard delete removes rows.
        """
        conn = self.get_connection()
        try:
            if hard_delete:
                self._execute_with_connection(
                    conn,
                    "DELETE FROM VisualDocuments WHERE media_id = :media_id",
                    {"media_id": media_id},
                )
                with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                    self._log_sync_event(
                        conn,
                        "VisualDocuments",
                        f"media:{media_id}",
                        "delete",
                        1,
                        json.dumps({"media_id": media_id, "mode": "hard"}),
                    )
            else:
                rows = self._fetchall_with_connection(
                    conn,
                    "SELECT uuid, version FROM VisualDocuments WHERE media_id = :media_id AND deleted = 0",
                    {"media_id": media_id},
                )
                for row in rows:
                    v_uuid = row.get("uuid")
                    current_version = int(row.get("version") or 1)
                    new_version = current_version + 1
                    self._execute_with_connection(
                        conn,
                        "UPDATE VisualDocuments SET deleted = 1, version = :version WHERE uuid = :uuid",
                        {"uuid": v_uuid, "version": new_version},
                    )
                    with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                        self._log_sync_event(
                            conn,
                            "VisualDocuments",
                            v_uuid,
                            "delete",
                            new_version,
                            json.dumps({"media_id": media_id}),
                        )
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            raise DatabaseError(f"Failed to delete VisualDocuments for media_id={media_id}: {exc}") from exc  # noqa: TRY003

    # -------------------------
    # MediaFiles CRUD helpers
    # -------------------------

    def insert_media_file(
        self,
        media_id: int,
        file_type: str,
        storage_path: str,
        *,
        original_filename: str | None = None,
        file_size: int | None = None,
        mime_type: str | None = None,
        checksum: str | None = None,
    ) -> str:
        return MediaFilesRepository.from_legacy_db(self).insert(
            media_id=media_id,
            file_type=file_type,
            storage_path=storage_path,
            original_filename=original_filename,
            file_size=file_size,
            mime_type=mime_type,
            checksum=checksum,
        )

    def get_media_file(
        self,
        media_id: int,
        file_type: str = "original",
        *,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None:
        return MediaFilesRepository.from_legacy_db(self).get_for_media(
            media_id=media_id,
            file_type=file_type,
            include_deleted=include_deleted,
        )

    def get_media_files(
        self,
        media_id: int,
        *,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        return MediaFilesRepository.from_legacy_db(self).list_for_media(
            media_id=media_id,
            include_deleted=include_deleted,
        )

    def has_original_file(self, media_id: int) -> bool:
        return MediaFilesRepository.from_legacy_db(self).has_original_file(media_id)

    def soft_delete_media_file(
        self,
        file_id: int,
    ) -> None:
        MediaFilesRepository.from_legacy_db(self).soft_delete(file_id)

    def soft_delete_media_files_for_media(
        self,
        media_id: int,
        *,
        hard_delete: bool = False,
    ) -> None:
        MediaFilesRepository.from_legacy_db(self).soft_delete_for_media(
            media_id=media_id,
            hard_delete=hard_delete,
        )

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
            existed = False
            try:
                cur = self.execute_query(
                    "SELECT 1 AS exists_flag FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'unvectorized_chunks_fts'"
                )
                existed = cur.fetchone() is not None
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                existed = False
            ddl = (
                "CREATE VIRTUAL TABLE IF NOT EXISTS unvectorized_chunks_fts "
                "USING fts5(\n"
                "  chunk_text,\n"
                "  content='UnvectorizedMediaChunks',\n"
                "  content_rowid='id'\n"
                ")"
            )
            self.execute_query(ddl, commit=True)
            if not existed:
                try:
                    self.execute_query(
                        "INSERT INTO unvectorized_chunks_fts(unvectorized_chunks_fts) VALUES('rebuild')",
                        commit=True,
                    )
                except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
                    logging.debug(f"ensure_chunk_fts rebuild skipped or failed: {e}")
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
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
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                # Table missing - try to create and continue
                pass
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
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
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
            outermost = self._get_txn_conn() is None
            if outermost:
                # Dedicated connection for this transaction
                conn = self._persistent_conn or self.backend.connect()
                with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                    conn.row_factory = sqlite3.Row
                try:
                    self._apply_sqlite_connection_pragmas(conn)
                except sqlite3.Error:
                    pass
            else:
                conn = self._get_txn_conn()

            self._inc_tx_depth()
            try:
                if outermost:
                    begin_immediate_if_needed(conn)
                    self._set_txn_conn(conn)
                    logging.debug("Started SQLite transaction.")
                yield conn
                if outermost:
                    conn.commit()
                    logging.debug("Committed SQLite transaction.")
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                logging.exception("SQLite transaction failed, rolling back")
                if outermost:
                    with suppress(sqlite3.Error):
                        conn.rollback()
                raise
            finally:
                self._dec_tx_depth()
                if outermost:
                    self._set_txn_conn(None)
                    if self._persistent_conn is None:
                        with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                            conn.close()
            return

        # PostgreSQL and others: reuse a single connection for nested transactions
        manages_backend_conn = self._get_txn_conn() is None
        conn = self.backend.get_pool().get_connection() if manages_backend_conn else self._get_txn_conn()

        manages_backend_tx = self._get_tx_depth() == 0
        self._inc_tx_depth()
        ctx = self.backend.transaction(conn) if manages_backend_tx else nullcontext(conn)
        try:
            with ctx as inner_conn:
                self._set_txn_conn(inner_conn)
                yield inner_conn
        finally:
            depth = self._dec_tx_depth()
            if depth == 0:
                self._set_txn_conn(None)
            if manages_backend_conn:
                with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                    self.backend.get_pool().return_connection(conn)

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
                raise DatabaseError(f"Could not determine database schema version: {e}") from e  # noqa: TRY003

    @property
    def _SCHEMA_UPDATE_VERSION_SQL_V1(self):
        return (
            "DELETE FROM schema_version WHERE version <> 0;\n"  # nosec B608
            f"UPDATE schema_version SET version = {self._CURRENT_SCHEMA_VERSION} WHERE version = 0;"
        )

    def _apply_schema_v1_sqlite(self, conn: sqlite3.Connection):
        """Applies the full Version 1 schema, ensuring version update is part of the main script."""
        logging.info(f"Applying initial schema (Version 1) to DB: {self.db_path_str}...")
        try:
            # --- Combine all schema DDL into a single executescript ---
            # executescript wraps the script in a transaction on this connection,
            # so keep everything together to avoid partial application.
            full_schema_script = f"""
                {self._TABLES_SQL_V1}
                {self._INDICES_SQL_V1}
                {self._TRIGGERS_SQL_V1}
                {self._SCHEMA_UPDATE_VERSION_SQL_V1}
                {self._CLAIMS_TABLE_SQL}
                {self._MEDIA_FILES_TABLE_SQL}
                {self._TTS_HISTORY_TABLE_SQL}
                {self._DATA_TABLES_SQL}
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

                CREATE TABLE IF NOT EXISTS collection_tags (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    UNIQUE (user_id, name)
                );

                CREATE TABLE IF NOT EXISTS content_items (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    origin_type TEXT,
                    origin_id INTEGER,
                    url TEXT,
                    canonical_url TEXT,
                    domain TEXT,
                    title TEXT,
                    summary TEXT,
                    notes TEXT,
                    content_hash TEXT,
                    word_count INTEGER,
                    published_at TEXT,
                    status TEXT,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT,
                    media_id INTEGER,
                    job_id INTEGER,
                    run_id INTEGER,
                    source_id INTEGER,
                    read_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_canonical ON content_items(user_id, canonical_url) WHERE canonical_url IS NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_hash ON content_items(user_id, content_hash) WHERE content_hash IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_content_items_user_updated ON content_items(user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_content_items_user_domain ON content_items(user_id, domain);
                CREATE INDEX IF NOT EXISTS idx_content_items_job ON content_items(job_id);
                CREATE INDEX IF NOT EXISTS idx_content_items_run ON content_items(run_id);

                CREATE TABLE IF NOT EXISTS content_item_tags (
                    item_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    UNIQUE (item_id, tag_id)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS content_items_fts USING fts5(
                    title,
                    summary,
                    metadata,
                    content=''
                );
            """  # Note the added UPDATE statement

            logging.debug("[Schema V1] Applying full schema script...")
            conn.executescript(full_schema_script)
            logging.debug("[Schema V1] Full schema script executed.")
            # Ensure stage-1 email-native schema is present on fresh SQLite DBs.
            self._ensure_sqlite_email_schema(conn)

            # --- Validation step (optional but good) - Check Media table ---
            try:
                cursor = conn.execute("PRAGMA table_info(Media)")
                columns = {row['name'] for row in cursor.fetchall()}
                # Update this set to match ALL columns defined in _TABLES_SQL_V1.Media
                expected_cols = {
                    'id',
                    'url',
                    'title',
                    'type',
                    'content',
                    'author',
                    'ingestion_date',
                    'transcription_model',
                    'is_trash',
                    'trash_date',
                    'vector_embedding',
                    'chunking_status',
                    'vector_processing',
                    'content_hash',
                    'source_hash',
                    'uuid',
                    'last_modified',
                    'version',
                    'org_id',
                    'team_id',
                    'visibility',
                    'owner_user_id',
                    'client_id',
                    'deleted',
                    'prev_version',
                    'merge_parent_uuid',
                }
                if not expected_cols.issubset(columns):
                    missing_cols = expected_cols - columns
                    raise SchemaError(f"Validation Error: Media table is missing columns after creation: {missing_cols}")  # noqa: TRY003, TRY301
                logging.debug("[Schema V1] Media table structure validated successfully.")
            except (sqlite3.Error, SchemaError) as val_err:
                logging.error(f"[Schema V1] Validation failed after table creation: {val_err}", exc_info=True)
                raise

            # --- Explicitly check version after script ---
            cursor_check = conn.execute("SELECT version FROM schema_version LIMIT 1")
            version_in_db = cursor_check.fetchone()
            if not version_in_db or version_in_db['version'] != self._CURRENT_SCHEMA_VERSION:
                logging.error(
                    "[Schema V1] Version check failed after schema script. Found: {}",
                    version_in_db['version'] if version_in_db else 'None',
                )
                raise SchemaError("Schema version update did not take effect after schema script.")  # noqa: TRY003
            logging.debug(
                "[Schema V1] Version check confirmed version is {}.",
                self._CURRENT_SCHEMA_VERSION,
            )

            logging.info(
                "[Schema V1] Core Schema V1 (incl. version update) applied successfully for DB: {}.",
                self.db_path_str,
            )

            # --- Create FTS Tables Separately (Remains the same) ---
            try:
                logging.debug("[Schema V1] Applying FTS Tables...")
                self._ensure_fts_structures(conn)
                logging.info("[Schema V1] FTS Tables created successfully.")
            except (sqlite3.Error, DatabaseError) as fts_err:
                logging.error(f"[Schema V1] Failed to create FTS tables: {fts_err}", exc_info=True)

        except sqlite3.Error as e:
            logging.error(f"[Schema V1] Application failed during schema script: {e}", exc_info=True)
            raise DatabaseError(f"DB schema V1 setup failed: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logging.error(f"[Schema V1] Unexpected error during schema V1 application: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error applying schema V1: {e}") from e  # noqa: TRY003

    def _convert_sqlite_sql_to_postgres_statements(self, sql: str) -> list[str]:
        """Convert SQLite-oriented SQL blob into Postgres-compatible statements."""

        statements: list[str] = []
        buffer: list[str] = []
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

    def _transform_sqlite_statement_to_postgres(self, statement: str) -> str | None:
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
            stmt = stmt[:-1] + ' ON CONFLICT DO NOTHING;' if stmt.endswith(';') else stmt + ' ON CONFLICT DO NOTHING;'

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
        # Add MediaFiles table for original file storage
        table_statements += self._convert_sqlite_sql_to_postgres_statements(self._MEDIA_FILES_TABLE_SQL)
        # Add TTS history table
        table_statements += self._convert_sqlite_sql_to_postgres_statements(self._TTS_HISTORY_TABLE_SQL)
        # Add Data Tables storage for generated tables
        table_statements += self._convert_sqlite_sql_to_postgres_statements(self._DATA_TABLES_SQL)

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
                raise SchemaError(f"Postgres schema init missing table: {t}")  # noqa: TRY003

        index_statements = self._convert_sqlite_sql_to_postgres_statements(self._INDICES_SQL_V1)
        for stmt in index_statements:
            logger.debug(f"Applying Postgres index DDL: {stmt[:120]}...")
            self.backend.execute(stmt, connection=conn)

        # Ensure stage-1 email-native schema is present on fresh PostgreSQL DBs.
        self._ensure_postgres_email_schema(conn)

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
        ensure_media_schema(self)

    def _initialize_schema_sqlite(self):
        conn = self.get_connection()
        try:
            current_db_version = self._get_db_version(conn)
            target_version = self._CURRENT_SCHEMA_VERSION

            logging.info(f"Checking DB schema. Current version: {current_db_version}. Code supports: {target_version}")

            if current_db_version == target_version:
                logging.debug("Database schema is up to date.")
                # Optionally ensure FTS tables and newer helper structures exist
                try:
                    # Ensure Claims table exists for older DBs without bumping version
                    conn.executescript(self._CLAIMS_TABLE_SQL)
                    # Ensure MediaFiles table exists for original file storage
                    conn.executescript(self._MEDIA_FILES_TABLE_SQL)
                    # Ensure TTS history table exists
                    conn.executescript(self._TTS_HISTORY_TABLE_SQL)
                    # Ensure Data Tables schema exists for generated tables
                    self._ensure_sqlite_data_tables(conn)
                    ensure_sqlite_fts_structures(self, conn)
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

                        CREATE TABLE IF NOT EXISTS collection_tags (
                            id INTEGER PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            UNIQUE (user_id, name)
                        );

                        CREATE TABLE IF NOT EXISTS content_items (
                            id INTEGER PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            origin TEXT NOT NULL,
                            origin_type TEXT,
                            origin_id INTEGER,
                            url TEXT,
                            canonical_url TEXT,
                            domain TEXT,
                            title TEXT,
                            summary TEXT,
                            notes TEXT,
                            content_hash TEXT,
                            word_count INTEGER,
                            published_at TEXT,
                            status TEXT,
                            favorite INTEGER NOT NULL DEFAULT 0,
                            metadata_json TEXT,
                            media_id INTEGER,
                            job_id INTEGER,
                            run_id INTEGER,
                            source_id INTEGER,
                            read_at TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_canonical ON content_items(user_id, canonical_url) WHERE canonical_url IS NOT NULL;
                        CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_hash ON content_items(user_id, content_hash) WHERE content_hash IS NOT NULL;
                        CREATE INDEX IF NOT EXISTS idx_content_items_user_updated ON content_items(user_id, updated_at DESC);
                        CREATE INDEX IF NOT EXISTS idx_content_items_user_domain ON content_items(user_id, domain);
                        CREATE INDEX IF NOT EXISTS idx_content_items_job ON content_items(job_id);
                        CREATE INDEX IF NOT EXISTS idx_content_items_run ON content_items(run_id);

                        CREATE TABLE IF NOT EXISTS content_item_tags (
                            item_id INTEGER NOT NULL,
                            tag_id INTEGER NOT NULL,
                            UNIQUE (item_id, tag_id)
                        );

                        CREATE VIRTUAL TABLE IF NOT EXISTS content_items_fts USING fts5(
                            title,
                            summary,
                            metadata,
                            content=''
                        );
                        """
                    )
                    # Ensure visibility/owner columns and indexes exist on upgraded DBs
                    self._ensure_sqlite_visibility_columns(conn)
                    self._ensure_sqlite_source_hash_column(conn)
                    self._ensure_sqlite_claims_extensions(conn)
                    self._ensure_sqlite_email_schema(conn)
                    logging.debug("Verified FTS tables and visibility columns exist.")
                except (sqlite3.Error, DatabaseError) as fts_err:
                    logging.warning(f"Could not verify/create FTS tables on already correct schema version: {fts_err}")
                return

            if current_db_version > target_version:
                raise SchemaError(f"Database schema version ({current_db_version}) is newer than supported by code ({target_version}).")  # noqa: TRY003, TRY301

            # --- Apply Migrations ---
            if current_db_version == 0:
                # Fresh database, apply base schema directly at current version
                apply_sqlite_core_media_schema(self, conn)
                # Verify version update
                final_db_version = self._get_db_version(conn)
                if final_db_version != target_version:
                    raise SchemaError(f"Schema applied, but final DB version is {final_db_version}, expected {target_version}.")  # noqa: TRY003, TRY301
                logger.info(f"Database schema initialized to version {target_version}.")

            elif current_db_version < target_version:
                # Use the migration system for existing databases.
                # Special-case in-memory DBs: treat them as fresh and apply base schema,
                # since migration helpers open separate connections that won't share :memory: state.
                try:
                    if self.is_memory_db:
                        apply_sqlite_core_media_schema(self, conn)
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
                            elif status == "no_migrations":
                                migrations_dir_used = (
                                    (result or {}).get("migrations_dir")
                                    or getattr(migrator, "migrations_dir", None)
                                    or migrations_dir
                                )
                                available_versions = (result or {}).get("available_versions") or []
                                missing_versions = (result or {}).get("missing_versions") or []
                                raise SchemaError(  # noqa: TRY003
                                    "No migration scripts available to upgrade database schema "
                                    f"from version {current_db_version} to {target_version}. "
                                    f"migrations_dir={migrations_dir_used}, "
                                    f"discovered_versions={available_versions}, "
                                    f"missing_versions={missing_versions}."
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
                                raise SchemaError(  # noqa: TRY003
                                    "Database schema did not reach expected version after migration run "
                                    f"(status={status}, current={final_db_version}, expected={target_version})."
                                )
                            # Ensure FTS tables exist
                            ensure_sqlite_fts_structures(self, conn)
                            # Ensure Data Tables schema exists for upgraded DBs
                            self._ensure_sqlite_data_tables(conn)
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

                                CREATE TABLE IF NOT EXISTS collection_tags (
                                    id INTEGER PRIMARY KEY,
                                    user_id TEXT NOT NULL,
                                    name TEXT NOT NULL,
                                    UNIQUE (user_id, name)
                                );

                                CREATE TABLE IF NOT EXISTS content_items (
                                    id INTEGER PRIMARY KEY,
                                    user_id TEXT NOT NULL,
                                    origin TEXT NOT NULL,
                                    origin_type TEXT,
                                    origin_id INTEGER,
                                    url TEXT,
                                    canonical_url TEXT,
                                    domain TEXT,
                                    title TEXT,
                                    summary TEXT,
                                    notes TEXT,
                                    content_hash TEXT,
                                    word_count INTEGER,
                                    published_at TEXT,
                                    status TEXT,
                                    favorite INTEGER NOT NULL DEFAULT 0,
                                    metadata_json TEXT,
                                    media_id INTEGER,
                                    job_id INTEGER,
                                    run_id INTEGER,
                                    source_id INTEGER,
                                    read_at TEXT,
                                    created_at TEXT NOT NULL,
                                    updated_at TEXT NOT NULL
                                );
                                CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_canonical ON content_items(user_id, canonical_url) WHERE canonical_url IS NOT NULL;
                                CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_hash ON content_items(user_id, content_hash) WHERE content_hash IS NOT NULL;
                                CREATE INDEX IF NOT EXISTS idx_content_items_user_updated ON content_items(user_id, updated_at DESC);
                                CREATE INDEX IF NOT EXISTS idx_content_items_user_domain ON content_items(user_id, domain);
                                CREATE INDEX IF NOT EXISTS idx_content_items_job ON content_items(job_id);
                                CREATE INDEX IF NOT EXISTS idx_content_items_run ON content_items(run_id);

                                CREATE TABLE IF NOT EXISTS content_item_tags (
                                    item_id INTEGER NOT NULL,
                                    tag_id INTEGER NOT NULL,
                                    UNIQUE (item_id, tag_id)
                                );

                                CREATE VIRTUAL TABLE IF NOT EXISTS content_items_fts USING fts5(
                                    title,
                                    summary,
                                    metadata,
                                    content=''
                                );
                                """
                            )
                            # Ensure visibility/owner columns and indexes exist on upgraded DBs
                            self._ensure_sqlite_visibility_columns(conn)
                            self._ensure_sqlite_source_hash_column(conn)
                            self._ensure_sqlite_claims_extensions(conn)
                            self._ensure_sqlite_email_schema(conn)
                        else:
                            raise SchemaError(f"Migration failed: {result}")  # noqa: TRY003

                except MigrationError as e:
                    raise SchemaError(f"Database migration failed: {e}") from e  # noqa: TRY003

            else:
                raise SchemaError(f"Migration needed from version {current_db_version} to {target_version}, but no migration path is defined.")  # noqa: TRY003, TRY301

        except (DatabaseError, SchemaError, sqlite3.Error) as e:
            logger.error(f"Schema initialization/migration failed: {e}", exc_info=True)
            raise DatabaseError(f"Schema initialization failed: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error during schema initialization: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error applying schema: {e}") from e  # noqa: TRY003

    def _initialize_schema_postgres(self):
        target_version = self._CURRENT_SCHEMA_VERSION
        backend = self.backend

        with backend.transaction() as conn:
            schema_exists = backend.table_exists('schema_version', connection=conn)

            if not schema_exists:
                apply_postgres_core_media_schema(self, conn)
                ensure_postgres_fts(self, conn)
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
                    backend.execute(
                        (
                            "CREATE TABLE IF NOT EXISTS collection_tags ("
                            "id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, "
                            "UNIQUE (user_id, name))"
                        ),
                        connection=conn,
                    )
                    backend.execute(
                        (
                            "CREATE TABLE IF NOT EXISTS content_items ("
                            "id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, origin TEXT NOT NULL, origin_type TEXT, "
                            "origin_id BIGINT, url TEXT, canonical_url TEXT, domain TEXT, title TEXT, summary TEXT, notes TEXT, "
                            "content_hash TEXT, word_count INTEGER, published_at TEXT, status TEXT, favorite INTEGER NOT NULL DEFAULT 0, "
                            "metadata_json TEXT, media_id BIGINT, job_id BIGINT, run_id BIGINT, source_id BIGINT, read_at TEXT, "
                            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
                        ),
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_canonical "
                        "ON content_items(user_id, canonical_url) WHERE canonical_url IS NOT NULL",
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_hash "
                        "ON content_items(user_id, content_hash) WHERE content_hash IS NOT NULL",
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_content_items_user_updated "
                        "ON content_items(user_id, updated_at DESC)",
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_content_items_user_domain "
                        "ON content_items(user_id, domain)",
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_content_items_job "
                        "ON content_items(job_id)",
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_content_items_run "
                        "ON content_items(run_id)",
                        connection=conn,
                    )
                    backend.execute(
                        (
                            "CREATE TABLE IF NOT EXISTS content_item_tags ("
                            "item_id BIGINT NOT NULL, tag_id BIGINT NOT NULL, "
                            "UNIQUE (item_id, tag_id))"
                        ),
                        connection=conn,
                    )
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    pass
                self._ensure_postgres_tts_history(conn)
                self._ensure_postgres_data_tables(conn)
                self._ensure_postgres_source_hash_column(conn)
                self._ensure_postgres_claims_extensions(conn)
                self._ensure_postgres_email_schema(conn)
                self._sync_postgres_sequences(conn)
                ensure_postgres_policies(self, conn)
                return

            result = backend.execute("SELECT version FROM schema_version LIMIT 1", connection=conn)
            current_version_raw = result.scalar if result else None
            current_version = int(current_version_raw or 0)

            if current_version > target_version:
                raise SchemaError(  # noqa: TRY003
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
                    "Postgres schema_version exists but base tables missing: {}. Applying base schema.", missing
                )
                apply_postgres_core_media_schema(self, conn)
                current_version = target_version  # base schema applies current version
                ensure_postgres_fts(self, conn)
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
                    backend.execute(
                        (
                            "CREATE TABLE IF NOT EXISTS collection_tags ("
                            "id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, "
                            "UNIQUE (user_id, name))"
                        ),
                        connection=conn,
                    )
                    backend.execute(
                        (
                            "CREATE TABLE IF NOT EXISTS content_items ("
                            "id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, origin TEXT NOT NULL, origin_type TEXT, "
                            "origin_id BIGINT, url TEXT, canonical_url TEXT, domain TEXT, title TEXT, summary TEXT, notes TEXT, "
                            "content_hash TEXT, word_count INTEGER, published_at TEXT, status TEXT, favorite INTEGER NOT NULL DEFAULT 0, "
                            "metadata_json TEXT, media_id BIGINT, job_id BIGINT, run_id BIGINT, source_id BIGINT, read_at TEXT, "
                            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
                        ),
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_canonical "
                        "ON content_items(user_id, canonical_url) WHERE canonical_url IS NOT NULL",
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_hash "
                        "ON content_items(user_id, content_hash) WHERE content_hash IS NOT NULL",
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_content_items_user_updated "
                        "ON content_items(user_id, updated_at DESC)",
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_content_items_user_domain "
                        "ON content_items(user_id, domain)",
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_content_items_job "
                        "ON content_items(job_id)",
                        connection=conn,
                    )
                    backend.execute(
                        "CREATE INDEX IF NOT EXISTS idx_content_items_run "
                        "ON content_items(run_id)",
                        connection=conn,
                    )
                    backend.execute(
                        (
                            "CREATE TABLE IF NOT EXISTS content_item_tags ("
                            "item_id BIGINT NOT NULL, tag_id BIGINT NOT NULL, "
                            "UNIQUE (item_id, tag_id))"
                        ),
                        connection=conn,
                    )
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    pass
                self._ensure_postgres_data_tables(conn)
                self._ensure_postgres_source_hash_column(conn)
                self._ensure_postgres_claims_extensions(conn)
                self._ensure_postgres_email_schema(conn)
                self._sync_postgres_sequences(conn)
                ensure_postgres_policies(self, conn)
                return

            if current_version < target_version:
                run_postgres_migrations(self, conn, current_version, target_version)

            ensure_postgres_fts(self, conn)
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
                backend.execute(
                    (
                        "CREATE TABLE IF NOT EXISTS collection_tags ("
                        "id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, "
                        "UNIQUE (user_id, name))"
                    ),
                    connection=conn,
                )
                backend.execute(
                    (
                        "CREATE TABLE IF NOT EXISTS content_items ("
                        "id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, origin TEXT NOT NULL, origin_type TEXT, "
                        "origin_id BIGINT, url TEXT, canonical_url TEXT, domain TEXT, title TEXT, summary TEXT, notes TEXT, "
                        "content_hash TEXT, word_count INTEGER, published_at TEXT, status TEXT, favorite INTEGER NOT NULL DEFAULT 0, "
                        "metadata_json TEXT, media_id BIGINT, job_id BIGINT, run_id BIGINT, source_id BIGINT, read_at TEXT, "
                        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
                    ),
                    connection=conn,
                )
                backend.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_canonical "
                    "ON content_items(user_id, canonical_url) WHERE canonical_url IS NOT NULL",
                    connection=conn,
                )
                backend.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_hash "
                    "ON content_items(user_id, content_hash) WHERE content_hash IS NOT NULL",
                    connection=conn,
                )
                backend.execute(
                    "CREATE INDEX IF NOT EXISTS idx_content_items_user_updated "
                    "ON content_items(user_id, updated_at DESC)",
                    connection=conn,
                )
                backend.execute(
                    "CREATE INDEX IF NOT EXISTS idx_content_items_user_domain "
                    "ON content_items(user_id, domain)",
                    connection=conn,
                )
                backend.execute(
                    "CREATE INDEX IF NOT EXISTS idx_content_items_job "
                    "ON content_items(job_id)",
                    connection=conn,
                )
                backend.execute(
                    "CREATE INDEX IF NOT EXISTS idx_content_items_run "
                    "ON content_items(run_id)",
                    connection=conn,
                )
                backend.execute(
                    (
                        "CREATE TABLE IF NOT EXISTS content_item_tags ("
                        "item_id BIGINT NOT NULL, tag_id BIGINT NOT NULL, "
                        "UNIQUE (item_id, tag_id))"
                    ),
                    connection=conn,
                )
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                pass
            self._ensure_postgres_tts_history(conn)
            self._ensure_postgres_data_tables(conn)
            self._ensure_postgres_source_hash_column(conn)
            self._ensure_postgres_claims_extensions(conn)
            self._ensure_postgres_email_schema(conn)
            self._sync_postgres_sequences(conn)
            ensure_postgres_policies(self, conn)

    def _run_postgres_migrations(self, conn, current_version: int, target_version: int) -> None:
        """Execute sequential PostgreSQL migrations until the target version is reached."""

        migrations = get_postgres_migrations(self)
        applied_version = current_version

        for version in sorted(migrations.keys()):
            if applied_version < version <= target_version:
                migrations[version](conn)
                self._update_schema_version_postgres(conn, version)
                applied_version = version

        ensure_postgres_policies(self, conn)

        if applied_version < target_version:
            raise SchemaError(  # noqa: TRY003
                f"PostgreSQL migration path incomplete for MediaDatabase: reached {applied_version}, expected {target_version}."
            )

    def _get_postgres_migrations(self):
        """Return mapping of target version to migration callable."""

        return {
            5: self._postgres_migrate_to_v5,
            6: self._postgres_migrate_to_v6,
            7: self._postgres_migrate_to_v7,
            8: self._postgres_migrate_to_v8,
            9: self._postgres_migrate_to_v9,
            10: self._postgres_migrate_to_v10,
            11: self._postgres_migrate_to_v11,
            12: self._postgres_migrate_to_v12,
            13: self._postgres_migrate_to_v13,
            14: self._postgres_migrate_to_v14,
            15: self._postgres_migrate_to_v15,
            16: self._postgres_migrate_to_v16,
            17: self._postgres_migrate_to_v17,
            18: self._postgres_migrate_to_v18,
            19: self._postgres_migrate_to_v19,
            20: self._postgres_migrate_to_v20,
            21: self._postgres_migrate_to_v21,
            22: self._postgres_migrate_to_v22,
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

    def _postgres_migrate_to_v9(self, conn) -> None:
        """Add visibility and owner_user_id columns for content sharing (PostgreSQL)."""
        backend = self.backend
        ident = backend.escape_identifier

        # Add visibility column with check constraint
        backend.execute(
            f"ALTER TABLE {ident('media')} ADD COLUMN IF NOT EXISTS {ident('visibility')} TEXT DEFAULT 'personal'",
            connection=conn,
        )

        # Add check constraint for visibility values (idempotent)
        try:
            media_table_ident = ident("media")
            visibility_col_ident = ident("visibility")
            visibility_constraint_template = """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'chk_media_visibility'
                          AND conrelid = 'media'::regclass
                    ) THEN
                        ALTER TABLE {media_table}
                        ADD CONSTRAINT chk_media_visibility
                        CHECK ({visibility_col} IN ('personal', 'team', 'org'));
                    END IF;
                END $$;
                """
            visibility_constraint_sql = visibility_constraint_template.format(
                media_table=media_table_ident,
                visibility_col=visibility_col_ident,
            )  # nosec B608
            backend.execute(
                visibility_constraint_sql,
                connection=conn,
            )
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            logging.debug(f"Could not add visibility check constraint: {exc}")

        # Add owner_user_id column
        backend.execute(
            f"ALTER TABLE {ident('media')} ADD COLUMN IF NOT EXISTS {ident('owner_user_id')} BIGINT",
            connection=conn,
        )

        # Backfill owner_user_id from client_id where possible
        try:
            media_table_ident = ident("media")
            owner_user_id_col_ident = ident("owner_user_id")
            client_id_col_ident = ident("client_id")
            owner_backfill_template = """
                UPDATE {media_table}
                SET {owner_user_id_col} = CAST({client_id_col} AS BIGINT)
                WHERE {owner_user_id_col} IS NULL
                  AND {client_id_col} ~ '^[0-9]+$'
                """
            owner_backfill_sql = owner_backfill_template.format(
                media_table=media_table_ident,
                owner_user_id_col=owner_user_id_col_ident,
                client_id_col=client_id_col_ident,
            )  # nosec B608
            backend.execute(
                owner_backfill_sql,
                connection=conn,
            )
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            logging.debug(f"Could not backfill owner_user_id: {exc}")

        # Add indexes
        backend.execute(
            f"CREATE INDEX IF NOT EXISTS idx_media_visibility ON {ident('media')}({ident('visibility')})",
            connection=conn,
        )
        backend.execute(
            f"CREATE INDEX IF NOT EXISTS idx_media_owner_user_id ON {ident('media')}({ident('owner_user_id')})",
            connection=conn,
        )

    def _postgres_migrate_to_v10(self, conn) -> None:
        """Ensure Claims tables and review extensions exist (PostgreSQL)."""

        self._ensure_postgres_claims_tables(conn)
        self._ensure_postgres_claims_extensions(conn)

    def _postgres_migrate_to_v11(self, conn) -> None:
        """Ensure MediaFiles table exists for artifact storage (PostgreSQL)."""

        try:
            statements = self._convert_sqlite_sql_to_postgres_statements(
                self._MEDIA_FILES_TABLE_SQL
            )
            for stmt in statements:
                try:
                    self.backend.execute(stmt, connection=conn)
                except BackendDatabaseError as exc:
                    logger.warning(
                        "Could not apply MediaFiles migration statement on PostgreSQL: {}",
                        exc,
                    )
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            # pragma: no cover - defensive
            pass
            logger.warning("MediaFiles Postgres migration v11 failed: {}", exc)

    def _postgres_migrate_to_v12(self, conn) -> None:
        """Ensure collections and content item tables exist (PostgreSQL)."""

        self._ensure_postgres_collections_tables(conn)

    def _postgres_migrate_to_v13(self, conn) -> None:
        """Ensure collections tables are indexed and ready (PostgreSQL)."""

        self._ensure_postgres_collections_tables(conn)

    def _postgres_migrate_to_v14(self, conn) -> None:
        """Ensure Data Tables base schema exists (PostgreSQL)."""

        self._ensure_postgres_data_tables(conn)

    def _postgres_migrate_to_v15(self, conn) -> None:
        """Ensure Data Tables columns and late additions exist (PostgreSQL)."""

        self._ensure_postgres_data_tables(conn)

    def _postgres_migrate_to_v16(self, conn) -> None:
        """Ensure Media.source_hash column/index exist (PostgreSQL)."""

        self._ensure_postgres_source_hash_column(conn)

    def _postgres_migrate_to_v17(self, conn) -> None:
        """Ensure Claims extensions remain aligned (PostgreSQL)."""

        self._ensure_postgres_claims_tables(conn)
        self._ensure_postgres_claims_extensions(conn)

    def _postgres_migrate_to_v18(self, conn) -> None:
        """Ensure sequences are synced after structural changes (PostgreSQL)."""

        self._sync_postgres_sequences(conn)

    def _postgres_migrate_to_v19(self, conn) -> None:
        """Finalise schema ensures (FTS + RLS) for PostgreSQL."""

        self._ensure_postgres_fts(conn)
        self._ensure_postgres_rls(conn)

    def _postgres_migrate_to_v20(self, conn) -> None:
        """Ensure tts_history tables exist (PostgreSQL)."""

        self._ensure_postgres_tts_history(conn)

    def _postgres_migrate_to_v21(self, conn) -> None:
        """Add structure/visual lookup indexes introduced in schema v21."""

        backend = self.backend
        ident = backend.escape_identifier

        structure_table: str | None = None
        if backend.table_exists("documentstructureindex", connection=conn):
            structure_table = "documentstructureindex"
        elif backend.table_exists("DocumentStructureIndex", connection=conn):
            structure_table = "DocumentStructureIndex"
        if structure_table:
            backend.execute(
                (
                    f"CREATE INDEX IF NOT EXISTS {ident('idx_dsi_media_path')} "
                    f"ON {ident(structure_table)} ({ident('media_id')}, {ident('path')})"
                ),
                connection=conn,
            )

        visual_documents_table: str | None = None
        if backend.table_exists("visualdocuments", connection=conn):
            visual_documents_table = "visualdocuments"
        elif backend.table_exists("VisualDocuments", connection=conn):
            visual_documents_table = "VisualDocuments"
        if visual_documents_table:
            backend.execute(
                (
                    f"CREATE INDEX IF NOT EXISTS {ident('idx_visualdocs_caption')} "
                    f"ON {ident(visual_documents_table)} ({ident('caption')})"
                ),
                connection=conn,
            )
            backend.execute(
                (
                    f"CREATE INDEX IF NOT EXISTS {ident('idx_visualdocs_tags')} "
                    f"ON {ident(visual_documents_table)} ({ident('tags')})"
                ),
                connection=conn,
            )

    def _postgres_migrate_to_v22(self, conn) -> None:
        """Ensure email-native schema and lookup indexes exist (schema v22)."""

        self._ensure_postgres_email_schema(conn)

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
                    f"SELECT COALESCE(MAX({ident(column_name)}), 0) AS max_id "  # nosec B608
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
                raise DatabaseError(f"Missing required FTS tables: {', '.join(sorted(missing))}")  # noqa: TRY003
        finally:
            conn.commit()

    def _ensure_sqlite_email_schema(self, conn: sqlite3.Connection) -> None:
        """Ensure email-native schema/index/FTS objects exist on SQLite."""

        try:
            fts_existed = (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='email_fts' LIMIT 1"
                ).fetchone()
                is not None
            )
            conn.executescript(self._EMAIL_SCHEMA_SQL)
            conn.executescript(self._EMAIL_INDICES_SQL)
            conn.executescript(self._EMAIL_SQLITE_FTS_SQL)
            if not fts_existed:
                with suppress(sqlite3.Error):
                    conn.execute("INSERT INTO email_fts(email_fts) VALUES ('rebuild')")
        except sqlite3.Error as exc:
            logger.warning(f"Could not ensure email-native schema on SQLite: {exc}")

    def _ensure_postgres_email_schema(self, conn) -> None:
        """Ensure email-native schema/index objects exist on PostgreSQL."""

        schema_statements = self._convert_sqlite_sql_to_postgres_statements(
            self._EMAIL_SCHEMA_SQL
        )
        index_statements = self._convert_sqlite_sql_to_postgres_statements(
            self._EMAIL_INDICES_SQL
        )
        for stmt in schema_statements + index_statements:
            try:
                self.backend.execute(stmt, connection=conn)
            except BackendDatabaseError as exc:
                logger.warning(
                    "Could not ensure email-native Postgres statement '{}': {}",
                    stmt[:120],
                    exc,
                )

    def _ensure_sqlite_visibility_columns(self, conn: sqlite3.Connection) -> None:
        """
        Ensure Media.visibility and Media.owner_user_id columns and indexes exist on SQLite.

        This guards against mixed-version databases where the base schema has been
        updated but older files may have been migrated without the newer columns.
        """
        try:
            cursor = conn.execute("PRAGMA table_info(Media)")
            columns = {row[1] for row in cursor.fetchall()}
        except sqlite3.Error as exc:
            logging.warning(f"Could not introspect Media table for visibility columns: {exc}")
            return

        try:
            index_cursor = conn.execute("PRAGMA index_list(Media)")
            indexes = {row[1] for row in index_cursor.fetchall()}
        except sqlite3.Error:
            indexes = set()

        statements: list[str] = []

        if "visibility" not in columns:
            statements.append(
                "ALTER TABLE Media ADD COLUMN visibility TEXT DEFAULT 'personal' "
                "CHECK (visibility IN ('personal', 'team', 'org'));"
            )

        if "owner_user_id" not in columns:
            statements.append("ALTER TABLE Media ADD COLUMN owner_user_id INTEGER;")

        # Indexes are idempotent; still skip work when already present.
        if not indexes or "idx_media_visibility" not in indexes:
            statements.append(
                "CREATE INDEX IF NOT EXISTS idx_media_visibility ON Media(visibility);"
            )
        if not indexes or "idx_media_owner_user_id" not in indexes:
            statements.append(
                "CREATE INDEX IF NOT EXISTS idx_media_owner_user_id ON Media(owner_user_id);"
            )

        if not statements:
            return

        try:
            conn.executescript("\n".join(statements))
        except sqlite3.Error as exc:
            logger.warning(f"Could not ensure visibility columns/indexes on Media: {exc}")

    def _ensure_sqlite_source_hash_column(self, conn: sqlite3.Connection) -> None:
        """
        Ensure Media.source_hash column and index exist on SQLite.

        This guards against older databases where the base schema predates source_hash.
        """
        try:
            cursor = conn.execute("PRAGMA table_info(Media)")
            columns = {row[1] for row in cursor.fetchall()}
        except sqlite3.Error as exc:
            logging.warning(f"Could not introspect Media table for source_hash column: {exc}")
            return

        try:
            index_cursor = conn.execute("PRAGMA index_list(Media)")
            indexes = {row[1] for row in index_cursor.fetchall()}
        except sqlite3.Error:
            indexes = set()

        statements: list[str] = []

        if "source_hash" not in columns:
            statements.append("ALTER TABLE Media ADD COLUMN source_hash TEXT;")

        if not indexes or "idx_media_source_hash" not in indexes:
            statements.append(
                "CREATE INDEX IF NOT EXISTS idx_media_source_hash ON Media(source_hash);"
            )

        if not statements:
            return

        try:
            conn.executescript("\n".join(statements))
        except sqlite3.Error as exc:
            logger.warning(f"Could not ensure source_hash column/index on Media: {exc}")

    def _ensure_sqlite_data_tables(self, conn: sqlite3.Connection) -> None:
        """Ensure Data Tables schema exists on SQLite."""
        try:
            conn.executescript(self._DATA_TABLES_SQL)
        except sqlite3.Error as exc:
            logger.warning(f"Could not ensure data_tables schema on SQLite: {exc}")

    def _ensure_sqlite_claims_extensions(self, conn: sqlite3.Connection) -> None:
        """
        Ensure Claims review/cluster columns and related tables exist on SQLite.
        """
        try:
            table_cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='Claims'"
            )
            if not table_cursor.fetchone():
                conn.executescript(self._CLAIMS_TABLE_SQL)
                return
        except sqlite3.Error as exc:
            logger.warning(f"Could not introspect Claims table for extensions: {exc}")
            return

        try:
            cursor = conn.execute("PRAGMA table_info(Claims)")
            columns = {row[1] for row in cursor.fetchall()}
        except sqlite3.Error as exc:
            logging.warning(f"Could not introspect Claims table for extension columns: {exc}")
            return

        statements: list[str] = []

        if "review_status" not in columns:
            statements.append("ALTER TABLE Claims ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending';")
        if "reviewer_id" not in columns:
            statements.append("ALTER TABLE Claims ADD COLUMN reviewer_id INTEGER;")
        if "review_group" not in columns:
            statements.append("ALTER TABLE Claims ADD COLUMN review_group TEXT;")
        if "reviewed_at" not in columns:
            statements.append("ALTER TABLE Claims ADD COLUMN reviewed_at DATETIME;")
        if "review_notes" not in columns:
            statements.append("ALTER TABLE Claims ADD COLUMN review_notes TEXT;")
        if "review_version" not in columns:
            statements.append("ALTER TABLE Claims ADD COLUMN review_version INTEGER NOT NULL DEFAULT 1;")
        if "review_reason_code" not in columns:
            statements.append("ALTER TABLE Claims ADD COLUMN review_reason_code TEXT;")
        if "claim_cluster_id" not in columns:
            statements.append("ALTER TABLE Claims ADD COLUMN claim_cluster_id INTEGER;")

        if statements:
            try:
                conn.executescript("\n".join(statements))
            except sqlite3.Error as exc:
                logger.warning(f"Could not ensure Claims extension columns: {exc}")

        try:
            conn.executescript(self._CLAIMS_TABLE_SQL)
        except sqlite3.Error as exc:
            logger.warning(f"Could not ensure Claims extension tables/indexes: {exc}")

        try:
            events_cursor = conn.execute("PRAGMA table_info(claims_monitoring_events)")
            events_columns = {row[1] for row in events_cursor.fetchall()}
            events_statements: list[str] = []
            if "delivered_at" not in events_columns:
                events_statements.append(
                    "ALTER TABLE claims_monitoring_events ADD COLUMN delivered_at DATETIME;"
                )
            if events_statements:
                conn.executescript("\n".join(events_statements))
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_claims_monitoring_events_delivered "
                "ON claims_monitoring_events(delivered_at);"
            )
        except sqlite3.Error as exc:
            logger.warning(f"Could not ensure delivered_at for claims_monitoring_events: {exc}")

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
        except BackendDatabaseError as exc:
            logger.warning(f"Failed to ensure Postgres chunk-level FTS: {exc}")

    def _ensure_postgres_data_tables(self, conn) -> None:
        """Ensure Data Tables schema exists on PostgreSQL."""
        statements = self._convert_sqlite_sql_to_postgres_statements(self._DATA_TABLES_SQL)
        create_tables = [s for s in statements if s.strip().upper().startswith("CREATE TABLE")]
        other_statements = [s for s in statements if s not in create_tables]

        for stmt in create_tables:
            try:
                self.backend.execute(stmt, connection=conn)
            except BackendDatabaseError as exc:
                logger.warning(
                    "Could not ensure Data Tables base table on PostgreSQL: {}",
                    exc,
                )

        # Some older PostgreSQL schemas may have partial data_tables definitions.
        # Ensure late-added columns exist before applying indexes that depend on them.
        self._ensure_postgres_data_tables_columns(conn)

        for stmt in other_statements:
            try:
                self.backend.execute(stmt, connection=conn)
            except BackendDatabaseError as exc:
                logger.warning(
                    "Could not ensure Data Tables index/statement on PostgreSQL: {}",
                    exc,
                )

    def _ensure_postgres_columns(
        self,
        conn,
        *,
        table: str,
        column_defs: dict[str, str],
    ) -> None:
        """Ensure a set of columns exist on a PostgreSQL table."""

        backend = self.backend
        ident = backend.escape_identifier

        if not backend.table_exists(table, connection=conn):
            return

        try:
            existing = {
                str(row.get("name") or "").lower()
                for row in backend.get_table_info(table, connection=conn)
            }
        except BackendDatabaseError as exc:
            logger.warning("Could not introspect PostgreSQL table {}: {}", table, exc)
            return

        for column, definition in column_defs.items():
            if column.lower() in existing:
                continue
            try:
                backend.execute(
                    f"ALTER TABLE {ident(table)} "
                    f"ADD COLUMN IF NOT EXISTS {ident(column)} {definition}",
                    connection=conn,
                )
            except BackendDatabaseError as exc:
                logger.warning(
                    "Could not add PostgreSQL column {}.{}: {}",
                    table,
                    column,
                    exc,
                )

    def _ensure_postgres_data_tables_columns(self, conn) -> None:
        """Ensure late-added Data Tables columns and indexes exist on PostgreSQL."""

        backend = self.backend
        ident = backend.escape_identifier

        try:
            self._ensure_postgres_columns(
                conn,
                table="data_tables",
                column_defs={
                    "workspace_tag": "TEXT",
                    "column_hints_json": "TEXT",
                    "last_modified": "TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP",
                    "version": "INTEGER NOT NULL DEFAULT 1",
                    "client_id": "TEXT NOT NULL DEFAULT ''",
                    "deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
                    "prev_version": "BIGINT",
                    "merge_parent_uuid": "TEXT",
                },
            )
            self._ensure_postgres_columns(
                conn,
                table="data_table_columns",
                column_defs={
                    "format": "TEXT",
                    "last_modified": "TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP",
                    "version": "INTEGER NOT NULL DEFAULT 1",
                    "client_id": "TEXT NOT NULL DEFAULT ''",
                    "deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
                    "prev_version": "BIGINT",
                    "merge_parent_uuid": "TEXT",
                },
            )
            self._ensure_postgres_columns(
                conn,
                table="data_table_rows",
                column_defs={
                    "row_hash": "TEXT",
                    "last_modified": "TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP",
                    "version": "INTEGER NOT NULL DEFAULT 1",
                    "client_id": "TEXT NOT NULL DEFAULT ''",
                    "deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
                    "prev_version": "BIGINT",
                    "merge_parent_uuid": "TEXT",
                },
            )
            self._ensure_postgres_columns(
                conn,
                table="data_table_sources",
                column_defs={
                    "last_modified": "TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP",
                    "version": "INTEGER NOT NULL DEFAULT 1",
                    "client_id": "TEXT NOT NULL DEFAULT ''",
                    "deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
                    "prev_version": "BIGINT",
                    "merge_parent_uuid": "TEXT",
                },
            )

            if backend.table_exists("data_tables", connection=conn):
                backend.execute(
                    f"UPDATE {ident('data_tables')} "  # nosec B608
                    f"SET {ident('client_id')} = %s "
                    f"WHERE {ident('client_id')} IS NULL OR {ident('client_id')} = ''",
                    (str(self.client_id),),
                    connection=conn,
                )
                backend.execute(
                    f"UPDATE {ident('data_tables')} "  # nosec B608
                    f"SET {ident('last_modified')} = CURRENT_TIMESTAMP "
                    f"WHERE {ident('last_modified')} IS NULL",
                    connection=conn,
                )
                backend.execute(
                    f"CREATE INDEX IF NOT EXISTS {ident('idx_data_tables_workspace_tag')} "
                    f"ON {ident('data_tables')} ({ident('workspace_tag')})",
                    connection=conn,
                )
        except BackendDatabaseError as exc:
            logger.warning(
                "Could not ensure late Data Tables columns/indexes on PostgreSQL: {}",
                exc,
            )

    def _ensure_postgres_claims_tables(self, conn) -> None:
        """Ensure Claims base tables exist on PostgreSQL."""

        statements = self._convert_sqlite_sql_to_postgres_statements(self._CLAIMS_TABLE_SQL)
        create_tables = [s for s in statements if s.strip().upper().startswith("CREATE TABLE")]
        other_statements = [s for s in statements if s not in create_tables]

        for stmt in create_tables:
            try:
                self.backend.execute(stmt, connection=conn)
            except BackendDatabaseError as exc:
                logger.warning("Could not ensure Claims base table on PostgreSQL: {}", exc)

        # Claims extensions add late columns before index creation.
        self._ensure_postgres_claims_extensions(conn)

        for stmt in other_statements:
            try:
                self.backend.execute(stmt, connection=conn)
            except BackendDatabaseError as exc:
                logger.warning("Could not ensure Claims index/statement on PostgreSQL: {}", exc)

    def _ensure_postgres_collections_tables(self, conn) -> None:
        """Ensure collections/content item tables exist on PostgreSQL."""

        backend = self.backend

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
            backend.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_output_templates_user_name "
                "ON output_templates(user_id, name)",
                connection=conn,
            )
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
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_highlights_user_item ON reading_highlights(user_id, item_id)",
                connection=conn,
            )
            backend.execute(
                (
                    "CREATE TABLE IF NOT EXISTS collection_tags ("
                    "id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, "
                    "UNIQUE (user_id, name))"
                ),
                connection=conn,
            )
            backend.execute(
                (
                    "CREATE TABLE IF NOT EXISTS content_items ("
                    "id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, origin TEXT NOT NULL, origin_type TEXT, "
                    "origin_id BIGINT, url TEXT, canonical_url TEXT, domain TEXT, title TEXT, summary TEXT, notes TEXT, "
                    "content_hash TEXT, word_count INTEGER, published_at TEXT, status TEXT, favorite INTEGER NOT NULL DEFAULT 0, "
                    "metadata_json TEXT, media_id BIGINT, job_id BIGINT, run_id BIGINT, source_id BIGINT, read_at TEXT, "
                    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
                ),
                connection=conn,
            )
            backend.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_canonical "
                "ON content_items(user_id, canonical_url) WHERE canonical_url IS NOT NULL",
                connection=conn,
            )
            backend.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_hash "
                "ON content_items(user_id, content_hash) WHERE content_hash IS NOT NULL",
                connection=conn,
            )
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_content_items_user_updated "
                "ON content_items(user_id, updated_at DESC)",
                connection=conn,
            )
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_content_items_user_domain "
                "ON content_items(user_id, domain)",
                connection=conn,
            )
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_content_items_job "
                "ON content_items(job_id)",
                connection=conn,
            )
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_content_items_run "
                "ON content_items(run_id)",
                connection=conn,
            )
            backend.execute(
                (
                    "CREATE TABLE IF NOT EXISTS content_item_tags ("
                    "item_id BIGINT NOT NULL, tag_id BIGINT NOT NULL, "
                    "UNIQUE (item_id, tag_id))"
                ),
                connection=conn,
            )
        except BackendDatabaseError as exc:
            logger.warning("Could not ensure collections tables on PostgreSQL: {}", exc)

    def _ensure_postgres_tts_history(self, conn) -> None:
        """Ensure TTS history tables and indexes exist on PostgreSQL."""

        backend = self.backend
        try:
            backend.execute(
                (
                    "CREATE TABLE IF NOT EXISTS tts_history ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "created_at TIMESTAMPTZ NOT NULL, "
                    "text TEXT, "
                    "text_hash TEXT NOT NULL, "
                    "text_length INTEGER, "
                    "provider TEXT, "
                    "model TEXT, "
                    "voice_id TEXT, "
                    "voice_name TEXT, "
                    "voice_info TEXT, "
                    "format TEXT, "
                    "duration_ms INTEGER, "
                    "generation_time_ms INTEGER, "
                    "params_json TEXT, "
                    "status TEXT, "
                    "segments_json TEXT, "
                    "favorite BOOLEAN NOT NULL DEFAULT FALSE, "
                    "job_id BIGINT, "
                    "output_id BIGINT, "
                    "artifact_ids TEXT, "
                    "artifact_deleted_at TIMESTAMPTZ, "
                    "error_message TEXT, "
                    "deleted BOOLEAN NOT NULL DEFAULT FALSE, "
                    "deleted_at TIMESTAMPTZ"
                    ")"
                ),
                connection=conn,
            )
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_tts_history_user_created "
                "ON tts_history(user_id, created_at DESC)",
                connection=conn,
            )
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_tts_history_user_favorite "
                "ON tts_history(user_id, favorite)",
                connection=conn,
            )
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_tts_history_user_provider "
                "ON tts_history(user_id, provider)",
                connection=conn,
            )
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_tts_history_user_model "
                "ON tts_history(user_id, model)",
                connection=conn,
            )
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_tts_history_user_voice_id "
                "ON tts_history(user_id, voice_id)",
                connection=conn,
            )
            backend.execute(
                "CREATE INDEX IF NOT EXISTS idx_tts_history_user_text_hash "
                "ON tts_history(user_id, text_hash)",
                connection=conn,
            )
        except BackendDatabaseError as exc:
            logger.warning("Could not ensure tts_history table on PostgreSQL: {}", exc)

    def _ensure_postgres_source_hash_column(self, conn) -> None:
        """Ensure Media.source_hash column and index exist on PostgreSQL."""
        backend = self.backend
        ident = backend.escape_identifier
        try:
            backend.execute(
                f"ALTER TABLE {ident('media')} ADD COLUMN IF NOT EXISTS {ident('source_hash')} TEXT",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_media_source_hash')} ON {ident('media')} ({ident('source_hash')})",
                connection=conn,
            )
        except BackendDatabaseError as exc:
            logger.warning(f"Could not ensure source_hash column/index on media: {exc}")

    def _ensure_postgres_claims_extensions(self, conn) -> None:
        """Ensure Claims review/cluster columns and related tables exist on PostgreSQL."""
        backend = self.backend
        ident = backend.escape_identifier
        try:
            backend.execute(
                f"ALTER TABLE {ident('claims')} ADD COLUMN IF NOT EXISTS {ident('review_status')} TEXT DEFAULT 'pending'",
                connection=conn,
            )
            backend.execute(
                f"ALTER TABLE {ident('claims')} ADD COLUMN IF NOT EXISTS {ident('reviewer_id')} BIGINT",
                connection=conn,
            )
            backend.execute(
                f"ALTER TABLE {ident('claims')} ADD COLUMN IF NOT EXISTS {ident('review_group')} TEXT",
                connection=conn,
            )
            backend.execute(
                f"ALTER TABLE {ident('claims')} ADD COLUMN IF NOT EXISTS {ident('reviewed_at')} TIMESTAMPTZ",
                connection=conn,
            )
            backend.execute(
                f"ALTER TABLE {ident('claims')} ADD COLUMN IF NOT EXISTS {ident('review_notes')} TEXT",
                connection=conn,
            )
            backend.execute(
                f"ALTER TABLE {ident('claims')} ADD COLUMN IF NOT EXISTS {ident('review_version')} INTEGER DEFAULT 1",
                connection=conn,
            )
            backend.execute(
                f"ALTER TABLE {ident('claims')} ADD COLUMN IF NOT EXISTS {ident('review_reason_code')} TEXT",
                connection=conn,
            )
            backend.execute(
                f"ALTER TABLE {ident('claims')} ADD COLUMN IF NOT EXISTS {ident('claim_cluster_id')} BIGINT",
                connection=conn,
            )
            backend.execute(
                f"UPDATE {ident('claims')} SET {ident('review_status')} = 'pending' "  # nosec B608
                f"WHERE {ident('review_status')} IS NULL",
                connection=conn,
            )
            backend.execute(
                f"UPDATE {ident('claims')} SET {ident('review_version')} = 1 "  # nosec B608
                f"WHERE {ident('review_version')} IS NULL",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_review_status')} "
                f"ON {ident('claims')} ({ident('review_status')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_reviewer_id')} "
                f"ON {ident('claims')} ({ident('reviewer_id')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_review_group')} "
                f"ON {ident('claims')} ({ident('review_group')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_cluster_id')} "
                f"ON {ident('claims')} ({ident('claim_cluster_id')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claims_review_log')} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "claim_id BIGINT NOT NULL, "
                    "old_status TEXT, "
                    "new_status TEXT, "
                    "old_text TEXT, "
                    "new_text TEXT, "
                    "reviewer_id BIGINT, "
                    "notes TEXT, "
                    "reason_code TEXT, "
                    "action_ip TEXT, "
                    "action_user_agent TEXT, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_review_log_claim')} "
                f"ON {ident('claims_review_log')} ({ident('claim_id')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_review_log_reviewer')} "
                f"ON {ident('claims_review_log')} ({ident('reviewer_id')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_review_log_created')} "
                f"ON {ident('claims_review_log')} ({ident('created_at')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claims_review_extractor_metrics_daily')} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "report_date DATE NOT NULL, "
                    "extractor TEXT NOT NULL, "
                    "extractor_version TEXT NOT NULL DEFAULT '', "
                    "total_reviewed INTEGER NOT NULL DEFAULT 0, "
                    "approved_count INTEGER NOT NULL DEFAULT 0, "
                    "rejected_count INTEGER NOT NULL DEFAULT 0, "
                    "flagged_count INTEGER NOT NULL DEFAULT 0, "
                    "reassigned_count INTEGER NOT NULL DEFAULT 0, "
                    "edited_count INTEGER NOT NULL DEFAULT 0, "
                    "reason_code_counts_json TEXT, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "UNIQUE (user_id, report_date, extractor, extractor_version))"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_review_metrics_user')} "
                f"ON {ident('claims_review_extractor_metrics_daily')} ({ident('user_id')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_review_metrics_date')} "
                f"ON {ident('claims_review_extractor_metrics_daily')} ({ident('report_date')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_review_metrics_extractor')} "
                f"ON {ident('claims_review_extractor_metrics_daily')} ({ident('extractor')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claims_review_rules')} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "priority INTEGER NOT NULL DEFAULT 0, "
                    "predicate_json TEXT NOT NULL, "
                    "reviewer_id BIGINT, "
                    "review_group TEXT, "
                    "active BOOLEAN NOT NULL DEFAULT TRUE, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_review_rules_user')} "
                f"ON {ident('claims_review_rules')} ({ident('user_id')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_review_rules_active')} "
                f"ON {ident('claims_review_rules')} ({ident('active')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claims_monitoring_settings')} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "threshold_ratio DOUBLE PRECISION, "
                    "baseline_ratio DOUBLE PRECISION, "
                    "slack_webhook_url TEXT, "
                    "webhook_url TEXT, "
                    "email_recipients TEXT, "
                    "enabled BOOLEAN NOT NULL DEFAULT TRUE, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {ident('idx_claims_monitoring_settings_user')} "
                f"ON {ident('claims_monitoring_settings')} ({ident('user_id')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claims_monitoring_alerts')} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "name TEXT NOT NULL, "
                    "alert_type TEXT NOT NULL, "
                    "threshold_ratio DOUBLE PRECISION, "
                    "baseline_ratio DOUBLE PRECISION, "
                    "channels_json TEXT NOT NULL, "
                    "slack_webhook_url TEXT, "
                    "webhook_url TEXT, "
                    "email_recipients TEXT, "
                    "enabled BOOLEAN NOT NULL DEFAULT TRUE, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_monitoring_alerts_user')} "
                f"ON {ident('claims_monitoring_alerts')} ({ident('user_id')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claims_monitoring_config')} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "threshold_ratio DOUBLE PRECISION, "
                    "baseline_ratio DOUBLE PRECISION, "
                    "slack_webhook_url TEXT, "
                    "webhook_url TEXT, "
                    "email_recipients TEXT, "
                    "enabled BOOLEAN NOT NULL DEFAULT TRUE, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_monitoring_user')} "
                f"ON {ident('claims_monitoring_config')} ({ident('user_id')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claims_monitoring_events')} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "event_type TEXT NOT NULL, "
                    "severity TEXT, "
                    "payload_json TEXT, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "delivered_at TIMESTAMPTZ)"
                ),
                connection=conn,
            )
            backend.execute(
                f"ALTER TABLE {ident('claims_monitoring_events')} "
                f"ADD COLUMN IF NOT EXISTS {ident('delivered_at')} TIMESTAMPTZ",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_monitoring_events_user')} "
                f"ON {ident('claims_monitoring_events')} ({ident('user_id')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_monitoring_events_type')} "
                f"ON {ident('claims_monitoring_events')} ({ident('event_type')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_monitoring_events_delivered')} "
                f"ON {ident('claims_monitoring_events')} ({ident('delivered_at')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claims_monitoring_health')} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "queue_size INTEGER NOT NULL DEFAULT 0, "
                    "worker_count INTEGER, "
                    "last_worker_heartbeat TIMESTAMPTZ, "
                    "last_processed_at TIMESTAMPTZ, "
                    "last_failure_at TIMESTAMPTZ, "
                    "last_failure_reason TEXT, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {ident('idx_claims_monitoring_health_user')} "
                f"ON {ident('claims_monitoring_health')} ({ident('user_id')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claims_analytics_exports')} ("
                    "export_id TEXT PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "format TEXT NOT NULL, "
                    "status TEXT NOT NULL, "
                    "payload_json TEXT, "
                    "payload_csv TEXT, "
                    "filters_json TEXT, "
                    "pagination_json TEXT, "
                    "error_message TEXT, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_analytics_exports_user')} "
                f"ON {ident('claims_analytics_exports')} ({ident('user_id')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claims_notifications')} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "kind TEXT NOT NULL, "
                    "target_user_id TEXT, "
                    "target_review_group TEXT, "
                    "resource_type TEXT, "
                    "resource_id TEXT, "
                    "payload_json TEXT NOT NULL, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "delivered_at TIMESTAMPTZ)"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_notifications_user')} "
                f"ON {ident('claims_notifications')} ({ident('user_id')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_notifications_kind')} "
                f"ON {ident('claims_notifications')} ({ident('kind')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_notifications_target_user')} "
                f"ON {ident('claims_notifications')} ({ident('target_user_id')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_notifications_review_group')} "
                f"ON {ident('claims_notifications')} ({ident('target_review_group')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_notifications_resource')} "
                f"ON {ident('claims_notifications')} ({ident('resource_type')}, {ident('resource_id')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claims_notifications_delivered')} "
                f"ON {ident('claims_notifications')} ({ident('delivered_at')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claim_clusters')} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "user_id TEXT NOT NULL, "
                    "canonical_claim_text TEXT, "
                    "representative_claim_id BIGINT, "
                    "summary TEXT, "
                    "cluster_version INTEGER NOT NULL DEFAULT 1, "
                    "watchlist_count INTEGER NOT NULL DEFAULT 0, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claim_clusters_user')} "
                f"ON {ident('claim_clusters')} ({ident('user_id')})",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claim_clusters_updated')} "
                f"ON {ident('claim_clusters')} ({ident('updated_at')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claim_cluster_membership')} ("
                    "cluster_id BIGINT NOT NULL, "
                    "claim_id BIGINT NOT NULL, "
                    "similarity_score DOUBLE PRECISION, "
                    "cluster_joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "PRIMARY KEY (cluster_id, claim_id))"
                ),
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_claim_cluster_membership_claim')} "
                f"ON {ident('claim_cluster_membership')} ({ident('claim_id')})",
                connection=conn,
            )

            backend.execute(
                (
                    f"CREATE TABLE IF NOT EXISTS {ident('claim_cluster_links')} ("
                    "parent_cluster_id BIGINT NOT NULL, "
                    "child_cluster_id BIGINT NOT NULL, "
                    "relation_type TEXT, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "PRIMARY KEY (parent_cluster_id, child_cluster_id))"
                ),
                connection=conn,
            )
        except BackendDatabaseError as exc:
            logger.warning(f"Could not ensure Claims extensions on Postgres: {exc}")

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
        except BackendDatabaseError as exc:
            logger.warning(
                f"Failed to inspect Postgres RLS policy '{policy}' on table '{table}': {exc}"
            )
            return False

    def _ensure_postgres_rls(self, conn) -> None:
        """Ensure row-level security policies exist for shared content tables.

        Visibility-aware policies:
        - personal: Only the owner can access (owner_user_id or client_id match)
        - team: Team members can access (team_id in user's teams)
        - org: Organization members can access (org_id in user's orgs)
        - admin: Platform admins can access everything
        """
        backend = self.backend
        ident = backend.escape_identifier

        # Helper expressions for array conversions
        org_array = "COALESCE(string_to_array(NULLIF(current_setting('app.org_ids', true), ''), ',')::BIGINT[], ARRAY[]::BIGINT[])"
        team_array = "COALESCE(string_to_array(NULLIF(current_setting('app.team_ids', true), ''), ',')::BIGINT[], ARRAY[]::BIGINT[])"
        current_user = "current_setting('app.current_user_id', true)"
        is_admin = "COALESCE(current_setting('app.is_admin', true), '0') = '1'"
        not_deleted_predicate = f"COALESCE({ident('media')}.deleted, FALSE) = FALSE"

        # Build visibility-aware predicates for media table
        # Personal: owner_user_id matches OR client_id matches (backwards compatibility)
        personal_predicate = (
            f"(COALESCE({ident('media')}.visibility, 'personal') = 'personal' "
            f"AND (COALESCE({ident('media')}.owner_user_id::TEXT, {ident('media')}.client_id) = {current_user}))"
        )

        # Team: visibility is 'team' AND team_id is in user's team list
        team_predicate = (
            f"({ident('media')}.visibility = 'team' "
            f"AND {ident('media')}.team_id IS NOT NULL "
            f"AND {ident('media')}.team_id = ANY({team_array}))"
        )

        # Org: visibility is 'org' AND org_id is in user's org list
        org_predicate = (
            f"({ident('media')}.visibility = 'org' "
            f"AND {ident('media')}.org_id IS NOT NULL "
            f"AND {ident('media')}.org_id = ANY({org_array}))"
        )

        # Combined media access: admin OR personal OR team OR org
        media_access_predicate = (
            f"({is_admin} OR ({not_deleted_predicate} AND ({personal_predicate} OR {team_predicate} OR {org_predicate})))"
        )

        policy_sets = {
            'media': [
                ('media_visibility_access', media_access_predicate),
            ],
            'sync_log': [
                ('sync_scope_admin', is_admin),
                ('sync_scope_personal', f"{ident('sync_log')}.client_id = {current_user}"),
                ('sync_scope_org', f"{ident('sync_log')}.org_id IS NOT NULL AND {ident('sync_log')}.org_id = ANY({org_array})"),
                ('sync_scope_team', f"{ident('sync_log')}.team_id IS NOT NULL AND {ident('sync_log')}.team_id = ANY({team_array})"),
            ],
        }

        # Drop old media policies if they exist (migration to new visibility-based policy)
        old_media_policies = ['media_scope_admin', 'media_scope_personal', 'media_scope_org', 'media_scope_team']
        for old_policy in old_media_policies:
            try:
                if self._postgres_policy_exists(conn, 'media', old_policy):
                    backend.execute(
                        f"DROP POLICY IF EXISTS {backend.escape_identifier(old_policy)} ON {ident('media')}",
                        connection=conn,
                    )
                    logger.debug(f"Dropped old media policy: {old_policy}")
            except BackendDatabaseError as exc:
                logger.warning(f"Could not drop old media policy '{old_policy}': {exc}")

        try:
            backend.execute(
                f"ALTER TABLE {ident('media')} ENABLE ROW LEVEL SECURITY",
                connection=conn,
            )
            backend.execute(
                f"ALTER TABLE {ident('media')} FORCE ROW LEVEL SECURITY",
                connection=conn,
            )
        except BackendDatabaseError as exc:
            logger.warning(f"Could not enable RLS for media table: {exc}")

        # Create new visibility-aware media policy
        for policy_name, predicate in policy_sets['media']:
            try:
                # Drop and recreate to ensure latest predicate
                try:
                    backend.execute(
                        f"DROP POLICY IF EXISTS {backend.escape_identifier(policy_name)} ON {ident('media')}",
                        connection=conn,
                    )
                except BackendDatabaseError as exc:
                    logger.warning(f"Could not drop existing media policy '{policy_name}': {exc}")
                backend.execute(
                    f"""
                    CREATE POLICY {backend.escape_identifier(policy_name)} ON {ident('media')}
                    FOR ALL
                    USING ({predicate})
                    WITH CHECK ({predicate})
                    """,
                    connection=conn,
                )
            except BackendDatabaseError as exc:
                logger.warning(f"Skipping creation of media policy '{policy_name}': {exc}")

        try:
            backend.execute(
                f"ALTER TABLE {ident('sync_log')} ENABLE ROW LEVEL SECURITY",
                connection=conn,
            )
            backend.execute(
                f"ALTER TABLE {ident('sync_log')} FORCE ROW LEVEL SECURITY",
                connection=conn,
            )
        except BackendDatabaseError as exc:
            logger.warning(f"Could not enable RLS for sync_log table: {exc}")

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
            except BackendDatabaseError as exc:
                logger.warning(f"Skipping creation of sync_log policy '{policy_name}': {exc}")

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
    def upsert_claims(self, claims: list[dict[str, Any]]) -> int:
        """
        Insert claims in bulk. This is a minimal Stage 1 helper.

        Expects each item to contain: media_id, chunk_index, claim_text, chunk_hash,
        extractor, extractor_version. Optional: span_start, span_end, confidence,
        uuid, last_modified, version, client_id, deleted, reviewer_id, review_group.

        Returns:
            int: Number of rows inserted.
        """
        if not claims:
            return 0
        now = self._get_current_utc_timestamp_str()
        rows: list[tuple] = []
        for c in claims:
            media_id = int(c["media_id"])
            extractor = str(c.get("extractor", "heuristic"))
            reviewer_id = c.get("reviewer_id")
            review_group = c.get("review_group")
            rows.append((
                media_id,
                int(c.get("chunk_index", 0)),
                c.get("span_start"),
                c.get("span_end"),
                str(c["claim_text"]),
                float(c.get("confidence")) if c.get("confidence") is not None else None,
                extractor,
                str(c.get("extractor_version", "v1")),
                str(c["chunk_hash"]),
                str(c.get("uuid", self._generate_uuid())),
                str(c.get("last_modified", now)),
                int(c.get("version", 1)),
                str(c.get("client_id", self.client_id)),
                c.get("prev_version"),
                c.get("merge_parent_uuid"),
                int(reviewer_id) if reviewer_id is not None else None,
                str(review_group) if review_group else None,
            ))
        with self.transaction() as conn:
            self.execute_many(
                """
                INSERT INTO Claims (
                    media_id, chunk_index, span_start, span_end, claim_text, confidence,
                    extractor, extractor_version, chunk_hash, uuid, last_modified,
                    version, client_id, prev_version, merge_parent_uuid, reviewer_id, review_group
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
                commit=False,
                connection=conn,
            )
        return len(rows)

    def get_claims_by_media(self, media_id: int, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """
        Fetch claims for a media item (excluding soft-deleted), ordered by chunk_index then id.
        """
        cur = self.execute_query(
            """
            SELECT id, media_id, chunk_index, span_start, span_end, claim_text, confidence,
                   extractor, extractor_version, chunk_hash, created_at, uuid,
                   last_modified, version, client_id,
                   review_status, reviewer_id, review_group, reviewed_at,
                   review_notes, review_version, review_reason_code, claim_cluster_id
            FROM Claims
            WHERE media_id = ? AND deleted = 0
            ORDER BY chunk_index ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            (media_id, int(limit), int(max(0, offset))),
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_claims(
        self,
        *,
        media_id: int | None = None,
        owner_user_id: int | None = None,
        org_id: int | None = None,
        team_id: int | None = None,
        review_status: str | None = None,
        reviewer_id: int | None = None,
        review_group: str | None = None,
        claim_cluster_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """
        List claims with optional media and scope filtering.

        Joins Media to apply visibility scoping when a request scope is active.
        """
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            limit, offset = 100, 0
        limit = max(1, min(1000, limit))
        offset = max(0, offset)

        conditions: list[str] = ["c.media_id = m.id"]
        params: list[Any] = []

        if not include_deleted:
            conditions.append("c.deleted = 0")
        if media_id is not None:
            conditions.append("c.media_id = ?")
            params.append(int(media_id))
        if owner_user_id is not None:
            conditions.append("COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?")
            params.append(str(owner_user_id))
        if org_id is not None:
            conditions.append("m.org_id = ?")
            params.append(int(org_id))
        if team_id is not None:
            conditions.append("m.team_id = ?")
            params.append(int(team_id))
        if review_status is not None:
            conditions.append("c.review_status = ?")
            params.append(str(review_status))
        if reviewer_id is not None:
            conditions.append("c.reviewer_id = ?")
            params.append(int(reviewer_id))
        if review_group is not None:
            conditions.append("c.review_group = ?")
            params.append(str(review_group))
        if claim_cluster_id is not None:
            conditions.append("c.claim_cluster_id = ?")
            params.append(int(claim_cluster_id))

        # Visibility filtering (SQLite or Postgres shared backend)
        try:
            scope = get_scope()
        except _MEDIA_NONCRITICAL_EXCEPTIONS as scope_err:
            logging.debug(f"Failed to resolve scope for claims visibility filter: {scope_err}")
            scope = None
        if scope and not scope.is_admin:
            visibility_parts: list[str] = []
            user_id_str = str(scope.user_id) if scope.user_id is not None else ""
            if user_id_str:
                visibility_parts.append(
                    "(COALESCE(m.visibility, 'personal') = 'personal' "
                    "AND (COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?))"
                )
                params.append(user_id_str)
            if scope.team_ids:
                team_placeholders = ",".join("?" * len(scope.team_ids))
                visibility_parts.append(
                    f"(m.visibility = 'team' AND m.team_id IN ({team_placeholders}))"
                )
                params.extend(scope.team_ids)
            if scope.org_ids:
                org_placeholders = ",".join("?" * len(scope.org_ids))
                visibility_parts.append(
                    f"(m.visibility = 'org' AND m.org_id IN ({org_placeholders}))"
                )
                params.extend(scope.org_ids)

            if visibility_parts:
                conditions.append(f"({' OR '.join(visibility_parts)})")
            else:
                conditions.append("(0 = 1)")

        sql = (
            "SELECT c.id, c.media_id, c.chunk_index, c.span_start, c.span_end, c.claim_text, "  # nosec B608
            "c.confidence, c.extractor, c.extractor_version, c.chunk_hash, c.created_at, c.uuid, "
            "c.last_modified, c.version, c.client_id, "
            "c.review_status, c.reviewer_id, c.review_group, c.reviewed_at, "
            "c.review_notes, c.review_version, c.review_reason_code, c.claim_cluster_id, "
            "m.title AS media_title, m.visibility AS media_visibility, "
            "m.owner_user_id AS media_owner_user_id, m.org_id AS media_org_id, "
            "m.team_id AS media_team_id, m.client_id AS media_client_id "
            "FROM Claims c JOIN Media m ON c.media_id = m.id "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY c.media_id ASC, c.chunk_index ASC, c.id ASC "
            "LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_claim_with_media(self, claim_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
        """Fetch a claim by id with media visibility metadata (scoped)."""
        conditions: list[str] = ["c.media_id = m.id", "c.id = ?"]
        params: list[Any] = [int(claim_id)]

        if not include_deleted:
            conditions.append("c.deleted = 0")

        try:
            scope = get_scope()
        except _MEDIA_NONCRITICAL_EXCEPTIONS as scope_err:
            logging.debug(f"Failed to resolve scope for claim lookup: {scope_err}")
            scope = None
        if scope and not scope.is_admin:
            visibility_parts: list[str] = []
            user_id_str = str(scope.user_id) if scope.user_id is not None else ""
            if user_id_str:
                visibility_parts.append(
                    "(COALESCE(m.visibility, 'personal') = 'personal' "
                    "AND (COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?))"
                )
                params.append(user_id_str)
            if scope.team_ids:
                team_placeholders = ",".join("?" * len(scope.team_ids))
                visibility_parts.append(
                    f"(m.visibility = 'team' AND m.team_id IN ({team_placeholders}))"
                )
                params.extend(scope.team_ids)
            if scope.org_ids:
                org_placeholders = ",".join("?" * len(scope.org_ids))
                visibility_parts.append(
                    f"(m.visibility = 'org' AND m.org_id IN ({org_placeholders}))"
                )
                params.extend(scope.org_ids)

            if visibility_parts:
                conditions.append(f"({' OR '.join(visibility_parts)})")
            else:
                conditions.append("(0 = 1)")

        sql = (
            "SELECT c.id, c.media_id, c.chunk_index, c.span_start, c.span_end, c.claim_text, "  # nosec B608
            "c.confidence, c.extractor, c.extractor_version, c.chunk_hash, c.created_at, c.uuid, "
            "c.last_modified, c.version, c.client_id, c.deleted, "
            "c.review_status, c.reviewer_id, c.review_group, c.reviewed_at, "
            "c.review_notes, c.review_version, c.review_reason_code, c.claim_cluster_id, "
            "m.title AS media_title, m.visibility AS media_visibility, "
            "m.owner_user_id AS media_owner_user_id, m.org_id AS media_org_id, "
            "m.team_id AS media_team_id, m.client_id AS media_client_id "
            "FROM Claims c JOIN Media m ON c.media_id = m.id "
            f"WHERE {' AND '.join(conditions)} "
            "LIMIT 1"
        )
        row = self.execute_query(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def update_claim(
        self,
        claim_id: int,
        *,
        claim_text: str | None = None,
        span_start: int | None = None,
        span_end: int | None = None,
        confidence: float | None = None,
        extractor: str | None = None,
        extractor_version: str | None = None,
        deleted: bool | None = None,
    ) -> dict[str, Any] | None:
        """
        Update a claim row and return the updated record (or None if missing).
        """
        update_parts: list[str] = []
        params: list[Any] = []

        if claim_text is not None:
            update_parts.append("claim_text = ?")
            params.append(str(claim_text))
        if span_start is not None:
            update_parts.append("span_start = ?")
            params.append(int(span_start))
        if span_end is not None:
            update_parts.append("span_end = ?")
            params.append(int(span_end))
        if confidence is not None:
            update_parts.append("confidence = ?")
            params.append(float(confidence))
        if extractor is not None:
            update_parts.append("extractor = ?")
            params.append(str(extractor))
        if extractor_version is not None:
            update_parts.append("extractor_version = ?")
            params.append(str(extractor_version))
        if deleted is not None:
            update_parts.append("deleted = ?")
            params.append(1 if deleted else 0)

        if not update_parts:
            return self.get_claim_with_media(int(claim_id), include_deleted=True)

        now = self._get_current_utc_timestamp_str()
        update_parts.append("last_modified = ?")
        params.append(now)
        update_parts.append("version = version + 1")
        update_parts.append("client_id = ?")
        params.append(str(self.client_id))

        params.append(int(claim_id))

        sql = "UPDATE Claims SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
        self.execute_query(sql, tuple(params), commit=True)

        if self.backend_type == BackendType.POSTGRESQL and claim_text is not None:
            self.execute_query(
                "UPDATE Claims "
                "SET claims_fts_tsv = CASE "
                "WHEN deleted = 0 THEN to_tsvector('english', coalesce(claim_text, '')) "
                "ELSE NULL END "
                "WHERE id = ?",
                (int(claim_id),),
                commit=True,
            )

        return self.get_claim_with_media(int(claim_id), include_deleted=True)

    def update_claim_review(
        self,
        claim_id: int,
        *,
        review_status: str | None = None,
        reviewer_id: int | None = None,
        review_group: str | None = None,
        review_notes: str | None = None,
        review_reason_code: str | None = None,
        corrected_text: str | None = None,
        span_start: int | None = None,
        span_end: int | None = None,
        expected_version: int | None = None,
        action_ip: str | None = None,
        action_user_agent: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Update review fields on a claim with optional optimistic locking.

        Returns the updated claim row, or a dict with conflict metadata if the
        expected_version does not match.
        """
        with self.transaction() as conn:
            row = self._fetchone_with_connection(
                conn,
                "SELECT * FROM Claims WHERE id = ?",
                (int(claim_id),),
            )
            if not row:
                return None

            current_review_version = int(row.get("review_version") or 1)
            if expected_version is not None and current_review_version != int(expected_version):
                return {"conflict": True, "current": dict(row)}

            update_parts: list[str] = []
            params: list[Any] = []
            now = self._get_current_utc_timestamp_str()

            if review_status is not None:
                update_parts.append("review_status = ?")
                params.append(str(review_status))
            if reviewer_id is not None:
                update_parts.append("reviewer_id = ?")
                params.append(int(reviewer_id))
            if review_group is not None:
                update_parts.append("review_group = ?")
                params.append(str(review_group))
            if review_notes is not None:
                update_parts.append("review_notes = ?")
                params.append(str(review_notes))
            if review_reason_code is not None:
                update_parts.append("review_reason_code = ?")
                params.append(str(review_reason_code))
            if span_start is not None:
                update_parts.append("span_start = ?")
                params.append(int(span_start))
            if span_end is not None:
                update_parts.append("span_end = ?")
                params.append(int(span_end))

            if corrected_text is not None:
                update_parts.append("claim_text = ?")
                params.append(str(corrected_text))
                update_parts.append("last_modified = ?")
                params.append(now)
                update_parts.append("version = version + 1")
                update_parts.append("client_id = ?")
                params.append(str(self.client_id))

            if update_parts:
                update_parts.append("reviewed_at = ?")
                params.append(now)
                update_parts.append("review_version = review_version + 1")

            if not update_parts:
                return dict(row)

            where_clause = "id = ?"
            params.append(int(claim_id))
            if expected_version is not None:
                where_clause += " AND review_version = ?"
                params.append(int(expected_version))

            sql = "UPDATE Claims SET " + ", ".join(update_parts) + " WHERE " + where_clause  # nosec B608
            cur = self._execute_with_connection(conn, sql, tuple(params))
            if cur.rowcount == 0:
                return {"conflict": True, "current": dict(row)}

            if self.backend_type == BackendType.POSTGRESQL and corrected_text is not None:
                self._execute_with_connection(
                    conn,
                    "UPDATE Claims "
                    "SET claims_fts_tsv = CASE "
                    "WHEN deleted = 0 THEN to_tsvector('english', coalesce(claim_text, '')) "
                    "ELSE NULL END "
                    "WHERE id = ?",
                    (int(claim_id),),
                )

            old_status = row.get("review_status")
            old_text = row.get("claim_text")
            new_status = review_status if review_status is not None else old_status
            new_text = corrected_text if corrected_text is not None else old_text
            self._execute_with_connection(
                conn,
                (
                    "INSERT INTO claims_review_log "
                    "(claim_id, old_status, new_status, old_text, new_text, reviewer_id, notes, reason_code, "
                    "action_ip, action_user_agent, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                (
                    int(claim_id),
                    old_status,
                    new_status,
                    old_text,
                    new_text,
                    int(reviewer_id) if reviewer_id is not None else row.get("reviewer_id"),
                    review_notes,
                    review_reason_code,
                    action_ip,
                    action_user_agent,
                    now,
                ),
            )

        return self.get_claim_with_media(int(claim_id), include_deleted=True)

    def list_claim_review_history(self, claim_id: int) -> list[dict[str, Any]]:
        """Return ordered review log entries for a claim."""
        cur = self.execute_query(
            "SELECT id, claim_id, old_status, new_status, old_text, new_text, reviewer_id, notes, "
            "reason_code, action_ip, action_user_agent, created_at "
            "FROM claims_review_log WHERE claim_id = ? ORDER BY created_at ASC",
            (int(claim_id),),
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_claims_review_extractor_metrics_daily(
        self,
        *,
        user_id: str,
        report_date: str,
        extractor: str,
        extractor_version: str | None = None,
    ) -> dict[str, Any]:
        version = "" if extractor_version is None else str(extractor_version)
        row = self.execute_query(
            (
                "SELECT id, user_id, report_date, extractor, extractor_version, total_reviewed, "
                "approved_count, rejected_count, flagged_count, reassigned_count, edited_count, "
                "reason_code_counts_json, created_at, updated_at "
                "FROM claims_review_extractor_metrics_daily "
                "WHERE user_id = ? AND report_date = ? AND extractor = ? AND extractor_version = ?"
            ),
            (
                str(user_id),
                str(report_date),
                str(extractor),
                version,
            ),
        ).fetchone()
        return dict(row) if row else {}

    def upsert_claims_review_extractor_metrics_daily(
        self,
        *,
        user_id: str,
        report_date: str,
        extractor: str,
        extractor_version: str | None = None,
        total_reviewed: int = 0,
        approved_count: int = 0,
        rejected_count: int = 0,
        flagged_count: int = 0,
        reassigned_count: int = 0,
        edited_count: int = 0,
        reason_code_counts_json: str | None = None,
    ) -> dict[str, Any]:
        version = "" if extractor_version is None else str(extractor_version)
        now = self._get_current_utc_timestamp_str()
        existing = self.execute_query(
            "SELECT id FROM claims_review_extractor_metrics_daily "
            "WHERE user_id = ? AND report_date = ? AND extractor = ? AND extractor_version = ?",
            (
                str(user_id),
                str(report_date),
                str(extractor),
                version,
            ),
        ).fetchone()
        existing_id: int | None = None
        if existing is not None:
            try:
                existing_id = int(existing["id"])
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                try:
                    existing_id = int(existing[0])
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    existing_id = None

        if existing_id is None:
            insert_sql = (
                "INSERT INTO claims_review_extractor_metrics_daily "
                "(user_id, report_date, extractor, extractor_version, total_reviewed, approved_count, "
                "rejected_count, flagged_count, reassigned_count, edited_count, reason_code_counts_json, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            self.execute_query(
                insert_sql,
                (
                    str(user_id),
                    str(report_date),
                    str(extractor),
                    version,
                    int(total_reviewed),
                    int(approved_count),
                    int(rejected_count),
                    int(flagged_count),
                    int(reassigned_count),
                    int(edited_count),
                    reason_code_counts_json,
                    now,
                    now,
                ),
                commit=True,
            )
            return self.get_claims_review_extractor_metrics_daily(
                user_id=str(user_id),
                report_date=str(report_date),
                extractor=str(extractor),
                extractor_version=version,
            )

        self.execute_query(
            (
                "UPDATE claims_review_extractor_metrics_daily SET "
                "total_reviewed = ?, approved_count = ?, rejected_count = ?, flagged_count = ?, "
                "reassigned_count = ?, edited_count = ?, reason_code_counts_json = ?, updated_at = ? "
                "WHERE id = ?"
            ),
            (
                int(total_reviewed),
                int(approved_count),
                int(rejected_count),
                int(flagged_count),
                int(reassigned_count),
                int(edited_count),
                reason_code_counts_json,
                now,
                int(existing_id),
            ),
            commit=True,
        )
        return self.get_claims_review_extractor_metrics_daily(
            user_id=str(user_id),
            report_date=str(report_date),
            extractor=str(extractor),
            extractor_version=version,
        )

    def list_claims_review_extractor_metrics_daily(
        self,
        *,
        user_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        extractor: str | None = None,
        extractor_version: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            limit, offset = 500, 0
        limit = max(1, min(5000, limit))
        offset = max(0, offset)

        conditions: list[str] = ["user_id = ?"]
        params: list[Any] = [str(user_id)]
        if start_date:
            conditions.append("report_date >= ?")
            params.append(str(start_date))
        if end_date:
            conditions.append("report_date <= ?")
            params.append(str(end_date))
        if extractor:
            conditions.append("extractor = ?")
            params.append(str(extractor))
        if extractor_version is not None:
            conditions.append("extractor_version = ?")
            params.append(str(extractor_version))

        sql = (
            "SELECT id, user_id, report_date, extractor, extractor_version, total_reviewed, "  # nosec B608
            "approved_count, rejected_count, flagged_count, reassigned_count, edited_count, "
            "reason_code_counts_json, created_at, updated_at "
            "FROM claims_review_extractor_metrics_daily WHERE "
            + " AND ".join(conditions)
            + " ORDER BY report_date DESC, id DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_review_queue(
        self,
        *,
        status: str | None = None,
        reviewer_id: int | None = None,
        review_group: str | None = None,
        media_id: int | None = None,
        extractor: str | None = None,
        owner_user_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """List claims in the review queue with optional filters (scoped)."""
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            limit, offset = 100, 0
        limit = max(1, min(1000, limit))
        offset = max(0, offset)

        conditions: list[str] = ["c.media_id = m.id"]
        params: list[Any] = []

        if not include_deleted:
            conditions.append("c.deleted = 0")
        if status is not None:
            conditions.append("c.review_status = ?")
            params.append(str(status))
        if reviewer_id is not None:
            conditions.append("c.reviewer_id = ?")
            params.append(int(reviewer_id))
        if review_group is not None:
            conditions.append("c.review_group = ?")
            params.append(str(review_group))
        if media_id is not None:
            conditions.append("c.media_id = ?")
            params.append(int(media_id))
        if owner_user_id is not None:
            conditions.append("COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?")
            params.append(str(owner_user_id))
        if extractor is not None:
            conditions.append("c.extractor = ?")
            params.append(str(extractor))

        try:
            scope = get_scope()
        except _MEDIA_NONCRITICAL_EXCEPTIONS as scope_err:
            logging.debug(f"Failed to resolve scope for review queue visibility filter: {scope_err}")
            scope = None
        if scope and not scope.is_admin:
            visibility_parts: list[str] = []
            user_id_str = str(scope.user_id) if scope.user_id is not None else ""
            if user_id_str:
                visibility_parts.append(
                    "(COALESCE(m.visibility, 'personal') = 'personal' "
                    "AND (COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?))"
                )
                params.append(user_id_str)
            if scope.team_ids:
                team_placeholders = ",".join("?" * len(scope.team_ids))
                visibility_parts.append(
                    f"(m.visibility = 'team' AND m.team_id IN ({team_placeholders}))"
                )
                params.extend(scope.team_ids)
            if scope.org_ids:
                org_placeholders = ",".join("?" * len(scope.org_ids))
                visibility_parts.append(
                    f"(m.visibility = 'org' AND m.org_id IN ({org_placeholders}))"
                )
                params.extend(scope.org_ids)

            if visibility_parts:
                conditions.append(f"({' OR '.join(visibility_parts)})")
            else:
                conditions.append("(0 = 1)")

        sql = (
            "SELECT c.id, c.media_id, c.chunk_index, c.span_start, c.span_end, c.claim_text, "  # nosec B608
            "c.confidence, c.extractor, c.extractor_version, c.chunk_hash, c.created_at, c.uuid, "
            "c.last_modified, c.version, c.client_id, c.deleted, "
            "c.review_status, c.reviewer_id, c.review_group, c.reviewed_at, "
            "c.review_notes, c.review_version, c.review_reason_code, c.claim_cluster_id, "
            "m.title AS media_title, m.visibility AS media_visibility, "
            "m.owner_user_id AS media_owner_user_id, m.org_id AS media_org_id, "
            "m.team_id AS media_team_id, m.client_id AS media_client_id "
            "FROM Claims c JOIN Media m ON c.media_id = m.id "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY c.reviewed_at DESC, c.id DESC "
            "LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_claim_review_rules(
        self,
        user_id: str,
        *,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return review assignment rules for a user."""
        sql = (
            "SELECT id, user_id, priority, predicate_json, reviewer_id, review_group, active, "
            "created_at, updated_at "
            "FROM claims_review_rules WHERE user_id = ?"
        )
        params: list[Any] = [str(user_id)]
        if active_only:
            sql += " AND active = 1"
        sql += " ORDER BY priority DESC, id DESC"
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def create_claim_review_rule(
        self,
        *,
        user_id: str,
        priority: int,
        predicate_json: str,
        reviewer_id: int | None = None,
        review_group: str | None = None,
        active: bool = True,
    ) -> dict[str, Any]:
        """Insert a review rule and return it."""
        now = self._get_current_utc_timestamp_str()
        insert_sql = (
            "INSERT INTO claims_review_rules "
            "(user_id, priority, predicate_json, reviewer_id, review_group, active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
        if self.backend_type == BackendType.POSTGRESQL:
            insert_sql += " RETURNING id"
        cursor = self.execute_query(
            insert_sql,
            (
                str(user_id),
                int(priority),
                str(predicate_json),
                int(reviewer_id) if reviewer_id is not None else None,
                review_group,
                1 if active else 0,
                now,
                now,
            ),
            commit=True,
        )
        if self.backend_type == BackendType.POSTGRESQL:
            row = cursor.fetchone()
            rule_id = int(row["id"]) if row else None
        else:
            rule_id = cursor.lastrowid
        if rule_id is None:
            return {}
        return self.get_claim_review_rule(rule_id)

    def get_claim_review_rule(self, rule_id: int) -> dict[str, Any]:
        row = self.execute_query(
            "SELECT id, user_id, priority, predicate_json, reviewer_id, review_group, active, "
            "created_at, updated_at FROM claims_review_rules WHERE id = ?",
            (int(rule_id),),
        ).fetchone()
        return dict(row) if row else {}

    def update_claim_review_rule(
        self,
        rule_id: int,
        *,
        priority: int | None = None,
        predicate_json: str | None = None,
        reviewer_id: int | None = None,
        review_group: str | None = None,
        active: bool | None = None,
    ) -> dict[str, Any]:
        """Update a review rule and return the updated record."""
        update_parts: list[str] = []
        params: list[Any] = []
        now = self._get_current_utc_timestamp_str()

        if priority is not None:
            update_parts.append("priority = ?")
            params.append(int(priority))
        if predicate_json is not None:
            update_parts.append("predicate_json = ?")
            params.append(str(predicate_json))
        if reviewer_id is not None:
            update_parts.append("reviewer_id = ?")
            params.append(int(reviewer_id))
        if review_group is not None:
            update_parts.append("review_group = ?")
            params.append(str(review_group))
        if active is not None:
            update_parts.append("active = ?")
            params.append(1 if active else 0)

        if not update_parts:
            return self.get_claim_review_rule(int(rule_id))

        update_parts.append("updated_at = ?")
        params.append(now)
        params.append(int(rule_id))

        sql = "UPDATE claims_review_rules SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
        self.execute_query(sql, tuple(params), commit=True)
        return self.get_claim_review_rule(int(rule_id))

    def delete_claim_review_rule(self, rule_id: int) -> None:
        """Delete a review rule by id."""
        self.execute_query(
            "DELETE FROM claims_review_rules WHERE id = ?",
            (int(rule_id),),
            commit=True,
        )

    def get_claims_monitoring_settings(self, user_id: str) -> dict[str, Any]:
        row = self.execute_query(
            "SELECT id, user_id, threshold_ratio, baseline_ratio, slack_webhook_url, webhook_url, "
            "email_recipients, enabled, created_at, updated_at "
            "FROM claims_monitoring_settings WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
            (str(user_id),),
        ).fetchone()
        return dict(row) if row else {}

    def upsert_claims_monitoring_settings(
        self,
        *,
        user_id: str,
        threshold_ratio: float | None = None,
        baseline_ratio: float | None = None,
        slack_webhook_url: str | None = None,
        webhook_url: str | None = None,
        email_recipients: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        existing = self.get_claims_monitoring_settings(str(user_id))
        now = self._get_current_utc_timestamp_str()
        if not existing:
            insert_sql = (
                "INSERT INTO claims_monitoring_settings "
                "(user_id, threshold_ratio, baseline_ratio, slack_webhook_url, webhook_url, "
                "email_recipients, enabled, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            if self.backend_type == BackendType.POSTGRESQL:
                insert_sql += " RETURNING id"
            cursor = self.execute_query(
                insert_sql,
                (
                    str(user_id),
                    threshold_ratio,
                    baseline_ratio,
                    slack_webhook_url,
                    webhook_url,
                    email_recipients,
                    1 if enabled is None else (1 if enabled else 0),
                    now,
                    now,
                ),
                commit=True,
            )
            if self.backend_type == BackendType.POSTGRESQL:
                row = cursor.fetchone()
                config_id = int(row["id"]) if row else None
            else:
                config_id = cursor.lastrowid
            return self.get_claims_monitoring_settings(str(user_id)) if config_id else {}

        update_parts: list[str] = []
        params: list[Any] = []
        if threshold_ratio is not None:
            update_parts.append("threshold_ratio = ?")
            params.append(float(threshold_ratio))
        if baseline_ratio is not None:
            update_parts.append("baseline_ratio = ?")
            params.append(float(baseline_ratio))
        if slack_webhook_url is not None:
            update_parts.append("slack_webhook_url = ?")
            params.append(str(slack_webhook_url))
        if webhook_url is not None:
            update_parts.append("webhook_url = ?")
            params.append(str(webhook_url))
        if email_recipients is not None:
            update_parts.append("email_recipients = ?")
            params.append(str(email_recipients))
        if enabled is not None:
            update_parts.append("enabled = ?")
            params.append(1 if enabled else 0)
        if not update_parts:
            return self.get_claims_monitoring_settings(str(user_id))

        update_parts.append("updated_at = ?")
        params.append(now)
        params.append(int(existing.get("id")))
        sql = "UPDATE claims_monitoring_settings SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
        self.execute_query(sql, tuple(params), commit=True)
        return self.get_claims_monitoring_settings(str(user_id))

    def list_claims_monitoring_alerts(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.execute_query(
            "SELECT id, user_id, name, alert_type, threshold_ratio, baseline_ratio, channels_json, "
            "slack_webhook_url, webhook_url, email_recipients, enabled, created_at, updated_at "
            "FROM claims_monitoring_alerts WHERE user_id = ? ORDER BY id DESC",
            (str(user_id),),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_claims_monitoring_alert(self, alert_id: int) -> dict[str, Any]:
        row = self.execute_query(
            "SELECT id, user_id, name, alert_type, threshold_ratio, baseline_ratio, channels_json, "
            "slack_webhook_url, webhook_url, email_recipients, enabled, created_at, updated_at "
            "FROM claims_monitoring_alerts WHERE id = ?",
            (int(alert_id),),
        ).fetchone()
        return dict(row) if row else {}

    def create_claims_monitoring_alert(
        self,
        *,
        user_id: str,
        name: str,
        alert_type: str,
        channels_json: str,
        threshold_ratio: float | None = None,
        baseline_ratio: float | None = None,
        slack_webhook_url: str | None = None,
        webhook_url: str | None = None,
        email_recipients: str | None = None,
        enabled: bool = True,
        alert_id: int | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ) -> dict[str, Any]:
        now = self._get_current_utc_timestamp_str()
        created = created_at or now
        updated = updated_at or now
        if alert_id is not None:
            insert_sql = (
                "INSERT INTO claims_monitoring_alerts "
                "(id, user_id, name, alert_type, threshold_ratio, baseline_ratio, channels_json, "
                "slack_webhook_url, webhook_url, email_recipients, enabled, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            self.execute_query(
                insert_sql,
                (
                    int(alert_id),
                    str(user_id),
                    str(name),
                    str(alert_type),
                    threshold_ratio,
                    baseline_ratio,
                    str(channels_json),
                    slack_webhook_url,
                    webhook_url,
                    email_recipients,
                    1 if enabled else 0,
                    created,
                    updated,
                ),
                commit=True,
            )
            if self.backend_type == BackendType.POSTGRESQL:
                with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                    self.execute_query(
                        "SELECT setval(pg_get_serial_sequence('claims_monitoring_alerts','id'), "
                        "GREATEST((SELECT MAX(id) FROM claims_monitoring_alerts), 1))",
                        commit=True,
                    )
            return self.get_claims_monitoring_alert(int(alert_id))

        insert_sql = (
            "INSERT INTO claims_monitoring_alerts "
            "(user_id, name, alert_type, threshold_ratio, baseline_ratio, channels_json, "
            "slack_webhook_url, webhook_url, email_recipients, enabled, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        if self.backend_type == BackendType.POSTGRESQL:
            insert_sql += " RETURNING id"
        cursor = self.execute_query(
            insert_sql,
            (
                str(user_id),
                str(name),
                str(alert_type),
                threshold_ratio,
                baseline_ratio,
                str(channels_json),
                slack_webhook_url,
                webhook_url,
                email_recipients,
                1 if enabled else 0,
                created,
                updated,
            ),
            commit=True,
        )
        if self.backend_type == BackendType.POSTGRESQL:
            row = cursor.fetchone()
            new_id = int(row["id"]) if row else None
        else:
            new_id = cursor.lastrowid
        return self.get_claims_monitoring_alert(new_id) if new_id else {}

    def update_claims_monitoring_alert(
        self,
        alert_id: int,
        *,
        name: str | None = None,
        alert_type: str | None = None,
        threshold_ratio: float | None = None,
        baseline_ratio: float | None = None,
        channels_json: str | None = None,
        slack_webhook_url: str | None = None,
        webhook_url: str | None = None,
        email_recipients: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        update_parts: list[str] = []
        params: list[Any] = []
        now = self._get_current_utc_timestamp_str()
        if name is not None:
            update_parts.append("name = ?")
            params.append(str(name))
        if alert_type is not None:
            update_parts.append("alert_type = ?")
            params.append(str(alert_type))
        if threshold_ratio is not None:
            update_parts.append("threshold_ratio = ?")
            params.append(float(threshold_ratio))
        if baseline_ratio is not None:
            update_parts.append("baseline_ratio = ?")
            params.append(float(baseline_ratio))
        if channels_json is not None:
            update_parts.append("channels_json = ?")
            params.append(str(channels_json))
        if slack_webhook_url is not None:
            update_parts.append("slack_webhook_url = ?")
            params.append(str(slack_webhook_url))
        if webhook_url is not None:
            update_parts.append("webhook_url = ?")
            params.append(str(webhook_url))
        if email_recipients is not None:
            update_parts.append("email_recipients = ?")
            params.append(str(email_recipients))
        if enabled is not None:
            update_parts.append("enabled = ?")
            params.append(1 if enabled else 0)
        if not update_parts:
            return self.get_claims_monitoring_alert(int(alert_id))
        update_parts.append("updated_at = ?")
        params.append(now)
        params.append(int(alert_id))
        sql = "UPDATE claims_monitoring_alerts SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
        self.execute_query(sql, tuple(params), commit=True)
        return self.get_claims_monitoring_alert(int(alert_id))

    def delete_claims_monitoring_alert(self, alert_id: int) -> None:
        self.execute_query(
            "DELETE FROM claims_monitoring_alerts WHERE id = ?",
            (int(alert_id),),
            commit=True,
        )

    def delete_claims_monitoring_configs_by_user(self, user_id: str) -> None:
        self.execute_query(
            "DELETE FROM claims_monitoring_config WHERE user_id = ?",
            (str(user_id),),
            commit=True,
        )

    def list_claims_monitoring_configs(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """List monitoring configs (alert thresholds + channels) for a user."""
        rows = self.execute_query(
            "SELECT id, user_id, threshold_ratio, baseline_ratio, slack_webhook_url, webhook_url, "
            "email_recipients, enabled, created_at, updated_at "
            "FROM claims_monitoring_config WHERE user_id = ? ORDER BY id DESC",
            (str(user_id),),
        ).fetchall()
        return [dict(row) for row in rows]

    def create_claims_monitoring_config(
        self,
        *,
        user_id: str,
        threshold_ratio: float | None = None,
        baseline_ratio: float | None = None,
        slack_webhook_url: str | None = None,
        webhook_url: str | None = None,
        email_recipients: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Create a monitoring config row and return it."""
        now = self._get_current_utc_timestamp_str()
        insert_sql = (
            "INSERT INTO claims_monitoring_config "
            "(user_id, threshold_ratio, baseline_ratio, slack_webhook_url, webhook_url, "
            "email_recipients, enabled, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        if self.backend_type == BackendType.POSTGRESQL:
            insert_sql += " RETURNING id"
        cursor = self.execute_query(
            insert_sql,
            (
                str(user_id),
                threshold_ratio,
                baseline_ratio,
                slack_webhook_url,
                webhook_url,
                email_recipients,
                1 if enabled else 0,
                now,
                now,
            ),
            commit=True,
        )
        if self.backend_type == BackendType.POSTGRESQL:
            row = cursor.fetchone()
            config_id = int(row["id"]) if row else None
        else:
            config_id = cursor.lastrowid
        return self.get_claims_monitoring_config(config_id) if config_id else {}

    def get_claims_monitoring_config(self, config_id: int) -> dict[str, Any]:
        row = self.execute_query(
            "SELECT id, user_id, threshold_ratio, baseline_ratio, slack_webhook_url, webhook_url, "
            "email_recipients, enabled, created_at, updated_at "
            "FROM claims_monitoring_config WHERE id = ?",
            (int(config_id),),
        ).fetchone()
        return dict(row) if row else {}

    def update_claims_monitoring_config(
        self,
        config_id: int,
        *,
        threshold_ratio: float | None = None,
        baseline_ratio: float | None = None,
        slack_webhook_url: str | None = None,
        webhook_url: str | None = None,
        email_recipients: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        update_parts: list[str] = []
        params: list[Any] = []
        now = self._get_current_utc_timestamp_str()

        if threshold_ratio is not None:
            update_parts.append("threshold_ratio = ?")
            params.append(float(threshold_ratio))
        if baseline_ratio is not None:
            update_parts.append("baseline_ratio = ?")
            params.append(float(baseline_ratio))
        if slack_webhook_url is not None:
            update_parts.append("slack_webhook_url = ?")
            params.append(str(slack_webhook_url))
        if webhook_url is not None:
            update_parts.append("webhook_url = ?")
            params.append(str(webhook_url))
        if email_recipients is not None:
            update_parts.append("email_recipients = ?")
            params.append(str(email_recipients))
        if enabled is not None:
            update_parts.append("enabled = ?")
            params.append(1 if enabled else 0)

        if not update_parts:
            return self.get_claims_monitoring_config(int(config_id))

        update_parts.append("updated_at = ?")
        params.append(now)
        params.append(int(config_id))
        sql = "UPDATE claims_monitoring_config SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
        self.execute_query(sql, tuple(params), commit=True)
        return self.get_claims_monitoring_config(int(config_id))

    def delete_claims_monitoring_config(self, config_id: int) -> None:
        self.execute_query(
            "DELETE FROM claims_monitoring_config WHERE id = ?",
            (int(config_id),),
            commit=True,
        )

    def migrate_legacy_claims_monitoring_alerts(self, user_id: str) -> int:
        """Migrate legacy claims_monitoring_config rows into claims_monitoring_alerts."""
        existing = self.list_claims_monitoring_alerts(user_id)
        if existing:
            return 0
        legacy_rows = self.list_claims_monitoring_configs(user_id)
        if not legacy_rows:
            return 0
        migrated = 0
        for row in legacy_rows:
            slack_url = row.get("slack_webhook_url")
            webhook_url = row.get("webhook_url")
            email_recipients = row.get("email_recipients")
            email_enabled = False
            if email_recipients:
                try:
                    parsed = json.loads(str(email_recipients))
                    email_enabled = bool(parsed) if isinstance(parsed, list) else bool(str(email_recipients).strip())
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    email_enabled = bool(str(email_recipients).strip())
            channels = {
                "slack": bool(slack_url),
                "webhook": bool(webhook_url),
                "email": email_enabled,
            }
            self.create_claims_monitoring_alert(
                alert_id=int(row.get("id")),
                user_id=str(user_id),
                name=f"Legacy alert {row.get('id')}",
                alert_type="threshold_breach",
                threshold_ratio=row.get("threshold_ratio"),
                baseline_ratio=row.get("baseline_ratio"),
                channels_json=json.dumps(channels),
                slack_webhook_url=slack_url,
                webhook_url=webhook_url,
                email_recipients=email_recipients,
                enabled=bool(row.get("enabled", True)),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            )
            migrated += 1
        self.delete_claims_monitoring_configs_by_user(str(user_id))
        return migrated

    def insert_claim_notification(
        self,
        *,
        user_id: str,
        kind: str,
        payload_json: str,
        target_user_id: str | None = None,
        target_review_group: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> dict[str, Any]:
        now = self._get_current_utc_timestamp_str()
        insert_sql = (
            "INSERT INTO claims_notifications "
            "(user_id, kind, target_user_id, target_review_group, resource_type, resource_id, "
            "payload_json, created_at, delivered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        if self.backend_type == BackendType.POSTGRESQL:
            insert_sql += " RETURNING id"
        cursor = self.execute_query(
            insert_sql,
            (
                str(user_id),
                str(kind),
                str(target_user_id) if target_user_id is not None else None,
                str(target_review_group) if target_review_group is not None else None,
                str(resource_type) if resource_type is not None else None,
                str(resource_id) if resource_id is not None else None,
                str(payload_json),
                str(now),
                None,
            ),
            commit=True,
        )
        if self.backend_type == BackendType.POSTGRESQL:
            row = cursor.fetchone()
            notif_id = int(row["id"]) if row else None
        else:
            notif_id = cursor.lastrowid
        return self.get_claim_notification(int(notif_id)) if notif_id else {}

    def get_claim_notification(self, notification_id: int) -> dict[str, Any]:
        row = self.execute_query(
            "SELECT id, user_id, kind, target_user_id, target_review_group, resource_type, "
            "resource_id, payload_json, created_at, delivered_at "
            "FROM claims_notifications WHERE id = ?",
            (int(notification_id),),
        ).fetchone()
        return dict(row) if row else {}

    def get_latest_claim_notification(
        self,
        *,
        user_id: str,
        kind: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> dict[str, Any] | None:
        conditions = ["user_id = ?", "kind = ?"]
        params: list[Any] = [str(user_id), str(kind)]
        if resource_type is not None:
            conditions.append("resource_type = ?")
            params.append(str(resource_type))
        if resource_id is not None:
            conditions.append("resource_id = ?")
            params.append(str(resource_id))
        sql = (
            "SELECT id, user_id, kind, target_user_id, target_review_group, resource_type, "  # nosec B608
            "resource_id, payload_json, created_at, delivered_at "
            "FROM claims_notifications "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY created_at DESC LIMIT 1"
        )
        row = self.execute_query(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def list_claim_notifications(
        self,
        *,
        user_id: str,
        kind: str | None = None,
        target_user_id: str | None = None,
        target_review_group: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        delivered: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            limit, offset = 100, 0
        limit = max(1, min(1000, limit))
        offset = max(0, offset)
        conditions = ["user_id = ?"]
        params: list[Any] = [str(user_id)]
        if kind:
            conditions.append("kind = ?")
            params.append(str(kind))
        if target_user_id:
            conditions.append("target_user_id = ?")
            params.append(str(target_user_id))
        if target_review_group:
            conditions.append("target_review_group = ?")
            params.append(str(target_review_group))
        if resource_type:
            conditions.append("resource_type = ?")
            params.append(str(resource_type))
        if resource_id:
            conditions.append("resource_id = ?")
            params.append(str(resource_id))
        if delivered is True:
            conditions.append("delivered_at IS NOT NULL")
        elif delivered is False:
            conditions.append("delivered_at IS NULL")

        sql = (
            "SELECT id, user_id, kind, target_user_id, target_review_group, resource_type, "  # nosec B608
            "resource_id, payload_json, created_at, delivered_at "
            "FROM claims_notifications "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_claim_notifications_by_ids(self, ids: list[int]) -> list[dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        sql = (
            "SELECT id, user_id, kind, target_user_id, target_review_group, resource_type, "  # nosec B608
            "resource_id, payload_json, created_at, delivered_at "
            f"FROM claims_notifications WHERE id IN ({placeholders})"
        )
        rows = self.execute_query(sql, tuple(int(i) for i in ids)).fetchall()
        return [dict(row) for row in rows]

    def mark_claim_notifications_delivered(self, ids: list[int]) -> int:
        if not ids:
            return 0
        placeholders = ",".join("?" * len(ids))
        now = self._get_current_utc_timestamp_str()
        sql = f"UPDATE claims_notifications SET delivered_at = ? WHERE id IN ({placeholders})"  # nosec B608
        params: list[Any] = [str(now)]
        params.extend([int(i) for i in ids])
        cursor = self.execute_query(sql, tuple(params), commit=True)
        try:
            return int(getattr(cursor, "rowcount", 0) or 0)
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            return 0

    def get_claims_by_uuid(self, uuids: list[str]) -> list[dict[str, Any]]:
        if not uuids:
            return []
        placeholders = ",".join("?" * len(uuids))
        sql = (
            "SELECT id, uuid, media_id, chunk_index, claim_text, reviewer_id, review_group "  # nosec B608
            f"FROM Claims WHERE uuid IN ({placeholders})"
        )
        rows = self.execute_query(sql, tuple(uuids)).fetchall()
        return [dict(row) for row in rows]

    def get_claim_clusters_by_ids(self, cluster_ids: list[int]) -> list[dict[str, Any]]:
        if not cluster_ids:
            return []
        placeholders = ",".join("?" * len(cluster_ids))
        sql = (
            "SELECT id, canonical_claim_text, updated_at "  # nosec B608
            f"FROM claim_clusters WHERE id IN ({placeholders})"
        )
        rows = self.execute_query(sql, tuple(int(cid) for cid in cluster_ids)).fetchall()
        return [dict(row) for row in rows]

    def get_claim_cluster_member_counts(self, cluster_ids: list[int]) -> dict[int, int]:
        if not cluster_ids:
            return {}
        placeholders = ",".join("?" * len(cluster_ids))
        sql = (
            "SELECT cluster_id, COUNT(*) AS member_count "  # nosec B608
            f"FROM claim_cluster_membership WHERE cluster_id IN ({placeholders}) "
            "GROUP BY cluster_id"
        )
        rows = self.execute_query(sql, tuple(int(cid) for cid in cluster_ids)).fetchall()
        counts: dict[int, int] = {}
        for row in rows:
            try:
                counts[int(row[0])] = int(row[1])
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                continue
        return counts

    def update_claim_clusters_watchlist_counts(self, counts: dict[int, int]) -> int:
        if not counts:
            return 0
        params = [(int(count), int(cluster_id)) for cluster_id, count in counts.items()]
        self.execute_many(
            "UPDATE claim_clusters SET watchlist_count = ? WHERE id = ?",
            params,
        )
        return len(params)

    def insert_claims_monitoring_event(
        self,
        *,
        user_id: str,
        event_type: str,
        severity: str | None = None,
        payload_json: str | None = None,
    ) -> None:
        now = self._get_current_utc_timestamp_str()
        self.execute_query(
            (
                "INSERT INTO claims_monitoring_events "
                "(user_id, event_type, severity, payload_json, created_at, delivered_at) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
            (
                str(user_id),
                str(event_type),
                severity,
                payload_json,
                now,
                None,
            ),
            commit=True,
        )

    def list_claims_monitoring_events(
        self,
        *,
        user_id: str,
        event_type: str | None = None,
        severity: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = ["user_id = ?"]
        params: list[Any] = [str(user_id)]
        if event_type:
            conditions.append("event_type = ?")
            params.append(str(event_type))
        if severity:
            conditions.append("severity = ?")
            params.append(str(severity))
        if start_time:
            conditions.append("created_at >= ?")
            params.append(str(start_time))
        if end_time:
            conditions.append("created_at <= ?")
            params.append(str(end_time))
        where_clause = " AND ".join(conditions)
        rows = self.execute_query(
            (
                "SELECT id, user_id, event_type, severity, payload_json, created_at, delivered_at "  # nosec B608
                "FROM claims_monitoring_events WHERE "
                + where_clause
                + " ORDER BY created_at ASC"
            ),
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_undelivered_claims_monitoring_events(
        self,
        *,
        user_id: str,
        event_type: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 500
        limit = max(1, min(5000, limit))
        conditions: list[str] = ["user_id = ?", "delivered_at IS NULL"]
        params: list[Any] = [str(user_id)]
        if event_type:
            conditions.append("event_type = ?")
            params.append(str(event_type))
        sql = (
            "SELECT id, user_id, event_type, severity, payload_json, created_at, delivered_at "  # nosec B608
            "FROM claims_monitoring_events WHERE "
            + " AND ".join(conditions)
            + " ORDER BY created_at ASC LIMIT ?"
        )
        params.append(limit)
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def mark_claims_monitoring_events_delivered(self, ids: list[int]) -> int:
        if not ids:
            return 0
        placeholders = ",".join("?" * len(ids))
        now = self._get_current_utc_timestamp_str()
        sql = f"UPDATE claims_monitoring_events SET delivered_at = ? WHERE id IN ({placeholders})"  # nosec B608
        params: list[Any] = [str(now)]
        params.extend([int(i) for i in ids])
        cursor = self.execute_query(sql, tuple(params), commit=True)
        try:
            return int(getattr(cursor, "rowcount", 0) or 0)
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            return 0

    def get_latest_claims_monitoring_event_delivery(
        self,
        *,
        user_id: str,
        event_type: str | None = None,
    ) -> str | None:
        conditions: list[str] = ["user_id = ?", "delivered_at IS NOT NULL"]
        params: list[Any] = [str(user_id)]
        if event_type:
            conditions.append("event_type = ?")
            params.append(str(event_type))
        sql = (
            "SELECT MAX(delivered_at) AS delivered_at "  # nosec B608
            "FROM claims_monitoring_events WHERE "
            + " AND ".join(conditions)
        )
        row = self.execute_query(sql, tuple(params)).fetchone()
        if not row:
            return None
        try:
            return row.get("delivered_at")
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            try:
                return row[0]
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                return None

    def list_claims_monitoring_user_ids(self) -> list[str]:
        rows = self.execute_query(
            (
                "SELECT DISTINCT user_id FROM claims_monitoring_alerts "
                "UNION SELECT DISTINCT user_id FROM claims_monitoring_settings"
            ),
            (),
        ).fetchall()
        user_ids: list[str] = []
        for row in rows:
            try:
                user_ids.append(str(row["user_id"]))
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                try:
                    user_ids.append(str(row[0]))
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    continue
        return [uid for uid in user_ids if uid]

    def list_claims_review_user_ids(self) -> list[str]:
        """Return distinct user IDs with review log activity (Postgres only)."""
        if self.backend_type != BackendType.POSTGRESQL:
            return []
        rows = self.execute_query(
            (
                "SELECT DISTINCT COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) AS user_id "
                "FROM claims_review_log l "
                "LEFT JOIN claims c ON c.id = l.claim_id "
                "LEFT JOIN media m ON m.id = c.media_id"
            ),
            (),
        ).fetchall()
        user_ids: list[str] = []
        for row in rows:
            try:
                user_id = row["user_id"]
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                try:
                    user_id = row[0]
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    user_id = None
            if user_id is None:
                continue
            user_ids.append(str(user_id))
        return [uid for uid in user_ids if uid]

    def get_claims_monitoring_health(self, user_id: str) -> dict[str, Any]:
        row = self.execute_query(
            "SELECT id, user_id, queue_size, worker_count, last_worker_heartbeat, last_processed_at, "
            "last_failure_at, last_failure_reason, updated_at "
            "FROM claims_monitoring_health WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
            (str(user_id),),
        ).fetchone()
        return dict(row) if row else {}

    def upsert_claims_monitoring_health(
        self,
        *,
        user_id: str,
        queue_size: int,
        worker_count: int | None = None,
        last_worker_heartbeat: str | None = None,
        last_processed_at: str | None = None,
        last_failure_at: str | None = None,
        last_failure_reason: str | None = None,
    ) -> dict[str, Any]:
        now = self._get_current_utc_timestamp_str()
        existing = self.execute_query(
            "SELECT id FROM claims_monitoring_health WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
            (str(user_id),),
        ).fetchone()
        existing_id: int | None = None
        if existing is not None:
            try:
                existing_id = int(existing["id"])
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                try:
                    existing_id = int(existing[0])
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    existing_id = None
        if existing_id is None:
            self.execute_query(
                (
                    "INSERT INTO claims_monitoring_health "
                    "(user_id, queue_size, worker_count, last_worker_heartbeat, last_processed_at, "
                    "last_failure_at, last_failure_reason, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                (
                    str(user_id),
                    int(queue_size),
                    worker_count,
                    last_worker_heartbeat,
                    last_processed_at,
                    last_failure_at,
                    last_failure_reason,
                    now,
                ),
                commit=True,
            )
            return self.get_claims_monitoring_health(str(user_id))

        self.execute_query(
            (
                "UPDATE claims_monitoring_health SET "
                "queue_size = ?, worker_count = ?, last_worker_heartbeat = ?, last_processed_at = ?, "
                "last_failure_at = ?, last_failure_reason = ?, updated_at = ? "
                "WHERE id = ?"
            ),
            (
                int(queue_size),
                worker_count,
                last_worker_heartbeat,
                last_processed_at,
                last_failure_at,
                last_failure_reason,
                now,
                int(existing_id),
            ),
            commit=True,
        )
        return self.get_claims_monitoring_health(str(user_id))

    def create_claims_analytics_export(
        self,
        *,
        export_id: str,
        user_id: str,
        format: str,
        status: str,
        payload_json: str | None = None,
        payload_csv: str | None = None,
        filters_json: str | None = None,
        pagination_json: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        now = self._get_current_utc_timestamp_str()
        self.execute_query(
            (
                "INSERT INTO claims_analytics_exports "
                "(export_id, user_id, format, status, payload_json, payload_csv, filters_json, "
                "pagination_json, error_message, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                str(export_id),
                str(user_id),
                str(format),
                str(status),
                payload_json,
                payload_csv,
                filters_json,
                pagination_json,
                error_message,
                now,
                now,
            ),
            commit=True,
        )
        return self.get_claims_analytics_export(export_id, user_id=str(user_id))

    def create_tts_history_entry(
        self,
        *,
        user_id: str,
        text_hash: str,
        created_at: str | None = None,
        text: str | None = None,
        text_length: int | None = None,
        provider: str | None = None,
        model: str | None = None,
        voice_id: str | None = None,
        voice_name: str | None = None,
        voice_info: dict[str, Any] | None = None,
        format: str | None = None,
        duration_ms: int | None = None,
        generation_time_ms: int | None = None,
        params_json: dict[str, Any] | None = None,
        status: str | None = None,
        segments_json: dict[str, Any] | None = None,
        favorite: bool = False,
        job_id: int | None = None,
        output_id: int | None = None,
        artifact_ids: list[Any] | None = None,
        artifact_deleted_at: str | None = None,
        error_message: str | None = None,
        deleted: bool = False,
        deleted_at: str | None = None,
        conn: Any | None = None,
    ) -> int | None:
        """Insert a TTS history row and return its id."""
        now = created_at or self._get_current_utc_timestamp_str()
        insert_sql = (
            "INSERT INTO tts_history "
            "(user_id, created_at, text, text_hash, text_length, provider, model, voice_id, voice_name, "
            "voice_info, format, duration_ms, generation_time_ms, params_json, status, segments_json, "
            "favorite, job_id, output_id, artifact_ids, artifact_deleted_at, error_message, deleted, deleted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        if self.backend_type == BackendType.POSTGRESQL:
            insert_sql += " RETURNING id"

        voice_info_str = json.dumps(voice_info, separators=(",", ":"), ensure_ascii=True) if voice_info else None
        params_str = json.dumps(params_json, separators=(",", ":"), ensure_ascii=True) if params_json else None
        segments_str = json.dumps(segments_json, separators=(",", ":"), ensure_ascii=True) if segments_json else None
        artifacts_str = json.dumps(artifact_ids, separators=(",", ":"), ensure_ascii=True) if artifact_ids else None

        cursor = self.execute_query(
            insert_sql,
            (
                str(user_id),
                now,
                text,
                str(text_hash),
                int(text_length) if text_length is not None else None,
                provider,
                model,
                voice_id,
                voice_name,
                voice_info_str,
                format,
                int(duration_ms) if duration_ms is not None else None,
                int(generation_time_ms) if generation_time_ms is not None else None,
                params_str,
                status,
                segments_str,
                1 if favorite else 0,
                int(job_id) if job_id is not None else None,
                int(output_id) if output_id is not None else None,
                artifacts_str,
                artifact_deleted_at,
                error_message,
                1 if deleted else 0,
                deleted_at,
            ),
            commit=True,
            connection=conn,
        )
        if self.backend_type == BackendType.POSTGRESQL:
            row = cursor.fetchone()
            return int(row["id"]) if row and row.get("id") is not None else None
        return cursor.lastrowid

    def _build_tts_history_filters(
        self,
        *,
        user_id: str,
        q: str | None = None,
        text_hash: str | None = None,
        favorite: bool | None = None,
        provider: str | None = None,
        model: str | None = None,
        voice_id: str | None = None,
        voice_name: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        cursor_created_at: str | None = None,
        cursor_id: int | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[str], list[Any]]:
        conditions: list[str] = ["user_id = ?"]
        params: list[Any] = [str(user_id)]

        if not include_deleted:
            conditions.append("deleted = 0")
        if favorite is not None:
            conditions.append("favorite = ?")
            params.append(1 if favorite else 0)
        if provider:
            conditions.append("provider = ?")
            params.append(str(provider))
        if model:
            conditions.append("model = ?")
            params.append(str(model))
        if voice_id:
            conditions.append("voice_id = ?")
            params.append(str(voice_id))
        if voice_name:
            conditions.append("voice_name = ?")
            params.append(str(voice_name))
        if text_hash:
            conditions.append("text_hash = ?")
            params.append(str(text_hash))
        if created_from:
            conditions.append("created_at >= ?")
            params.append(str(created_from))
        if created_to:
            conditions.append("created_at <= ?")
            params.append(str(created_to))
        if q:
            pattern = f"%{q}%"
            self._append_case_insensitive_like(conditions, params, "text", pattern)
        if cursor_created_at and cursor_id is not None:
            conditions.append("(created_at < ? OR (created_at = ? AND id < ?))")
            params.extend([str(cursor_created_at), str(cursor_created_at), int(cursor_id)])

        return conditions, params

    def list_tts_history(
        self,
        *,
        user_id: str,
        q: str | None = None,
        text_hash: str | None = None,
        favorite: bool | None = None,
        provider: str | None = None,
        model: str | None = None,
        voice_id: str | None = None,
        voice_name: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        cursor_created_at: str | None = None,
        cursor_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            limit, offset = 50, 0
        # Allow a single-row overfetch for cursor pagination detection.
        limit = max(1, min(201, limit))
        offset = max(0, offset)

        conditions, params = self._build_tts_history_filters(
            user_id=user_id,
            q=q,
            text_hash=text_hash,
            favorite=favorite,
            provider=provider,
            model=model,
            voice_id=voice_id,
            voice_name=voice_name,
            created_from=created_from,
            created_to=created_to,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
            include_deleted=False,
        )

        query = (
            "SELECT id, user_id, created_at, text, provider, model, voice_id, voice_name, "  # nosec B608
            "voice_info, format, duration_ms, status, favorite, job_id, output_id, "
            "artifact_deleted_at "
            "FROM tts_history WHERE "
            + " AND ".join(conditions)
            + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self.execute_query(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def count_tts_history(
        self,
        *,
        user_id: str,
        q: str | None = None,
        text_hash: str | None = None,
        favorite: bool | None = None,
        provider: str | None = None,
        model: str | None = None,
        voice_id: str | None = None,
        voice_name: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> int:
        conditions, params = self._build_tts_history_filters(
            user_id=user_id,
            q=q,
            text_hash=text_hash,
            favorite=favorite,
            provider=provider,
            model=model,
            voice_id=voice_id,
            voice_name=voice_name,
            created_from=created_from,
            created_to=created_to,
            include_deleted=False,
        )
        query = "SELECT COUNT(*) AS count FROM tts_history WHERE " + " AND ".join(conditions)  # nosec B608
        row = self.execute_query(query, tuple(params)).fetchone()
        if not row:
            return 0
        try:
            return int(row["count"])
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            return int(list(row)[0])

    def get_tts_history_entry(
        self,
        *,
        user_id: str,
        history_id: int,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None:
        conditions = ["id = ?", "user_id = ?"]
        params: list[Any] = [int(history_id), str(user_id)]
        if not include_deleted:
            conditions.append("deleted = 0")
        query = (
            "SELECT id, user_id, created_at, text, text_hash, text_length, provider, model, "  # nosec B608
            "voice_id, voice_name, voice_info, format, duration_ms, generation_time_ms, "
            "params_json, status, segments_json, favorite, job_id, output_id, artifact_ids, "
            "artifact_deleted_at, error_message, deleted, deleted_at "
            "FROM tts_history WHERE "
            + " AND ".join(conditions)
            + " LIMIT 1"
        )
        row = self.execute_query(query, tuple(params)).fetchone()
        return dict(row) if row else None

    def update_tts_history_favorite(
        self,
        *,
        user_id: str,
        history_id: int,
        favorite: bool,
    ) -> bool:
        cursor = self.execute_query(
            "UPDATE tts_history SET favorite = ? WHERE id = ? AND user_id = ? AND deleted = 0",
            (1 if favorite else 0, int(history_id), str(user_id)),
            commit=True,
        )
        try:
            return cursor.rowcount > 0
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            return False

    def soft_delete_tts_history_entry(
        self,
        *,
        user_id: str,
        history_id: int,
        deleted_at: str | None = None,
    ) -> bool:
        ts = deleted_at or self._get_current_utc_timestamp_str()
        cursor = self.execute_query(
            "UPDATE tts_history SET deleted = 1, deleted_at = ? WHERE id = ? AND user_id = ? AND deleted = 0",
            (ts, int(history_id), str(user_id)),
            commit=True,
        )
        try:
            return cursor.rowcount > 0
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            return False

    def mark_tts_history_artifacts_deleted_for_output(
        self,
        *,
        user_id: str,
        output_id: int,
        deleted_at: str | None = None,
    ) -> int:
        ts = deleted_at or self._get_current_utc_timestamp_str()
        cursor = self.execute_query(
            (
                "UPDATE tts_history "
                "SET artifact_deleted_at = ?, output_id = NULL, artifact_ids = NULL "
                "WHERE user_id = ? AND output_id = ? AND deleted = 0"
            ),
            (ts, str(user_id), int(output_id)),
            commit=True,
        )
        try:
            return int(cursor.rowcount or 0)
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            return 0

    def mark_tts_history_artifacts_deleted_for_file_id(
        self,
        *,
        user_id: str,
        file_id: int,
        deleted_at: str | None = None,
    ) -> int:
        ts = deleted_at or self._get_current_utc_timestamp_str()
        rows = self.execute_query(
            (
                "SELECT id, artifact_ids FROM tts_history "
                "WHERE user_id = ? AND artifact_ids IS NOT NULL AND deleted = 0"
            ),
            (str(user_id),),
        ).fetchall()
        if not rows:
            return 0

        matched_ids: list[int] = []
        for row in rows:
            raw = row["artifact_ids"]
            if raw is None:
                continue
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                parsed = None
            if isinstance(parsed, list) and file_id in parsed:
                matched_ids.append(int(row["id"]))

        if not matched_ids:
            return 0

        placeholders = ",".join(["?"] * len(matched_ids))
        params: list[Any] = [ts, str(user_id)] + matched_ids
        cursor = self.execute_query(
            (
                "UPDATE tts_history "  # nosec B608
                "SET artifact_deleted_at = ?, output_id = NULL, artifact_ids = NULL "
                f"WHERE user_id = ? AND id IN ({placeholders}) AND deleted = 0"
            ),
            tuple(params),
            commit=True,
        )
        try:
            return int(cursor.rowcount or 0)
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            return len(matched_ids)

    def purge_tts_history_for_user(
        self,
        *,
        user_id: str,
        retention_days: int,
        max_rows: int,
    ) -> int:
        removed = 0
        if retention_days and retention_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=int(retention_days))
            cutoff_str = cutoff.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            cursor = self.execute_query(
                "DELETE FROM tts_history WHERE user_id = ? AND created_at < ?",
                (str(user_id), cutoff_str),
                commit=True,
            )
            with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                removed += int(cursor.rowcount or 0)

        if max_rows and max_rows > 0:
            row = self.execute_query(
                "SELECT COUNT(*) AS count FROM tts_history WHERE user_id = ?",
                (str(user_id),),
            ).fetchone()
            if row:
                try:
                    total = int(row["count"])
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    total = int(list(row)[0])
                if total > max_rows:
                    to_remove = total - int(max_rows)
                    cursor = self.execute_query(
                        (
                            "DELETE FROM tts_history WHERE user_id = ? AND id IN ("
                            "SELECT id FROM tts_history WHERE user_id = ? "
                            "ORDER BY created_at ASC, id ASC LIMIT ?"
                            ")"
                        ),
                        (str(user_id), str(user_id), int(to_remove)),
                        commit=True,
                    )
                    try:
                        removed += int(cursor.rowcount or 0)
                    except _MEDIA_NONCRITICAL_EXCEPTIONS:
                        removed += max(0, to_remove)

        return removed

    def list_tts_history_user_ids(self) -> list[str]:
        rows = self.execute_query(
            "SELECT DISTINCT user_id FROM tts_history",
            None,
        ).fetchall()
        user_ids: list[str] = []
        for row in rows:
            try:
                user_ids.append(str(row["user_id"]))
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                try:
                    user_ids.append(str(row[0]))
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    continue
        return user_ids

    def get_claims_analytics_export(
        self,
        export_id: str,
        *,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        params: list[Any] = [str(export_id)]
        conditions = ["export_id = ?"]
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(str(user_id))
        row = self.execute_query(
            (
                "SELECT export_id, user_id, format, status, payload_json, payload_csv, filters_json, "  # nosec B608
                "pagination_json, error_message, created_at, updated_at "
                "FROM claims_analytics_exports WHERE "
                + " AND ".join(conditions)
                + " LIMIT 1"
            ),
            tuple(params),
        ).fetchone()
        return dict(row) if row else {}

    def list_claims_analytics_exports(
        self,
        user_id: str,
        *,
        status: str | None = None,
        format: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            limit, offset = 100, 0
        limit = max(1, min(1000, limit))
        offset = max(0, offset)
        conditions = ["user_id = ?"]
        params: list[Any] = [str(user_id)]
        if status:
            conditions.append("status = ?")
            params.append(str(status))
        if format:
            conditions.append("format = ?")
            params.append(str(format))
        query = (
            "SELECT export_id, user_id, format, status, filters_json, pagination_json, error_message, "  # nosec B608
            "created_at, updated_at "
            "FROM claims_analytics_exports WHERE "
            + " AND ".join(conditions)
            + " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self.execute_query(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def count_claims_analytics_exports(
        self,
        user_id: str,
        *,
        status: str | None = None,
        format: str | None = None,
    ) -> int:
        conditions = ["user_id = ?"]
        params: list[Any] = [str(user_id)]
        if status:
            conditions.append("status = ?")
            params.append(str(status))
        if format:
            conditions.append("format = ?")
            params.append(str(format))
        row = self.execute_query(
            "SELECT COUNT(*) AS count FROM claims_analytics_exports WHERE " + " AND ".join(conditions),  # nosec B608
            tuple(params),
        ).fetchone()
        if not row:
            return 0
        try:
            return int(row["count"] or 0)
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            try:
                return int(row[0] or 0)
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                return 0

    def cleanup_claims_analytics_exports(
        self,
        *,
        user_id: str,
        retention_hours: float,
    ) -> int:
        try:
            retention_hours = float(retention_hours)
        except (TypeError, ValueError):
            return 0
        if retention_hours <= 0:
            return 0
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=retention_hours)
        ).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        cursor = self.execute_query(
            "DELETE FROM claims_analytics_exports WHERE user_id = ? AND created_at < ?",
            (str(user_id), cutoff),
            commit=True,
        )
        try:
            deleted = int(cursor.rowcount or 0)
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            deleted = 0
        return max(deleted, 0)

    def list_claim_clusters(
        self,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        updated_since: str | None = None,
        keyword: str | None = None,
        min_size: int | None = None,
        watchlisted: bool | None = None,
    ) -> list[dict[str, Any]]:
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            limit, offset = 100, 0
        limit = max(1, min(1000, limit))
        offset = max(0, offset)
        conditions: list[str] = ["c.user_id = ?"]
        params: list[Any] = [str(user_id)]
        if updated_since:
            conditions.append("c.updated_at >= ?")
            params.append(str(updated_since))
        if keyword:
            conditions.append("(c.canonical_claim_text LIKE ? OR c.summary LIKE ?)")
            like = f"%{keyword}%"
            params.extend([like, like])
        if watchlisted is not None:
            if watchlisted:
                conditions.append("c.watchlist_count > 0")
            else:
                conditions.append("c.watchlist_count = 0")
        if min_size is not None:
            conditions.append("COALESCE(m.member_count, 0) >= ?")
            params.append(int(min_size))

        sql = (
            "SELECT c.id, c.user_id, c.canonical_claim_text, c.representative_claim_id, c.summary, "  # nosec B608
            "c.cluster_version, c.watchlist_count, c.created_at, c.updated_at, "
            "COALESCE(m.member_count, 0) AS member_count "
            "FROM claim_clusters c "
            "LEFT JOIN (SELECT cluster_id, COUNT(*) AS member_count "
            "FROM claim_cluster_membership GROUP BY cluster_id) m "
            "ON m.cluster_id = c.id "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY c.updated_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_claim_cluster(self, cluster_id: int) -> dict[str, Any]:
        row = self.execute_query(
            "SELECT id, user_id, canonical_claim_text, representative_claim_id, summary, "
            "cluster_version, watchlist_count, created_at, updated_at "
            "FROM claim_clusters WHERE id = ?",
            (int(cluster_id),),
        ).fetchone()
        return dict(row) if row else {}

    def get_claim_cluster_link(
        self,
        *,
        parent_cluster_id: int,
        child_cluster_id: int,
    ) -> dict[str, Any]:
        row = self.execute_query(
            (
                "SELECT parent_cluster_id, child_cluster_id, relation_type, created_at "
                "FROM claim_cluster_links WHERE parent_cluster_id = ? AND child_cluster_id = ?"
            ),
            (int(parent_cluster_id), int(child_cluster_id)),
        ).fetchone()
        return dict(row) if row else {}

    def list_claim_cluster_links(
        self,
        *,
        cluster_id: int,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        direction_norm = str(direction or "both").lower()
        conditions: list[str] = []
        params: list[Any] = []
        if direction_norm in {"outbound", "parent"}:
            conditions.append("parent_cluster_id = ?")
            params.append(int(cluster_id))
        elif direction_norm in {"inbound", "child"}:
            conditions.append("child_cluster_id = ?")
            params.append(int(cluster_id))
        else:
            conditions.append("(parent_cluster_id = ? OR child_cluster_id = ?)")
            params.extend([int(cluster_id), int(cluster_id)])
        rows = self.execute_query(
            (
                "SELECT parent_cluster_id, child_cluster_id, relation_type, created_at "  # nosec B608
                "FROM claim_cluster_links WHERE "
                + " AND ".join(conditions)
                + " ORDER BY created_at DESC"
            ),
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]

    def create_claim_cluster_link(
        self,
        *,
        parent_cluster_id: int,
        child_cluster_id: int,
        relation_type: str | None = None,
    ) -> dict[str, Any]:
        now = self._get_current_utc_timestamp_str()
        self.execute_query(
            (
                "INSERT INTO claim_cluster_links "
                "(parent_cluster_id, child_cluster_id, relation_type, created_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING"
            ),
            (
                int(parent_cluster_id),
                int(child_cluster_id),
                relation_type,
                now,
            ),
            commit=True,
        )
        return self.get_claim_cluster_link(
            parent_cluster_id=parent_cluster_id,
            child_cluster_id=child_cluster_id,
        )

    def delete_claim_cluster_link(
        self,
        *,
        parent_cluster_id: int,
        child_cluster_id: int,
    ) -> int:
        cur = self.execute_query(
            (
                "DELETE FROM claim_cluster_links "
                "WHERE parent_cluster_id = ? AND child_cluster_id = ?"
            ),
            (int(parent_cluster_id), int(child_cluster_id)),
            commit=True,
        )
        try:
            deleted = int(cur.rowcount or 0)
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            deleted = 0
        return max(deleted, 0)

    def list_claim_cluster_members(
        self,
        cluster_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            limit, offset = 100, 0
        limit = max(1, min(1000, limit))
        offset = max(0, offset)
        conditions: list[str] = ["cm.cluster_id = ?", "c.media_id = m.id"]
        params: list[Any] = [int(cluster_id)]

        try:
            scope = get_scope()
        except _MEDIA_NONCRITICAL_EXCEPTIONS as scope_err:
            logging.debug(f"Failed to resolve scope for cluster membership visibility filter: {scope_err}")
            scope = None
        if scope and not scope.is_admin:
            visibility_parts: list[str] = []
            user_id_str = str(scope.user_id) if scope.user_id is not None else ""
            if user_id_str:
                visibility_parts.append(
                    "(COALESCE(m.visibility, 'personal') = 'personal' "
                    "AND (COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?))"
                )
                params.append(user_id_str)
            if scope.team_ids:
                team_placeholders = ",".join("?" * len(scope.team_ids))
                visibility_parts.append(
                    f"(m.visibility = 'team' AND m.team_id IN ({team_placeholders}))"
                )
                params.extend(scope.team_ids)
            if scope.org_ids:
                org_placeholders = ",".join("?" * len(scope.org_ids))
                visibility_parts.append(
                    f"(m.visibility = 'org' AND m.org_id IN ({org_placeholders}))"
                )
                params.extend(scope.org_ids)

            if visibility_parts:
                conditions.append(f"({' OR '.join(visibility_parts)})")
            else:
                conditions.append("(0 = 1)")

        sql = (
            "SELECT c.id, c.media_id, c.chunk_index, c.span_start, c.span_end, c.claim_text, "  # nosec B608
            "c.confidence, c.extractor, c.extractor_version, c.chunk_hash, c.created_at, c.uuid, "
            "c.last_modified, c.version, c.client_id, c.deleted, "
            "c.review_status, c.reviewer_id, c.review_group, c.reviewed_at, "
            "c.review_notes, c.review_version, c.review_reason_code, c.claim_cluster_id, "
            "m.title AS media_title, m.visibility AS media_visibility, "
            "m.owner_user_id AS media_owner_user_id, m.org_id AS media_org_id, "
            "m.team_id AS media_team_id, m.client_id AS media_client_id, "
            "cm.similarity_score, cm.cluster_joined_at "
            "FROM claim_cluster_membership cm "
            "JOIN Claims c ON c.id = cm.claim_id "
            "JOIN Media m ON c.media_id = m.id "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY cm.cluster_joined_at DESC "
            "LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def create_claim_cluster(
        self,
        *,
        user_id: str,
        canonical_claim_text: str | None = None,
        representative_claim_id: int | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        now = self._get_current_utc_timestamp_str()
        insert_sql = (
            "INSERT INTO claim_clusters "
            "(user_id, canonical_claim_text, representative_claim_id, summary, "
            "cluster_version, watchlist_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
        if self.backend_type == BackendType.POSTGRESQL:
            insert_sql += " RETURNING id"
        cursor = self.execute_query(
            insert_sql,
            (
                str(user_id),
                canonical_claim_text,
                int(representative_claim_id) if representative_claim_id is not None else None,
                summary,
                1,
                0,
                now,
                now,
            ),
            commit=True,
        )
        if self.backend_type == BackendType.POSTGRESQL:
            row = cursor.fetchone()
            cluster_id = int(row["id"]) if row else None
        else:
            cluster_id = cursor.lastrowid
        return self.get_claim_cluster(cluster_id) if cluster_id else {}

    def add_claim_to_cluster(
        self,
        *,
        cluster_id: int,
        claim_id: int,
        similarity_score: float | None = None,
    ) -> None:
        now = self._get_current_utc_timestamp_str()
        with self.transaction() as conn:
            self._execute_with_connection(
                conn,
                (
                    "INSERT INTO claim_cluster_membership "
                    "(cluster_id, claim_id, similarity_score, cluster_joined_at) "
                    "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING"
                ),
                (int(cluster_id), int(claim_id), similarity_score, now),
            )
            self._execute_with_connection(
                conn,
                "UPDATE Claims SET claim_cluster_id = ? WHERE id = ?",
                (int(cluster_id), int(claim_id)),
            )
            self._execute_with_connection(
                conn,
                "UPDATE claim_clusters SET cluster_version = cluster_version + 1, updated_at = ? WHERE id = ?",
                (now, int(cluster_id)),
            )

    def rebuild_claim_clusters_exact(
        self,
        *,
        user_id: str,
        min_size: int = 2,
    ) -> dict[str, int]:
        """Rebuild clusters by exact normalized claim text."""
        try:
            min_size = int(min_size)
        except (TypeError, ValueError):
            min_size = 2
        min_size = max(1, min_size)

        clusters_created = 0
        claims_assigned = 0

        with self.transaction() as conn:
            cluster_rows = self._fetchall_with_connection(
                conn,
                "SELECT id FROM claim_clusters WHERE user_id = ?",
                (str(user_id),),
            )
            cluster_ids = [int(r["id"]) for r in cluster_rows if r.get("id") is not None]
            if cluster_ids:
                placeholders = ",".join("?" * len(cluster_ids))
                params = tuple(cluster_ids)
                self._execute_with_connection(
                    conn,
                    f"DELETE FROM claim_cluster_membership WHERE cluster_id IN ({placeholders})",  # nosec B608
                    params,
                )
                self._execute_with_connection(
                    conn,
                    f"UPDATE Claims SET claim_cluster_id = NULL WHERE claim_cluster_id IN ({placeholders})",  # nosec B608
                    params,
                )
                self._execute_with_connection(
                    conn,
                    f"DELETE FROM claim_clusters WHERE id IN ({placeholders})",  # nosec B608
                    params,
                )

            rows = self._fetchall_with_connection(
                conn,
                (
                    "SELECT c.id, c.claim_text FROM Claims c "
                    "JOIN Media m ON c.media_id = m.id "
                    "WHERE c.deleted = 0 AND COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?"
                ),
                (str(user_id),),
            )

            groups: dict[str, list[dict[str, Any]]] = {}
            for r in rows:
                text = str(r.get("claim_text") or "").strip()
                if not text:
                    continue
                norm = " ".join(text.lower().split())
                groups.setdefault(norm, []).append({"id": int(r["id"]), "text": text})

            for claims in groups.values():
                if len(claims) < min_size:
                    continue
                rep = claims[0]
                now = self._get_current_utc_timestamp_str()
                insert_sql = (
                    "INSERT INTO claim_clusters "
                    "(user_id, canonical_claim_text, representative_claim_id, summary, "
                    "cluster_version, watchlist_count, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                )
                if self.backend_type == BackendType.POSTGRESQL:
                    insert_sql += " RETURNING id"
                cursor = self._execute_with_connection(
                    conn,
                    insert_sql,
                    (
                        str(user_id),
                        rep["text"],
                        rep["id"],
                        None,
                        1,
                        0,
                        now,
                        now,
                    ),
                )
                if self.backend_type == BackendType.POSTGRESQL:
                    inserted = cursor.fetchone()
                    cluster_id = inserted["id"] if inserted else None
                else:
                    cluster_id = cursor.lastrowid
                if not cluster_id:
                    continue
                clusters_created += 1
                for item in claims:
                    self._execute_with_connection(
                        conn,
                        (
                            "INSERT INTO claim_cluster_membership "
                            "(cluster_id, claim_id, similarity_score, cluster_joined_at) "
                            "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING"
                        ),
                        (int(cluster_id), int(item["id"]), 1.0, now),
                    )
                    self._execute_with_connection(
                        conn,
                        "UPDATE Claims SET claim_cluster_id = ? WHERE id = ?",
                        (int(cluster_id), int(item["id"])),
                    )
                    claims_assigned += 1
                self._execute_with_connection(
                    conn,
                    "UPDATE claim_clusters SET cluster_version = cluster_version + 1, updated_at = ? WHERE id = ?",
                    (now, int(cluster_id)),
                )

        return {
            "clusters_created": clusters_created,
            "claims_assigned": claims_assigned,
        }

    def rebuild_claim_clusters_from_assignments(
        self,
        *,
        user_id: str,
        clusters: list[dict[str, Any]],
    ) -> dict[str, int]:
        """
        Rebuild clusters from precomputed assignments.

        Each cluster entry should include:
          - canonical_claim_text
          - representative_claim_id
          - members: list of {claim_id, similarity}
        """
        clusters_created = 0
        claims_assigned = 0
        now = self._get_current_utc_timestamp_str()

        with self.transaction() as conn:
            cluster_rows = self._fetchall_with_connection(
                conn,
                "SELECT id FROM claim_clusters WHERE user_id = ?",
                (str(user_id),),
            )
            cluster_ids = [int(r["id"]) for r in cluster_rows if r.get("id") is not None]
            if cluster_ids:
                placeholders = ",".join("?" * len(cluster_ids))
                params = tuple(cluster_ids)
                self._execute_with_connection(
                    conn,
                    f"DELETE FROM claim_cluster_membership WHERE cluster_id IN ({placeholders})",  # nosec B608
                    params,
                )
                self._execute_with_connection(
                    conn,
                    f"DELETE FROM claim_clusters WHERE id IN ({placeholders})",  # nosec B608
                    params,
                )

            self._execute_with_connection(
                conn,
                (
                    "UPDATE Claims SET claim_cluster_id = NULL "
                    "WHERE id IN ("
                    "SELECT c.id FROM Claims c "
                    "JOIN Media m ON c.media_id = m.id "
                    "WHERE COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?"
                    ")"
                ),
                (str(user_id),),
            )

            membership_sql = (
                "INSERT INTO claim_cluster_membership "
                "(cluster_id, claim_id, similarity_score, cluster_joined_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING"
            )

            for cluster in clusters:
                canonical_text = str(cluster.get("canonical_claim_text") or "")
                rep_id = cluster.get("representative_claim_id")
                insert_sql = (
                    "INSERT INTO claim_clusters "
                    "(user_id, canonical_claim_text, representative_claim_id, summary, "
                    "cluster_version, watchlist_count, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                )
                if self.backend_type == BackendType.POSTGRESQL:
                    insert_sql = (
                        "INSERT INTO claim_clusters "
                        "(user_id, canonical_claim_text, representative_claim_id, summary, "
                        "cluster_version, watchlist_count, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id"
                    )
                cursor = self._execute_with_connection(
                    conn,
                    insert_sql,
                    (
                        str(user_id),
                        canonical_text,
                        int(rep_id) if rep_id is not None else None,
                        None,
                        1,
                        0,
                        now,
                        now,
                    ),
                )
                if self.backend_type == BackendType.POSTGRESQL:
                    inserted = cursor.fetchone()
                    cluster_id = inserted["id"] if inserted else None
                else:
                    cluster_id = cursor.lastrowid
                if not cluster_id:
                    continue
                clusters_created += 1

                members = cluster.get("members") or []
                membership_params: list[tuple] = []
                update_params: list[tuple] = []
                for member in members:
                    claim_id = member.get("claim_id")
                    if claim_id is None:
                        continue
                    similarity = member.get("similarity")
                    membership_params.append(
                        (
                            int(cluster_id),
                            int(claim_id),
                            float(similarity) if similarity is not None else None,
                            now,
                        )
                    )
                    update_params.append((int(cluster_id), int(claim_id)))
                    claims_assigned += 1

                if membership_params:
                    self.execute_many(
                        membership_sql,
                        membership_params,
                        connection=conn,
                    )
                if update_params:
                    self.execute_many(
                        "UPDATE Claims SET claim_cluster_id = ? WHERE id = ?",
                        update_params,
                        connection=conn,
                    )

        return {
            "clusters_created": clusters_created,
            "claims_assigned": claims_assigned,
        }

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
                    with suppress(sqlite3.Error):
                        self._execute_with_connection(
                            conn,
                            "INSERT INTO claims_fts(claims_fts, rowid, claim_text) "
                            "SELECT 'delete', id, claim_text FROM Claims WHERE media_id = ?",
                            (int(media_id),),
                        )

                return affected
        except sqlite3.Error as e:
            logging.error(f"Failed to soft-delete claims for media_id={media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to soft-delete claims: {e}") from e  # noqa: TRY003

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
                        logging.warning("claims_fts table missing during rebuild; recreating. Error: {}", sqlite_err)
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
            raise DatabaseError(f"Failed to rebuild claims_fts: {exc}") from exc  # noqa: TRY003
        except BackendDatabaseError as exc:
            logging.error(f"Failed to rebuild claims_fts (backend): {exc}", exc_info=True)
            raise DatabaseError(f"Failed to rebuild claims_fts: {exc}") from exc  # noqa: TRY003

    def _resolve_email_tenant_id(self, tenant_id: str | None = None) -> str:
        """Resolve tenant scope for email-native tables."""

        explicit = str(tenant_id or "").strip()
        if explicit:
            return explicit
        scope = get_scope()
        if scope is not None:
            if scope.effective_org_id is not None:
                return f"org:{int(scope.effective_org_id)}"
            if scope.user_id is not None:
                return f"user:{int(scope.user_id)}"
        return str(self.client_id)

    @staticmethod
    def _normalize_email_address(value: Any) -> str | None:
        addr = str(value or "").strip().lower()
        return addr if addr and "@" in addr else None

    @staticmethod
    def _parse_email_internal_date(value: Any) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
            dt = parsedate_to_datetime(raw)
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
        return None

    @staticmethod
    def _collect_email_labels(
        metadata: dict[str, Any] | None = None,
        labels: list[str] | str | None = None,
    ) -> list[str]:
        raw_values: list[str] = []
        if isinstance(labels, str):
            raw_values.extend(v.strip() for v in labels.split(","))
        elif isinstance(labels, list):
            raw_values.extend(str(v).strip() for v in labels if v is not None)

        email_meta = (metadata or {}).get("email")
        if isinstance(email_meta, dict):
            meta_labels = email_meta.get("labels")
            if isinstance(meta_labels, str):
                raw_values.extend(v.strip() for v in meta_labels.split(","))
            elif isinstance(meta_labels, list):
                raw_values.extend(str(v).strip() for v in meta_labels if v is not None)

        top_labels = (metadata or {}).get("labels")
        if isinstance(top_labels, str):
            raw_values.extend(v.strip() for v in top_labels.split(","))
        elif isinstance(top_labels, list):
            raw_values.extend(str(v).strip() for v in top_labels if v is not None)

        normalized: list[str] = []
        seen: set[str] = set()
        for value in raw_values:
            label = str(value or "").strip()
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(label)
        return normalized

    def upsert_email_message_graph(
        self,
        *,
        media_id: int,
        metadata: dict[str, Any] | None = None,
        body_text: str | None = None,
        tenant_id: str | None = None,
        provider: str = "upload",
        source_key: str | None = None,
        source_message_id: str | None = None,
        labels: list[str] | str | None = None,
    ) -> dict[str, Any]:
        """
        Upsert a normalized email message graph (message, participants, labels, attachments).

        This is the Stage-1 persistence bridge used by archive/upload ingestion.
        """

        media_id_int = int(media_id)
        if media_id_int <= 0:
            raise InputError("media_id must be a positive integer")  # noqa: TRY003

        metadata_map = metadata if isinstance(metadata, dict) else {}
        email_meta = metadata_map.get("email") if isinstance(metadata_map.get("email"), dict) else {}

        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        resolved_provider = str(provider or "upload").strip() or "upload"
        resolved_source_key = str(
            source_key
            or metadata_map.get("source_key")
            or metadata_map.get("source")
            or metadata_map.get("filename")
            or "upload"
        ).strip() or "upload"
        resolved_source_message_id = str(
            source_message_id
            or email_meta.get("source_message_id")
            or email_meta.get("id")
            or metadata_map.get("source_message_id")
            or ""
        ).strip() or None
        resolved_message_id = str(
            email_meta.get("message_id")
            or metadata_map.get("message_id")
            or ""
        ).strip() or None
        resolved_subject = str(
            email_meta.get("subject")
            or metadata_map.get("title")
            or ""
        ).strip() or None
        resolved_from = str(email_meta.get("from") or "").strip() or None
        resolved_to = str(email_meta.get("to") or "").strip() or None
        resolved_cc = str(email_meta.get("cc") or "").strip() or None
        resolved_bcc = str(email_meta.get("bcc") or "").strip() or None
        resolved_internal_date = self._parse_email_internal_date(
            email_meta.get("date") or metadata_map.get("date")
        )

        attachments_raw = email_meta.get("attachments")
        attachments: list[dict[str, Any]] = (
            [a for a in attachments_raw if isinstance(a, dict)]
            if isinstance(attachments_raw, list)
            else []
        )
        normalized_labels = self._collect_email_labels(metadata_map, labels)
        label_text = ", ".join(normalized_labels) if normalized_labels else None
        has_attachments = bool(attachments)
        raw_metadata_json = json.dumps(metadata_map, ensure_ascii=False) if metadata_map else None

        with self.transaction() as conn:
            self._execute_with_connection(
                conn,
                (
                    "INSERT INTO email_sources "
                    "(tenant_id, provider, source_key, display_name, status) "
                    "VALUES (?, ?, ?, ?, 'active') "
                    "ON CONFLICT(tenant_id, provider, source_key) "
                    "DO UPDATE SET "
                    "display_name = COALESCE(EXCLUDED.display_name, email_sources.display_name), "
                    "updated_at = CURRENT_TIMESTAMP"
                ),
                (
                    resolved_tenant,
                    resolved_provider,
                    resolved_source_key,
                    resolved_source_key,
                ),
            )
            source_row = self._fetchone_with_connection(
                conn,
                (
                    "SELECT id FROM email_sources "
                    "WHERE tenant_id = ? AND provider = ? AND source_key = ? "
                    "LIMIT 1"
                ),
                (resolved_tenant, resolved_provider, resolved_source_key),
            )
            if not source_row:
                raise DatabaseError("Failed to resolve email source after upsert.")  # noqa: TRY003
            source_id = int(source_row["id"])

            existing_message: dict[str, Any] | None = None
            match_strategy = "new"

            if resolved_source_message_id:
                existing_message = self._fetchone_with_connection(
                    conn,
                    (
                        "SELECT id FROM email_messages "
                        "WHERE tenant_id = ? AND source_id = ? AND source_message_id = ? "
                        "LIMIT 1"
                    ),
                    (resolved_tenant, source_id, resolved_source_message_id),
                )
                if existing_message:
                    match_strategy = "source_message_id"

            if existing_message is None and resolved_message_id:
                existing_message = self._fetchone_with_connection(
                    conn,
                    (
                        "SELECT id FROM email_messages "
                        "WHERE tenant_id = ? AND source_id = ? AND message_id = ? "
                        "LIMIT 1"
                    ),
                    (resolved_tenant, source_id, resolved_message_id),
                )
                if existing_message:
                    match_strategy = "message_id"

            if existing_message is None:
                existing_message = self._fetchone_with_connection(
                    conn,
                    "SELECT id FROM email_messages WHERE media_id = ? LIMIT 1",
                    (media_id_int,),
                )
                if existing_message:
                    match_strategy = "media_id"

            if existing_message is not None:
                email_message_id = int(existing_message["id"])
                self._execute_with_connection(
                    conn,
                    (
                        "UPDATE email_messages SET "
                        "media_id = ?, "
                        "source_id = ?, "
                        "source_message_id = ?, "
                        "message_id = ?, "
                        "subject = ?, "
                        "body_text = ?, "
                        "internal_date = ?, "
                        "from_text = ?, "
                        "to_text = ?, "
                        "cc_text = ?, "
                        "bcc_text = ?, "
                        "label_text = ?, "
                        "has_attachments = ?, "
                        "raw_metadata_json = ?, "
                        "updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = ?"
                    ),
                    (
                        media_id_int,
                        source_id,
                        resolved_source_message_id,
                        resolved_message_id,
                        resolved_subject,
                        str(body_text or ""),
                        resolved_internal_date,
                        resolved_from,
                        resolved_to,
                        resolved_cc,
                        resolved_bcc,
                        label_text,
                        bool(has_attachments),
                        raw_metadata_json,
                        email_message_id,
                    ),
                )
            else:
                self._execute_with_connection(
                    conn,
                    (
                        "INSERT INTO email_messages ("
                        "tenant_id, media_id, source_id, source_message_id, message_id, "
                        "subject, body_text, internal_date, from_text, to_text, cc_text, bcc_text, "
                        "label_text, has_attachments, raw_metadata_json"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    ),
                    (
                        resolved_tenant,
                        media_id_int,
                        source_id,
                        resolved_source_message_id,
                        resolved_message_id,
                        resolved_subject,
                        str(body_text or ""),
                        resolved_internal_date,
                        resolved_from,
                        resolved_to,
                        resolved_cc,
                        resolved_bcc,
                        label_text,
                        bool(has_attachments),
                        raw_metadata_json,
                    ),
                )
                inserted_message = self._fetchone_with_connection(
                    conn,
                    (
                        "SELECT id FROM email_messages "
                        "WHERE tenant_id = ? AND media_id = ? LIMIT 1"
                    ),
                    (resolved_tenant, media_id_int),
                )
                if not inserted_message and resolved_source_message_id:
                    inserted_message = self._fetchone_with_connection(
                        conn,
                        (
                            "SELECT id FROM email_messages "
                            "WHERE tenant_id = ? AND source_id = ? AND source_message_id = ? LIMIT 1"
                        ),
                        (resolved_tenant, source_id, resolved_source_message_id),
                    )
                if not inserted_message and resolved_message_id:
                    inserted_message = self._fetchone_with_connection(
                        conn,
                        (
                            "SELECT id FROM email_messages "
                            "WHERE tenant_id = ? AND source_id = ? AND message_id = ? LIMIT 1"
                        ),
                        (resolved_tenant, source_id, resolved_message_id),
                    )
                if not inserted_message:
                    raise DatabaseError("Failed to resolve email message row after insert.")  # noqa: TRY003
                email_message_id = int(inserted_message["id"])

            self._execute_with_connection(
                conn,
                "DELETE FROM email_message_participants WHERE email_message_id = ?",
                (email_message_id,),
            )
            self._execute_with_connection(
                conn,
                "DELETE FROM email_message_labels WHERE email_message_id = ?",
                (email_message_id,),
            )
            self._execute_with_connection(
                conn,
                "DELETE FROM email_attachments WHERE email_message_id = ?",
                (email_message_id,),
            )

            for role_name, value in (
                ("from", resolved_from),
                ("to", resolved_to),
                ("cc", resolved_cc),
                ("bcc", resolved_bcc),
            ):
                role_text = str(value or "").strip()
                if not role_text:
                    continue
                for display_name, email_addr in getaddresses([role_text]):
                    normalized_addr = self._normalize_email_address(email_addr)
                    if not normalized_addr:
                        continue
                    display = str(display_name or "").strip() or None
                    self._execute_with_connection(
                        conn,
                        (
                            "INSERT INTO email_participants (tenant_id, email_normalized, display_name) "
                            "VALUES (?, ?, ?) "
                            "ON CONFLICT(tenant_id, email_normalized) "
                            "DO UPDATE SET display_name = COALESCE(EXCLUDED.display_name, email_participants.display_name)"
                        ),
                        (resolved_tenant, normalized_addr, display),
                    )
                    participant_row = self._fetchone_with_connection(
                        conn,
                        (
                            "SELECT id FROM email_participants "
                            "WHERE tenant_id = ? AND email_normalized = ? LIMIT 1"
                        ),
                        (resolved_tenant, normalized_addr),
                    )
                    if participant_row:
                        self._execute_with_connection(
                            conn,
                            (
                                "INSERT INTO email_message_participants "
                                "(email_message_id, participant_id, role) "
                                "VALUES (?, ?, ?) ON CONFLICT DO NOTHING"
                            ),
                            (
                                email_message_id,
                                int(participant_row["id"]),
                                role_name,
                            ),
                        )

            for label_name in normalized_labels:
                label_key = str(label_name).strip().lower()
                if not label_key:
                    continue
                self._execute_with_connection(
                    conn,
                    (
                        "INSERT INTO email_labels (tenant_id, label_key, label_name) "
                        "VALUES (?, ?, ?) "
                        "ON CONFLICT(tenant_id, label_key) "
                        "DO UPDATE SET label_name = EXCLUDED.label_name, updated_at = CURRENT_TIMESTAMP"
                    ),
                    (resolved_tenant, label_key, label_name),
                )
                label_row = self._fetchone_with_connection(
                    conn,
                    (
                        "SELECT id FROM email_labels "
                        "WHERE tenant_id = ? AND label_key = ? LIMIT 1"
                    ),
                    (resolved_tenant, label_key),
                )
                if label_row:
                    self._execute_with_connection(
                        conn,
                        (
                            "INSERT INTO email_message_labels (email_message_id, label_id) "
                            "VALUES (?, ?) ON CONFLICT DO NOTHING"
                        ),
                        (email_message_id, int(label_row["id"])),
                    )

            for attachment in attachments:
                filename = str(
                    attachment.get("filename")
                    or attachment.get("name")
                    or ""
                ).strip() or None
                content_type = str(attachment.get("content_type") or "").strip() or None
                size_bytes_raw = attachment.get("size_bytes")
                if size_bytes_raw is None:
                    size_bytes_raw = attachment.get("size")
                with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                    size_bytes_raw = int(size_bytes_raw) if size_bytes_raw is not None else None
                if isinstance(size_bytes_raw, bool):
                    size_bytes_raw = None
                size_bytes = size_bytes_raw if isinstance(size_bytes_raw, int) else None
                content_id = str(attachment.get("content_id") or "").strip() or None
                disposition = str(attachment.get("disposition") or "").strip() or None
                extracted_text_available = bool(
                    attachment.get("extracted_text_available")
                    or attachment.get("text_extracted")
                )
                self._execute_with_connection(
                    conn,
                    (
                        "INSERT INTO email_attachments ("
                        "email_message_id, filename, content_type, size_bytes, "
                        "content_id, disposition, extracted_text_available"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?)"
                    ),
                    (
                        email_message_id,
                        filename,
                        content_type,
                        size_bytes,
                        content_id,
                        disposition,
                        bool(extracted_text_available),
                    ),
                )

            if self.backend_type == BackendType.SQLITE:
                with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                    self._execute_with_connection(
                        conn,
                        (
                            "INSERT OR REPLACE INTO email_fts "
                            "(rowid, subject, body_text, from_text, to_text, cc_text, bcc_text, label_text) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                        ),
                        (
                            email_message_id,
                            resolved_subject or "",
                            str(body_text or ""),
                            resolved_from or "",
                            resolved_to or "",
                            resolved_cc or "",
                            resolved_bcc or "",
                            label_text or "",
                        ),
                    )

            return {
                "email_message_id": email_message_id,
                "source_id": source_id,
                "tenant_id": resolved_tenant,
                "match_strategy": match_strategy,
            }

    @staticmethod
    def _normalize_email_sync_cursor(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _resolve_email_sync_source_row_id(
        self,
        conn,
        *,
        tenant_id: str,
        provider: str,
        source_key: str,
        create_if_missing: bool,
    ) -> int | None:
        if create_if_missing:
            self._execute_with_connection(
                conn,
                (
                    "INSERT INTO email_sources "
                    "(tenant_id, provider, source_key, display_name, status) "
                    "VALUES (?, ?, ?, ?, 'active') "
                    "ON CONFLICT(tenant_id, provider, source_key) "
                    "DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
                ),
                (tenant_id, provider, source_key, source_key),
            )

        source_row = self._fetchone_with_connection(
            conn,
            (
                "SELECT id FROM email_sources "
                "WHERE tenant_id = ? AND provider = ? AND source_key = ? "
                "LIMIT 1"
            ),
            (tenant_id, provider, source_key),
        )
        if not source_row:
            return None
        return int(source_row["id"])

    def _fetch_email_sync_state_row(
        self,
        conn,
        *,
        tenant_id: str,
        source_id: int,
        provider: str,
        source_key: str,
    ) -> dict[str, Any] | None:
        state_row = self._fetchone_with_connection(
            conn,
            (
                "SELECT id, cursor, last_run_at, last_success_at, error_state, "
                "retry_backoff_count, updated_at "
                "FROM email_sync_state "
                "WHERE tenant_id = ? AND source_id = ? "
                "LIMIT 1"
            ),
            (tenant_id, int(source_id)),
        )
        if not state_row:
            return None
        return {
            "id": int(state_row["id"]),
            "tenant_id": tenant_id,
            "source_id": int(source_id),
            "provider": provider,
            "source_key": source_key,
            "cursor": state_row.get("cursor"),
            "last_run_at": state_row.get("last_run_at"),
            "last_success_at": state_row.get("last_success_at"),
            "error_state": state_row.get("error_state"),
            "retry_backoff_count": int(state_row.get("retry_backoff_count") or 0),
            "updated_at": state_row.get("updated_at"),
        }

    def get_email_sync_state(
        self,
        *,
        provider: str,
        source_key: str,
        tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        resolved_provider = str(provider or "").strip().lower() or "upload"
        resolved_source_key = str(source_key or "").strip()
        if not resolved_source_key:
            raise InputError("source_key is required for email sync state.")  # noqa: TRY003

        with self.transaction() as conn:
            source_row_id = self._resolve_email_sync_source_row_id(
                conn,
                tenant_id=resolved_tenant,
                provider=resolved_provider,
                source_key=resolved_source_key,
                create_if_missing=False,
            )
            if source_row_id is None:
                return None
            return self._fetch_email_sync_state_row(
                conn,
                tenant_id=resolved_tenant,
                source_id=source_row_id,
                provider=resolved_provider,
                source_key=resolved_source_key,
            )

    def mark_email_sync_run_started(
        self,
        *,
        provider: str,
        source_key: str,
        tenant_id: str | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        resolved_provider = str(provider or "").strip().lower() or "upload"
        resolved_source_key = str(source_key or "").strip()
        if not resolved_source_key:
            raise InputError("source_key is required for email sync state.")  # noqa: TRY003

        started_at = datetime.now(timezone.utc).isoformat()
        normalized_cursor = self._normalize_email_sync_cursor(cursor)

        with self.transaction() as conn:
            source_row_id = self._resolve_email_sync_source_row_id(
                conn,
                tenant_id=resolved_tenant,
                provider=resolved_provider,
                source_key=resolved_source_key,
                create_if_missing=True,
            )
            if source_row_id is None:
                raise DatabaseError("Failed to resolve email source for sync state.")  # noqa: TRY003

            existing_row = self._fetch_email_sync_state_row(
                conn,
                tenant_id=resolved_tenant,
                source_id=source_row_id,
                provider=resolved_provider,
                source_key=resolved_source_key,
            )
            next_cursor = (
                normalized_cursor
                if normalized_cursor is not None
                else (existing_row or {}).get("cursor")
            )

            if existing_row:
                self._execute_with_connection(
                    conn,
                    (
                        "UPDATE email_sync_state SET "
                        "cursor = ?, "
                        "last_run_at = ?, "
                        "updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = ?"
                    ),
                    (next_cursor, started_at, int(existing_row["id"])),
                )
            else:
                self._execute_with_connection(
                    conn,
                    (
                        "INSERT INTO email_sync_state "
                        "(tenant_id, source_id, cursor, last_run_at, last_success_at, error_state, retry_backoff_count, updated_at) "
                        "VALUES (?, ?, ?, ?, NULL, NULL, 0, CURRENT_TIMESTAMP)"
                    ),
                    (
                        resolved_tenant,
                        source_row_id,
                        next_cursor,
                        started_at,
                    ),
                )

            state = self._fetch_email_sync_state_row(
                conn,
                tenant_id=resolved_tenant,
                source_id=source_row_id,
                provider=resolved_provider,
                source_key=resolved_source_key,
            )
            if not state:
                raise DatabaseError("Failed to persist email sync start state.")  # noqa: TRY003
            return state

    def mark_email_sync_run_succeeded(
        self,
        *,
        provider: str,
        source_key: str,
        cursor: str | None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        resolved_provider = str(provider or "").strip().lower() or "upload"
        resolved_source_key = str(source_key or "").strip()
        if not resolved_source_key:
            raise InputError("source_key is required for email sync state.")  # noqa: TRY003

        succeeded_at = datetime.now(timezone.utc).isoformat()
        normalized_cursor = self._normalize_email_sync_cursor(cursor)

        with self.transaction() as conn:
            source_row_id = self._resolve_email_sync_source_row_id(
                conn,
                tenant_id=resolved_tenant,
                provider=resolved_provider,
                source_key=resolved_source_key,
                create_if_missing=True,
            )
            if source_row_id is None:
                raise DatabaseError("Failed to resolve email source for sync state.")  # noqa: TRY003

            existing_row = self._fetch_email_sync_state_row(
                conn,
                tenant_id=resolved_tenant,
                source_id=source_row_id,
                provider=resolved_provider,
                source_key=resolved_source_key,
            )
            next_cursor = (
                normalized_cursor
                if normalized_cursor is not None
                else (existing_row or {}).get("cursor")
            )

            if existing_row:
                self._execute_with_connection(
                    conn,
                    (
                        "UPDATE email_sync_state SET "
                        "cursor = ?, "
                        "last_run_at = ?, "
                        "last_success_at = ?, "
                        "error_state = NULL, "
                        "retry_backoff_count = 0, "
                        "updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = ?"
                    ),
                    (
                        next_cursor,
                        succeeded_at,
                        succeeded_at,
                        int(existing_row["id"]),
                    ),
                )
            else:
                self._execute_with_connection(
                    conn,
                    (
                        "INSERT INTO email_sync_state "
                        "(tenant_id, source_id, cursor, last_run_at, last_success_at, error_state, retry_backoff_count, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, NULL, 0, CURRENT_TIMESTAMP)"
                    ),
                    (
                        resolved_tenant,
                        source_row_id,
                        next_cursor,
                        succeeded_at,
                        succeeded_at,
                    ),
                )

            state = self._fetch_email_sync_state_row(
                conn,
                tenant_id=resolved_tenant,
                source_id=source_row_id,
                provider=resolved_provider,
                source_key=resolved_source_key,
            )
            if not state:
                raise DatabaseError("Failed to persist email sync success state.")  # noqa: TRY003
            return state

    def mark_email_sync_run_failed(
        self,
        *,
        provider: str,
        source_key: str,
        error_state: str,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        resolved_provider = str(provider or "").strip().lower() or "upload"
        resolved_source_key = str(source_key or "").strip()
        if not resolved_source_key:
            raise InputError("source_key is required for email sync state.")  # noqa: TRY003

        failed_at = datetime.now(timezone.utc).isoformat()
        normalized_error = str(error_state or "sync_failed").strip()[:1024] or "sync_failed"

        with self.transaction() as conn:
            source_row_id = self._resolve_email_sync_source_row_id(
                conn,
                tenant_id=resolved_tenant,
                provider=resolved_provider,
                source_key=resolved_source_key,
                create_if_missing=True,
            )
            if source_row_id is None:
                raise DatabaseError("Failed to resolve email source for sync state.")  # noqa: TRY003

            existing_row = self._fetch_email_sync_state_row(
                conn,
                tenant_id=resolved_tenant,
                source_id=source_row_id,
                provider=resolved_provider,
                source_key=resolved_source_key,
            )
            if existing_row:
                retry_count = int(existing_row.get("retry_backoff_count") or 0) + 1
                self._execute_with_connection(
                    conn,
                    (
                        "UPDATE email_sync_state SET "
                        "last_run_at = ?, "
                        "error_state = ?, "
                        "retry_backoff_count = ?, "
                        "updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = ?"
                    ),
                    (
                        failed_at,
                        normalized_error,
                        retry_count,
                        int(existing_row["id"]),
                    ),
                )
            else:
                self._execute_with_connection(
                    conn,
                    (
                        "INSERT INTO email_sync_state "
                        "(tenant_id, source_id, cursor, last_run_at, last_success_at, error_state, retry_backoff_count, updated_at) "
                        "VALUES (?, ?, NULL, ?, NULL, ?, 1, CURRENT_TIMESTAMP)"
                    ),
                    (
                        resolved_tenant,
                        source_row_id,
                        failed_at,
                        normalized_error,
                    ),
                )

            state = self._fetch_email_sync_state_row(
                conn,
                tenant_id=resolved_tenant,
                source_id=source_row_id,
                provider=resolved_provider,
                source_key=resolved_source_key,
            )
            if not state:
                raise DatabaseError("Failed to persist email sync failure state.")  # noqa: TRY003
            return state

    @staticmethod
    def _normalize_email_backfill_key(value: Any) -> str:
        text = str(value or "").strip().lower()
        return text[:128] if text else "legacy_media_email"

    def _fetch_email_backfill_state_row(
        self,
        conn,
        *,
        tenant_id: str,
        backfill_key: str,
    ) -> dict[str, Any] | None:
        row = self._fetchone_with_connection(
            conn,
            (
                "SELECT id, last_media_id, processed_count, success_count, skipped_count, "
                "failed_count, status, last_error, started_at, completed_at, updated_at "
                "FROM email_backfill_state "
                "WHERE tenant_id = ? AND backfill_key = ? "
                "LIMIT 1"
            ),
            (tenant_id, backfill_key),
        )
        if not row:
            return None
        return {
            "id": int(row["id"]),
            "tenant_id": tenant_id,
            "backfill_key": backfill_key,
            "last_media_id": int(row.get("last_media_id") or 0),
            "processed_count": int(row.get("processed_count") or 0),
            "success_count": int(row.get("success_count") or 0),
            "skipped_count": int(row.get("skipped_count") or 0),
            "failed_count": int(row.get("failed_count") or 0),
            "status": str(row.get("status") or "idle"),
            "last_error": row.get("last_error"),
            "started_at": row.get("started_at"),
            "completed_at": row.get("completed_at"),
            "updated_at": row.get("updated_at"),
        }

    def _ensure_email_backfill_state_row(
        self,
        conn,
        *,
        tenant_id: str,
        backfill_key: str,
    ) -> None:
        self._execute_with_connection(
            conn,
            (
                "INSERT INTO email_backfill_state "
                "(tenant_id, backfill_key, last_media_id, processed_count, success_count, "
                "skipped_count, failed_count, status, updated_at) "
                "VALUES (?, ?, 0, 0, 0, 0, 0, 'idle', CURRENT_TIMESTAMP) "
                "ON CONFLICT(tenant_id, backfill_key) DO NOTHING"
            ),
            (tenant_id, backfill_key),
        )

    def get_email_legacy_backfill_state(
        self,
        *,
        tenant_id: str | None = None,
        backfill_key: str = "legacy_media_email",
    ) -> dict[str, Any] | None:
        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        resolved_key = self._normalize_email_backfill_key(backfill_key)
        with self.transaction() as conn:
            return self._fetch_email_backfill_state_row(
                conn,
                tenant_id=resolved_tenant,
                backfill_key=resolved_key,
            )

    @staticmethod
    def _parse_email_backfill_safe_metadata(raw_safe_metadata: Any) -> dict[str, Any]:
        if isinstance(raw_safe_metadata, dict):
            metadata_map = dict(raw_safe_metadata)
        else:
            raw_text = str(raw_safe_metadata or "").strip()
            if not raw_text:
                return {}
            try:
                parsed = json.loads(raw_text)
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                return {}
            if not isinstance(parsed, dict):
                return {}
            metadata_map = dict(parsed)

        nested_meta = metadata_map.get("metadata")
        if (
            not isinstance(metadata_map.get("email"), dict)
            and isinstance(nested_meta, dict)
            and isinstance(nested_meta.get("email"), dict)
        ):
            # Some older document versions wrap parser metadata under "metadata".
            merged = dict(nested_meta)
            for key, value in metadata_map.items():
                if key not in merged:
                    merged[key] = value
            metadata_map = merged

        return metadata_map

    @staticmethod
    def _derive_email_backfill_source_fields(
        *,
        metadata_map: dict[str, Any],
        media_url: Any,
        tenant_id: str,
    ) -> tuple[str, str, str | None]:
        url_text = str(media_url or "").strip()
        provider_hint = str(metadata_map.get("provider") or "").strip().lower()
        source_hint = str(metadata_map.get("source") or "").strip().lower()
        email_meta = metadata_map.get("email")
        email_map = email_meta if isinstance(email_meta, dict) else {}

        provider = provider_hint
        if not provider:
            if source_hint in {"gmail", "gmail_connector"} or url_text.lower().startswith("gmail://"):
                provider = "gmail"
            else:
                provider = "upload"

        source_key = str(
            metadata_map.get("source_key")
            or email_map.get("source_key")
            or ""
        ).strip()
        source_message_id = str(
            email_map.get("source_message_id")
            or metadata_map.get("source_message_id")
            or ""
        ).strip() or None

        if url_text.lower().startswith("gmail://"):
            path = url_text[len("gmail://") :]
            source_part, sep, message_part = path.partition("/")
            source_part = source_part.strip()
            message_part = message_part.strip()
            if provider == "gmail" and not source_key and source_part:
                source_key = source_part
            if source_message_id is None and sep and message_part:
                source_message_id = message_part

        if not source_key:
            source_key = f"legacy-media:{tenant_id}"

        return provider, source_key, source_message_id

    def _update_email_backfill_progress(
        self,
        *,
        tenant_id: str,
        backfill_key: str,
        last_media_id: int,
        delta_processed: int,
        delta_success: int,
        delta_skipped: int,
        delta_failed: int,
        status: str,
        last_error: str | None = None,
    ) -> None:
        error_text = str(last_error or "").strip()
        normalized_error = error_text[:1024] if error_text else None
        with self.transaction() as conn:
            self._ensure_email_backfill_state_row(
                conn,
                tenant_id=tenant_id,
                backfill_key=backfill_key,
            )
            self._execute_with_connection(
                conn,
                (
                    "UPDATE email_backfill_state SET "
                    "last_media_id = ?, "
                    "processed_count = processed_count + ?, "
                    "success_count = success_count + ?, "
                    "skipped_count = skipped_count + ?, "
                    "failed_count = failed_count + ?, "
                    "status = ?, "
                    "last_error = CASE WHEN ? = 1 THEN ? ELSE last_error END, "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE tenant_id = ? AND backfill_key = ?"
                ),
                (
                    int(last_media_id),
                    int(delta_processed),
                    int(delta_success),
                    int(delta_skipped),
                    int(delta_failed),
                    str(status or "running"),
                    1 if normalized_error else 0,
                    normalized_error,
                    tenant_id,
                    backfill_key,
                ),
            )

    def run_email_legacy_backfill_batch(
        self,
        *,
        batch_size: int = 500,
        tenant_id: str | None = None,
        backfill_key: str = "legacy_media_email",
    ) -> dict[str, Any]:
        """
        Backfill one batch of legacy email Media rows into normalized email tables.

        Progress is checkpointed in `email_backfill_state` by `(tenant_id, backfill_key)`
        so repeated calls resume from the prior `last_media_id`.
        """

        try:
            batch_size_int = int(batch_size)
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            raise InputError("batch_size must be an integer.") from exc  # noqa: TRY003
        if batch_size_int <= 0:
            raise InputError("batch_size must be greater than zero.")  # noqa: TRY003

        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        resolved_key = self._normalize_email_backfill_key(backfill_key)
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.transaction() as conn:
            self._ensure_email_backfill_state_row(
                conn,
                tenant_id=resolved_tenant,
                backfill_key=resolved_key,
            )
            self._execute_with_connection(
                conn,
                (
                    "UPDATE email_backfill_state SET "
                    "status = 'running', "
                    "started_at = COALESCE(started_at, ?), "
                    "completed_at = NULL, "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE tenant_id = ? AND backfill_key = ?"
                ),
                (now_iso, resolved_tenant, resolved_key),
            )
            state_before = self._fetch_email_backfill_state_row(
                conn,
                tenant_id=resolved_tenant,
                backfill_key=resolved_key,
            )
            if state_before is None:
                raise DatabaseError("Failed to initialize email backfill state.")  # noqa: TRY003
            cursor_start = int(state_before.get("last_media_id") or 0)
            rows = self._fetchall_with_connection(
                conn,
                (
                    "SELECT m.id, m.url, m.title, m.content, m.author, m.ingestion_date, "
                    "(SELECT dv.safe_metadata "
                    " FROM DocumentVersions dv "
                    " WHERE dv.media_id = m.id AND dv.deleted = 0 "
                    " ORDER BY dv.version_number DESC, dv.id DESC "
                    " LIMIT 1) AS safe_metadata_json, "
                    "EXISTS(SELECT 1 FROM email_messages em WHERE em.media_id = m.id) AS already_backfilled "
                    "FROM Media m "
                    "WHERE m.deleted = 0 "
                    "AND lower(COALESCE(m.type, '')) = 'email' "
                    "AND m.id > ? "
                    "ORDER BY m.id ASC "
                    "LIMIT ?"
                ),
                (cursor_start, batch_size_int),
            )

        if not rows:
            with self.transaction() as conn:
                state = self._fetch_email_backfill_state_row(
                    conn,
                    tenant_id=resolved_tenant,
                    backfill_key=resolved_key,
                )
                if state is None:
                    raise DatabaseError("Failed to load email backfill state.")  # noqa: TRY003
                final_status = (
                    "completed_with_errors"
                    if int(state.get("failed_count") or 0) > 0
                    else "completed"
                )
                self._execute_with_connection(
                    conn,
                    (
                        "UPDATE email_backfill_state SET "
                        "status = ?, "
                        "completed_at = COALESCE(completed_at, ?), "
                        "updated_at = CURRENT_TIMESTAMP "
                        "WHERE tenant_id = ? AND backfill_key = ?"
                    ),
                    (final_status, now_iso, resolved_tenant, resolved_key),
                )
                state_after = self._fetch_email_backfill_state_row(
                    conn,
                    tenant_id=resolved_tenant,
                    backfill_key=resolved_key,
                )
            return {
                "tenant_id": resolved_tenant,
                "backfill_key": resolved_key,
                "batch_size": batch_size_int,
                "cursor_start": cursor_start,
                "cursor_end": cursor_start,
                "scanned": 0,
                "ingested": 0,
                "skipped": 0,
                "failed": 0,
                "completed": True,
                "status": final_status,
                "state": state_after,
            }

        scanned = 0
        ingested = 0
        skipped = 0
        failed = 0
        cursor_end = cursor_start

        for row in rows:
            media_id = int(row.get("id") or 0)
            if media_id <= 0:
                continue
            cursor_end = media_id
            scanned += 1

            delta_success = 0
            delta_skipped = 0
            delta_failed = 0
            row_error: str | None = None

            already_backfilled = bool(row.get("already_backfilled"))
            if already_backfilled:
                skipped += 1
                delta_skipped = 1
            else:
                try:
                    metadata_map = self._parse_email_backfill_safe_metadata(
                        row.get("safe_metadata_json")
                    )
                    email_meta = metadata_map.get("email")
                    if not isinstance(email_meta, dict):
                        email_meta = {}
                        metadata_map["email"] = email_meta

                    subject_fallback = str(row.get("title") or "").strip()
                    from_fallback = str(row.get("author") or "").strip()
                    date_fallback = str(row.get("ingestion_date") or "").strip()
                    if subject_fallback and not str(email_meta.get("subject") or "").strip():
                        email_meta["subject"] = subject_fallback
                    if from_fallback and not str(email_meta.get("from") or "").strip():
                        email_meta["from"] = from_fallback
                    if date_fallback and not str(email_meta.get("date") or "").strip():
                        email_meta["date"] = date_fallback

                    provider, source_key, source_message_id = self._derive_email_backfill_source_fields(
                        metadata_map=metadata_map,
                        media_url=row.get("url"),
                        tenant_id=resolved_tenant,
                    )
                    if source_message_id and not str(email_meta.get("source_message_id") or "").strip():
                        email_meta["source_message_id"] = source_message_id

                    body_text = str(row.get("content") or "")
                    labels = self._collect_email_labels(metadata_map)

                    self.upsert_email_message_graph(
                        media_id=media_id,
                        metadata=metadata_map,
                        body_text=body_text,
                        tenant_id=resolved_tenant,
                        provider=provider,
                        source_key=source_key,
                        source_message_id=source_message_id,
                        labels=labels,
                    )
                    ingested += 1
                    delta_success = 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    delta_failed = 1
                    row_error = f"{type(exc).__name__}: {exc}"

            self._update_email_backfill_progress(
                tenant_id=resolved_tenant,
                backfill_key=resolved_key,
                last_media_id=media_id,
                delta_processed=1,
                delta_success=delta_success,
                delta_skipped=delta_skipped,
                delta_failed=delta_failed,
                status="running",
                last_error=row_error,
            )

        with self.transaction() as conn:
            remaining = self._fetchone_with_connection(
                conn,
                (
                    "SELECT id FROM Media "
                    "WHERE deleted = 0 "
                    "AND lower(COALESCE(type, '')) = 'email' "
                    "AND id > ? "
                    "LIMIT 1"
                ),
                (cursor_end,),
            )
            has_more = bool(remaining)
            state_after = self._fetch_email_backfill_state_row(
                conn,
                tenant_id=resolved_tenant,
                backfill_key=resolved_key,
            )
            if state_after is None:
                raise DatabaseError("Failed to load email backfill state after batch.")  # noqa: TRY003
            final_status = str(state_after.get("status") or "running")
            if not has_more:
                final_status = (
                    "completed_with_errors"
                    if int(state_after.get("failed_count") or 0) > 0
                    else "completed"
                )
                self._execute_with_connection(
                    conn,
                    (
                        "UPDATE email_backfill_state SET "
                        "status = ?, "
                        "completed_at = COALESCE(completed_at, ?), "
                        "updated_at = CURRENT_TIMESTAMP "
                        "WHERE tenant_id = ? AND backfill_key = ?"
                    ),
                    (final_status, now_iso, resolved_tenant, resolved_key),
                )
                state_after = self._fetch_email_backfill_state_row(
                    conn,
                    tenant_id=resolved_tenant,
                    backfill_key=resolved_key,
                )
                if state_after is None:
                    raise DatabaseError("Failed to persist final email backfill state.")  # noqa: TRY003

        return {
            "tenant_id": resolved_tenant,
            "backfill_key": resolved_key,
            "batch_size": batch_size_int,
            "cursor_start": cursor_start,
            "cursor_end": cursor_end,
            "scanned": scanned,
            "ingested": ingested,
            "skipped": skipped,
            "failed": failed,
            "completed": not has_more,
            "status": final_status,
            "state": state_after,
        }

    def run_email_legacy_backfill_worker(
        self,
        *,
        batch_size: int = 500,
        tenant_id: str | None = None,
        backfill_key: str = "legacy_media_email",
        max_batches: int | None = None,
    ) -> dict[str, Any]:
        """
        Worker-style loop for the legacy email backfill.

        Runs `run_email_legacy_backfill_batch` repeatedly until completion or
        until `max_batches` is reached.
        """

        max_batches_int: int | None = None
        if max_batches is not None:
            try:
                max_batches_int = int(max_batches)
            except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
                raise InputError("max_batches must be an integer or None.") from exc  # noqa: TRY003
            if max_batches_int <= 0:
                raise InputError("max_batches must be greater than zero when provided.")  # noqa: TRY003

        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        resolved_key = self._normalize_email_backfill_key(backfill_key)

        batches_run = 0
        scanned_total = 0
        ingested_total = 0
        skipped_total = 0
        failed_total = 0
        completed = False
        stop_reason = "max_batches"
        last_batch: dict[str, Any] | None = None

        while True:
            if max_batches_int is not None and batches_run >= max_batches_int:
                break

            batch_result = self.run_email_legacy_backfill_batch(
                batch_size=batch_size,
                tenant_id=resolved_tenant,
                backfill_key=resolved_key,
            )
            last_batch = batch_result
            batches_run += 1
            scanned_total += int(batch_result.get("scanned") or 0)
            ingested_total += int(batch_result.get("ingested") or 0)
            skipped_total += int(batch_result.get("skipped") or 0)
            failed_total += int(batch_result.get("failed") or 0)

            if bool(batch_result.get("completed")):
                completed = True
                stop_reason = "completed"
                break

            # Safety valve: avoid infinite loops if a batch made no forward progress.
            if int(batch_result.get("scanned") or 0) <= 0:
                completed = True
                stop_reason = "no_progress"
                break

        final_state = self.get_email_legacy_backfill_state(
            tenant_id=resolved_tenant,
            backfill_key=resolved_key,
        )
        return {
            "tenant_id": resolved_tenant,
            "backfill_key": resolved_key,
            "batch_size": int(batch_size),
            "max_batches": max_batches_int,
            "batches_run": batches_run,
            "scanned": scanned_total,
            "ingested": ingested_total,
            "skipped": skipped_total,
            "failed": failed_total,
            "completed": completed,
            "stop_reason": stop_reason,
            "last_batch": last_batch,
            "state": final_state,
        }

    @staticmethod
    def _normalize_email_label_values(values: list[str] | str | None) -> dict[str, str]:
        if values is None:
            return {}
        raw_values: list[str] = []
        if isinstance(values, str):
            raw_values.extend(part.strip() for part in values.split(","))
        elif isinstance(values, list):
            raw_values.extend(str(part or "").strip() for part in values)

        out: dict[str, str] = {}
        for value in raw_values:
            text = str(value or "").strip()
            if not text:
                continue
            key = text.lower()
            if key not in out:
                out[key] = text
        return out

    def _resolve_email_message_row_for_source_message(
        self,
        conn,
        *,
        tenant_id: str,
        source_id: int,
        source_message_id: str,
    ) -> dict[str, Any] | None:
        return self._fetchone_with_connection(
            conn,
            (
                "SELECT id, media_id, label_text, raw_metadata_json "
                "FROM email_messages "
                "WHERE tenant_id = ? AND source_id = ? AND source_message_id = ? "
                "LIMIT 1"
            ),
            (tenant_id, int(source_id), source_message_id),
        )

    def apply_email_label_delta(
        self,
        *,
        provider: str,
        source_key: str,
        source_message_id: str,
        labels_added: list[str] | str | None = None,
        labels_removed: list[str] | str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        resolved_provider = str(provider or "").strip().lower() or "upload"
        resolved_source_key = str(source_key or "").strip()
        resolved_message_key = str(source_message_id or "").strip()
        if not resolved_source_key:
            raise InputError("source_key is required for email label delta.")  # noqa: TRY003
        if not resolved_message_key:
            raise InputError("source_message_id is required for email label delta.")  # noqa: TRY003

        added_map = self._normalize_email_label_values(labels_added)
        removed_map = self._normalize_email_label_values(labels_removed)
        if not added_map and not removed_map:
            return {
                "applied": False,
                "reason": "empty_delta",
                "tenant_id": resolved_tenant,
                "provider": resolved_provider,
                "source_key": resolved_source_key,
                "source_message_id": resolved_message_key,
                "labels": [],
            }

        # Net out contradictory changes in a single delta window.
        overlap_keys = set(added_map.keys()) & set(removed_map.keys())
        for key in overlap_keys:
            added_map.pop(key, None)
            removed_map.pop(key, None)

        with self.transaction() as conn:
            source_row_id = self._resolve_email_sync_source_row_id(
                conn,
                tenant_id=resolved_tenant,
                provider=resolved_provider,
                source_key=resolved_source_key,
                create_if_missing=False,
            )
            if source_row_id is None:
                return {
                    "applied": False,
                    "reason": "source_not_found",
                    "tenant_id": resolved_tenant,
                    "provider": resolved_provider,
                    "source_key": resolved_source_key,
                    "source_message_id": resolved_message_key,
                    "labels": [],
                }

            message_row = self._resolve_email_message_row_for_source_message(
                conn,
                tenant_id=resolved_tenant,
                source_id=source_row_id,
                source_message_id=resolved_message_key,
            )
            if message_row is None:
                return {
                    "applied": False,
                    "reason": "message_not_found",
                    "tenant_id": resolved_tenant,
                    "provider": resolved_provider,
                    "source_key": resolved_source_key,
                    "source_message_id": resolved_message_key,
                    "labels": [],
                }

            email_message_id = int(message_row["id"])
            media_id = int(message_row["media_id"])

            removed_count = 0
            for label_key in removed_map.keys():
                label_row = self._fetchone_with_connection(
                    conn,
                    (
                        "SELECT id FROM email_labels "
                        "WHERE tenant_id = ? AND label_key = ? "
                        "LIMIT 1"
                    ),
                    (resolved_tenant, label_key),
                )
                if not label_row:
                    continue
                delete_cursor = self._execute_with_connection(
                    conn,
                    (
                        "DELETE FROM email_message_labels "
                        "WHERE email_message_id = ? AND label_id = ?"
                    ),
                    (email_message_id, int(label_row["id"])),
                )
                removed_count += int(getattr(delete_cursor, "rowcount", 0) or 0)

            added_count = 0
            for label_key, label_name in added_map.items():
                self._execute_with_connection(
                    conn,
                    (
                        "INSERT INTO email_labels (tenant_id, label_key, label_name) "
                        "VALUES (?, ?, ?) "
                        "ON CONFLICT(tenant_id, label_key) "
                        "DO UPDATE SET label_name = EXCLUDED.label_name, updated_at = CURRENT_TIMESTAMP"
                    ),
                    (resolved_tenant, label_key, label_name),
                )
                label_row = self._fetchone_with_connection(
                    conn,
                    (
                        "SELECT id FROM email_labels "
                        "WHERE tenant_id = ? AND label_key = ? "
                        "LIMIT 1"
                    ),
                    (resolved_tenant, label_key),
                )
                if not label_row:
                    continue
                insert_cursor = self._execute_with_connection(
                    conn,
                    (
                        "INSERT INTO email_message_labels (email_message_id, label_id) "
                        "VALUES (?, ?) ON CONFLICT DO NOTHING"
                    ),
                    (email_message_id, int(label_row["id"])),
                )
                added_count += int(getattr(insert_cursor, "rowcount", 0) or 0)

            label_rows = self._fetchall_with_connection(
                conn,
                (
                    "SELECT el.label_name AS label_name "
                    "FROM email_message_labels eml "
                    "JOIN email_labels el ON el.id = eml.label_id "
                    "WHERE eml.email_message_id = ? AND el.tenant_id = ? "
                    "ORDER BY el.label_name ASC"
                ),
                (email_message_id, resolved_tenant),
            )
            final_labels = [
                str(row.get("label_name") or "").strip()
                for row in label_rows
                if str(row.get("label_name") or "").strip()
            ]
            label_text = ", ".join(final_labels) if final_labels else None

            raw_metadata_json = message_row.get("raw_metadata_json")
            metadata_json_out = raw_metadata_json
            if isinstance(raw_metadata_json, str) and raw_metadata_json.strip():
                with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                    metadata_obj = json.loads(raw_metadata_json)
                    if isinstance(metadata_obj, dict):
                        metadata_obj["labels"] = final_labels
                        email_obj = metadata_obj.get("email")
                        if isinstance(email_obj, dict):
                            email_obj["labels"] = final_labels
                        metadata_json_out = json.dumps(metadata_obj, ensure_ascii=False)

            self._execute_with_connection(
                conn,
                (
                    "UPDATE email_messages "
                    "SET label_text = ?, raw_metadata_json = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?"
                ),
                (label_text, metadata_json_out, email_message_id),
            )

            if self.backend_type == BackendType.SQLITE:
                with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                    self._execute_with_connection(
                        conn,
                        (
                            "INSERT OR REPLACE INTO email_fts "
                            "(rowid, subject, body_text, from_text, to_text, cc_text, bcc_text, label_text) "
                            "SELECT id, COALESCE(subject, ''), COALESCE(body_text, ''), "
                            "COALESCE(from_text, ''), COALESCE(to_text, ''), "
                            "COALESCE(cc_text, ''), COALESCE(bcc_text, ''), COALESCE(label_text, '') "
                            "FROM email_messages WHERE id = ?"
                        ),
                        (email_message_id,),
                    )

            return {
                "applied": bool(added_count or removed_count),
                "reason": "ok",
                "tenant_id": resolved_tenant,
                "provider": resolved_provider,
                "source_key": resolved_source_key,
                "source_message_id": resolved_message_key,
                "source_id": int(source_row_id),
                "email_message_id": email_message_id,
                "media_id": media_id,
                "added_count": int(added_count),
                "removed_count": int(removed_count),
                "labels": final_labels,
            }

    def reconcile_email_message_state(
        self,
        *,
        provider: str,
        source_key: str,
        source_message_id: str,
        tenant_id: str | None = None,
        deleted: bool | None = None,
    ) -> dict[str, Any]:
        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        resolved_provider = str(provider or "").strip().lower() or "upload"
        resolved_source_key = str(source_key or "").strip()
        resolved_message_key = str(source_message_id or "").strip()
        if not resolved_source_key:
            raise InputError("source_key is required for email state reconciliation.")  # noqa: TRY003
        if not resolved_message_key:
            raise InputError("source_message_id is required for email state reconciliation.")  # noqa: TRY003

        if deleted is None:
            return {
                "applied": False,
                "reason": "no_state_change",
                "tenant_id": resolved_tenant,
                "provider": resolved_provider,
                "source_key": resolved_source_key,
                "source_message_id": resolved_message_key,
            }

        with self.transaction() as conn:
            source_row_id = self._resolve_email_sync_source_row_id(
                conn,
                tenant_id=resolved_tenant,
                provider=resolved_provider,
                source_key=resolved_source_key,
                create_if_missing=False,
            )
            if source_row_id is None:
                return {
                    "applied": False,
                    "reason": "source_not_found",
                    "tenant_id": resolved_tenant,
                    "provider": resolved_provider,
                    "source_key": resolved_source_key,
                    "source_message_id": resolved_message_key,
                }

            message_row = self._resolve_email_message_row_for_source_message(
                conn,
                tenant_id=resolved_tenant,
                source_id=source_row_id,
                source_message_id=resolved_message_key,
            )
            if message_row is None:
                return {
                    "applied": False,
                    "reason": "message_not_found",
                    "tenant_id": resolved_tenant,
                    "provider": resolved_provider,
                    "source_key": resolved_source_key,
                    "source_message_id": resolved_message_key,
                    "source_id": int(source_row_id),
                }

            media_id = int(message_row["media_id"])
            media_row = self._fetchone_with_connection(
                conn,
                "SELECT deleted FROM Media WHERE id = ? LIMIT 1",
                (media_id,),
            )
            media_deleted = bool((media_row or {}).get("deleted"))

        if bool(deleted):
            if media_deleted:
                return {
                    "applied": False,
                    "reason": "already_deleted",
                    "tenant_id": resolved_tenant,
                    "provider": resolved_provider,
                    "source_key": resolved_source_key,
                    "source_message_id": resolved_message_key,
                    "media_id": media_id,
                }
            removed = bool(self.soft_delete_media(media_id, cascade=True))
            return {
                "applied": removed,
                "reason": "deleted" if removed else "delete_failed",
                "tenant_id": resolved_tenant,
                "provider": resolved_provider,
                "source_key": resolved_source_key,
                "source_message_id": resolved_message_key,
                "media_id": media_id,
            }

        return {
            "applied": False,
            "reason": "unsupported_state",
            "tenant_id": resolved_tenant,
            "provider": resolved_provider,
            "source_key": resolved_source_key,
            "source_message_id": resolved_message_key,
            "media_id": media_id,
        }

    @staticmethod
    def _parse_email_retention_datetime(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
            parsed = parsedate_to_datetime(text)
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
        return None

    def _cleanup_email_orphans_for_tenant(
        self,
        conn,
        *,
        tenant_id: str,
        delete_empty_sources: bool = False,
    ) -> dict[str, int]:
        labels_cursor = self._execute_with_connection(
            conn,
            (
                "DELETE FROM email_labels "
                "WHERE tenant_id = ? "
                "AND NOT EXISTS ("
                "SELECT 1 FROM email_message_labels eml "
                "WHERE eml.label_id = email_labels.id"
                ")"
            ),
            (tenant_id,),
        )
        participants_cursor = self._execute_with_connection(
            conn,
            (
                "DELETE FROM email_participants "
                "WHERE tenant_id = ? "
                "AND NOT EXISTS ("
                "SELECT 1 FROM email_message_participants emp "
                "WHERE emp.participant_id = email_participants.id"
                ")"
            ),
            (tenant_id,),
        )

        sources_deleted = 0
        if delete_empty_sources:
            sources_cursor = self._execute_with_connection(
                conn,
                (
                    "DELETE FROM email_sources "
                    "WHERE tenant_id = ? "
                    "AND NOT EXISTS ("
                    "SELECT 1 FROM email_messages em "
                    "WHERE em.source_id = email_sources.id"
                    ")"
                ),
                (tenant_id,),
            )
            sources_deleted = int(getattr(sources_cursor, "rowcount", 0) or 0)

        return {
            "labels_deleted": int(getattr(labels_cursor, "rowcount", 0) or 0),
            "participants_deleted": int(getattr(participants_cursor, "rowcount", 0) or 0),
            "sources_deleted": int(sources_deleted),
        }

    def enforce_email_retention_policy(
        self,
        *,
        retention_days: int,
        tenant_id: str | None = None,
        hard_delete: bool = False,
        include_missing_internal_date: bool = False,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Apply tenant-scoped retention policy to normalized email rows."""

        try:
            retention_days_int = int(retention_days)
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            raise InputError("retention_days must be an integer.") from exc  # noqa: TRY003
        if retention_days_int < 0:
            raise InputError("retention_days must be greater than or equal to zero.")  # noqa: TRY003

        limit_int = None
        if limit is not None:
            try:
                limit_int = int(limit)
            except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
                raise InputError("limit must be an integer when provided.") from exc  # noqa: TRY003
            if limit_int <= 0:
                raise InputError("limit must be greater than zero when provided.")  # noqa: TRY003

        resolved_tenant = self._resolve_email_tenant_id(tenant_id)
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=retention_days_int)

        with self.transaction() as conn:
            candidate_rows = self._fetchall_with_connection(
                conn,
                (
                    "SELECT "
                    "em.id AS email_message_id, "
                    "em.media_id AS media_id, "
                    "em.internal_date AS internal_date, "
                    "m.deleted AS media_deleted "
                    "FROM email_messages em "
                    "JOIN Media m ON m.id = em.media_id "
                    "WHERE em.tenant_id = ? "
                    "ORDER BY em.internal_date ASC, em.id ASC"
                ),
                (resolved_tenant,),
            )

        skipped_missing_date = 0
        skipped_already_deleted = 0
        eligible_message_ids: list[int] = []
        candidate_media_ids: list[int] = []
        seen_media_ids: set[int] = set()
        for row in candidate_rows:
            parsed_dt = self._parse_email_retention_datetime(row.get("internal_date"))
            if parsed_dt is None and not include_missing_internal_date:
                skipped_missing_date += 1
                continue
            if parsed_dt is not None and parsed_dt > cutoff_dt:
                continue

            media_id = int(row["media_id"])
            media_deleted = bool(row.get("media_deleted"))
            if not hard_delete and media_deleted:
                skipped_already_deleted += 1
                continue

            eligible_message_ids.append(int(row["email_message_id"]))
            if media_id in seen_media_ids:
                continue
            seen_media_ids.add(media_id)
            candidate_media_ids.append(media_id)

        total_candidate_media = len(candidate_media_ids)
        if limit_int is not None:
            candidate_media_ids = candidate_media_ids[:limit_int]

        failed_media_ids: list[int] = []
        applied_media_ids: list[int] = []
        for media_id in candidate_media_ids:
            try:
                removed = (
                    _permanently_delete_item(self, media_id)
                    if hard_delete
                    else self.soft_delete_media(media_id, cascade=True)
                )
            except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
                logger.warning(
                    "Email retention delete failed for tenant={} media_id={}: {}",
                    resolved_tenant,
                    media_id,
                    exc,
                )
                failed_media_ids.append(int(media_id))
                continue
            if removed:
                applied_media_ids.append(int(media_id))
            else:
                failed_media_ids.append(int(media_id))

        with self.transaction() as conn:
            cleanup_counts = self._cleanup_email_orphans_for_tenant(
                conn,
                tenant_id=resolved_tenant,
                delete_empty_sources=False,
            )

        return {
            "tenant_id": resolved_tenant,
            "retention_days": int(retention_days_int),
            "hard_delete": bool(hard_delete),
            "cutoff_internal_date": cutoff_dt.isoformat(),
            "eligible_message_count": int(len(eligible_message_ids)),
            "candidate_media_count": int(total_candidate_media),
            "candidate_media_count_after_limit": int(len(candidate_media_ids)),
            "applied_count": int(len(applied_media_ids)),
            "applied_media_ids": applied_media_ids,
            "failed_media_ids": failed_media_ids,
            "skipped_missing_internal_date_count": int(skipped_missing_date),
            "skipped_already_deleted_count": int(skipped_already_deleted),
            "orphan_labels_deleted": int(cleanup_counts["labels_deleted"]),
            "orphan_participants_deleted": int(cleanup_counts["participants_deleted"]),
            "orphan_sources_deleted": int(cleanup_counts["sources_deleted"]),
        }

    def hard_delete_email_tenant_data(
        self,
        *,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """Hard-delete all normalized email data (and linked Media rows) for a tenant."""

        resolved_tenant = self._resolve_email_tenant_id(tenant_id)

        with self.transaction() as conn:
            rows = self._fetchall_with_connection(
                conn,
                (
                    "SELECT em.media_id AS media_id "
                    "FROM email_messages em "
                    "WHERE em.tenant_id = ? "
                    "ORDER BY em.id ASC"
                ),
                (resolved_tenant,),
            )
        media_ids = [int(row["media_id"]) for row in rows]

        deleted_media_ids: list[int] = []
        failed_media_ids: list[int] = []
        for media_id in media_ids:
            try:
                removed = _permanently_delete_item(self, int(media_id))
            except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
                logger.warning(
                    "Tenant email hard delete failed for tenant={} media_id={}: {}",
                    resolved_tenant,
                    media_id,
                    exc,
                )
                failed_media_ids.append(int(media_id))
                continue
            if removed:
                deleted_media_ids.append(int(media_id))
            else:
                failed_media_ids.append(int(media_id))

        sync_state_deleted = 0
        sources_deleted = 0
        backfill_deleted = 0
        cleanup_counts: dict[str, int] = {
            "labels_deleted": 0,
            "participants_deleted": 0,
            "sources_deleted": 0,
        }

        with self.transaction() as conn:
            cleanup_counts = self._cleanup_email_orphans_for_tenant(
                conn,
                tenant_id=resolved_tenant,
                delete_empty_sources=True,
            )

            if not failed_media_ids:
                sync_cursor = self._execute_with_connection(
                    conn,
                    "DELETE FROM email_sync_state WHERE tenant_id = ?",
                    (resolved_tenant,),
                )
                sync_state_deleted = int(getattr(sync_cursor, "rowcount", 0) or 0)

                source_cursor = self._execute_with_connection(
                    conn,
                    "DELETE FROM email_sources WHERE tenant_id = ?",
                    (resolved_tenant,),
                )
                sources_deleted = int(getattr(source_cursor, "rowcount", 0) or 0)

                backfill_cursor = self._execute_with_connection(
                    conn,
                    "DELETE FROM email_backfill_state WHERE tenant_id = ?",
                    (resolved_tenant,),
                )
                backfill_deleted = int(getattr(backfill_cursor, "rowcount", 0) or 0)
            else:
                sources_deleted = int(cleanup_counts.get("sources_deleted", 0))

        return {
            "tenant_id": resolved_tenant,
            "candidate_media_count": int(len(media_ids)),
            "deleted_media_count": int(len(deleted_media_ids)),
            "deleted_media_ids": deleted_media_ids,
            "failed_media_ids": failed_media_ids,
            "sync_state_deleted": int(sync_state_deleted),
            "sources_deleted": int(sources_deleted),
            "backfill_state_deleted": int(backfill_deleted),
            "orphan_labels_deleted": int(cleanup_counts.get("labels_deleted", 0)),
            "orphan_participants_deleted": int(cleanup_counts.get("participants_deleted", 0)),
            "orphan_sources_deleted": int(cleanup_counts.get("sources_deleted", 0)),
        }

    @staticmethod
    def _parse_email_relative_window(value: str) -> timedelta | None:
        text = str(value or "").strip().lower()
        match = re.fullmatch(r"(\d+)([smhdwy])", text)
        if not match:
            return None
        magnitude = int(match.group(1))
        unit = match.group(2)
        if magnitude <= 0:
            return None
        if unit == "s":
            return timedelta(seconds=magnitude)
        if unit == "m":
            return timedelta(minutes=magnitude)
        if unit == "h":
            return timedelta(hours=magnitude)
        if unit == "d":
            return timedelta(days=magnitude)
        if unit == "w":
            return timedelta(days=magnitude * 7)
        if unit == "y":
            return timedelta(days=magnitude * 365)
        return None

    @staticmethod
    def _sqlite_fts_literal_term(value: str) -> str | None:
        """Return a safely quoted SQLite FTS5 literal term."""

        text = str(value or "").strip()
        if not text:
            return None
        escaped = text.replace('"', '""')
        return f'"{escaped}"'

    def _parse_email_operator_query(self, query: str | None) -> list[list[dict[str, Any]]]:
        cleaned = str(query or "").strip()
        if not cleaned:
            return [[]]
        if "(" in cleaned or ")" in cleaned:
            raise InputError("Parentheses are not supported in email query v1.")  # noqa: TRY003
        try:
            tokens = shlex.split(cleaned)
        except ValueError as exc:
            raise InputError(f"Invalid email query syntax: {exc}") from exc  # noqa: TRY003
        if not tokens:
            return [[]]

        groups: list[list[dict[str, Any]]] = [[]]
        for token in tokens:
            raw_token = str(token or "").strip()
            if not raw_token:
                continue
            if raw_token.upper() == "OR":
                if not groups[-1]:
                    raise InputError("Invalid email query: OR requires terms on both sides.")  # noqa: TRY003
                groups.append([])
                continue

            negated = raw_token.startswith("-")
            core = raw_token[1:] if negated else raw_token
            if not core:
                raise InputError("Invalid email query: empty negated token.")  # noqa: TRY003

            term: dict[str, Any] = {"kind": "text", "value": core, "negated": negated}
            field_name = ""
            field_value = ""
            if ":" in core:
                field_name, field_value = core.split(":", 1)
                field_name = field_name.strip().lower()
                field_value = field_value.strip()

            if field_name in {"from", "to", "cc", "bcc"} and field_value:
                term = {
                    "kind": "participant",
                    "role": field_name,
                    "value": field_value,
                    "negated": negated,
                }
            elif field_name == "subject" and field_value:
                term = {"kind": "subject", "value": field_value, "negated": negated}
            elif field_name == "label" and field_value:
                term = {"kind": "label", "value": field_value, "negated": negated}
            elif field_name == "has" and field_value.lower() == "attachment":
                term = {"kind": "has_attachment", "value": True, "negated": negated}
            elif field_name in {"before", "after"} and field_value:
                try:
                    parsed_date = datetime.strptime(field_value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError as exc:
                    raise InputError(
                        f"Invalid {field_name}: expected YYYY-MM-DD."
                    ) from exc  # noqa: TRY003
                term = {
                    "kind": field_name,
                    "value": parsed_date.isoformat(),
                    "negated": negated,
                }
            elif field_name in {"older_than", "newer_than"} and field_value:
                delta = self._parse_email_relative_window(field_value)
                if delta is None:
                    raise InputError(
                        f"Invalid {field_name}: expected patterns like 7d, 12h, 30m."
                    )  # noqa: TRY003
                threshold = (datetime.now(timezone.utc) - delta).isoformat()
                term = {
                    "kind": field_name,
                    "value": threshold,
                    "negated": negated,
                }
            elif field_name and not field_value:
                raise InputError(f"Invalid email query token '{raw_token}'.")  # noqa: TRY003

            groups[-1].append(term)

        if not groups or not groups[-1]:
            raise InputError("Invalid email query: dangling OR without trailing term.")  # noqa: TRY003
        return groups

    def _email_like_clause(self, column_sql: str) -> str:
        return (
            f"{column_sql} ILIKE ?"
            if self.backend_type == BackendType.POSTGRESQL
            else f"{column_sql} LIKE ? COLLATE NOCASE"
        )

    def search_email_messages(
        self,
        *,
        query: str | None = None,
        tenant_id: str | None = None,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Search normalized email messages with Stage-1 operator support.

        Sorting is deterministic: internal_date DESC, email_message_id DESC.
        """

        query_present = "true" if isinstance(query, str) and query.strip() else "false"
        include_deleted_label = "true" if include_deleted else "false"
        started_at = time.perf_counter()
        _emit_email_metric_counter(
            "email_native_search_requests_total",
            labels={
                "phase": "attempt",
                "query_present": query_present,
                "include_deleted": include_deleted_label,
            },
        )

        try:
            try:
                limit_int = max(1, min(500, int(limit)))
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                limit_int = 50
            try:
                offset_int = max(0, int(offset))
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                offset_int = 0

            resolved_tenant = self._resolve_email_tenant_id(tenant_id)
            parsed_groups = self._parse_email_operator_query(query)

            where_clauses = ["em.tenant_id = ?"]
            if not include_deleted:
                if self.backend_type == BackendType.POSTGRESQL:
                    where_clauses.extend(
                        [
                            "COALESCE(m.deleted, FALSE) = FALSE",
                            "COALESCE(m.is_trash, FALSE) = FALSE",
                        ]
                    )
                else:
                    where_clauses.extend(
                        [
                            "COALESCE(m.deleted, 0) = 0",
                            "COALESCE(m.is_trash, 0) = 0",
                        ]
                    )
            where_params: list[Any] = [resolved_tenant]

            group_sql_clauses: list[str] = []
            for group in parsed_groups:
                group_parts: list[str] = []
                for term in group:
                    kind = str(term.get("kind") or "").strip().lower()
                    value = term.get("value")
                    negated = bool(term.get("negated"))
                    part_sql = ""
                    part_params: list[Any] = []

                    if kind == "participant":
                        role = str(term.get("role") or "").strip().lower()
                        like_value = f"%{str(value or '').strip()}%"
                        participant_display_expr = "COALESCE(ep.display_name, '')"
                        participant_text_clause = (
                            f"{self._email_like_clause('ep.email_normalized')} "
                            f"OR {self._email_like_clause(participant_display_expr)}"
                        )
                        part_sql = (
                            "EXISTS ("  # nosec B608
                            "SELECT 1 FROM email_message_participants emp "
                            "JOIN email_participants ep ON ep.id = emp.participant_id "
                            "WHERE emp.email_message_id = em.id "
                            "AND emp.role = ? "
                            "AND ep.tenant_id = em.tenant_id "
                            f"AND ({participant_text_clause})"
                            ")"
                        )
                        part_params.extend([role, like_value, like_value])
                    elif kind == "subject":
                        like_value = f"%{str(value or '').strip()}%"
                        part_sql = self._email_like_clause("COALESCE(em.subject, '')")
                        part_params.append(like_value)
                    elif kind == "label":
                        like_value = f"%{str(value or '').strip()}%"
                        label_text_clause = (
                            f"{self._email_like_clause('el.label_name')} "
                            f"OR {self._email_like_clause('el.label_key')}"
                        )
                        part_sql = (
                            "EXISTS ("  # nosec B608
                            "SELECT 1 FROM email_message_labels eml "
                            "JOIN email_labels el ON el.id = eml.label_id "
                            "WHERE eml.email_message_id = em.id "
                            "AND el.tenant_id = em.tenant_id "
                            f"AND ({label_text_clause})"
                            ")"
                        )
                        part_params.extend([like_value, like_value])
                    elif kind == "has_attachment":
                        bool_true = True if self.backend_type == BackendType.POSTGRESQL else 1
                        part_sql = (
                            "(em.has_attachments = ? OR EXISTS ("
                            "SELECT 1 FROM email_attachments ea WHERE ea.email_message_id = em.id"
                            "))"
                        )
                        part_params.append(bool_true)
                    elif kind == "before":
                        part_sql = "em.internal_date < ?"
                        part_params.append(str(value))
                    elif kind == "after":
                        part_sql = "em.internal_date >= ?"
                        part_params.append(str(value))
                    elif kind == "older_than":
                        part_sql = "em.internal_date < ?"
                        part_params.append(str(value))
                    elif kind == "newer_than":
                        part_sql = "em.internal_date >= ?"
                        part_params.append(str(value))
                    else:
                        text_value = str(value or "").strip()
                        like_value = f"%{text_value}%"
                        like_clauses = [
                            self._email_like_clause("COALESCE(em.subject, '')"),
                            self._email_like_clause("COALESCE(em.body_text, '')"),
                            self._email_like_clause("COALESCE(em.from_text, '')"),
                            self._email_like_clause("COALESCE(em.to_text, '')"),
                            self._email_like_clause("COALESCE(em.cc_text, '')"),
                            self._email_like_clause("COALESCE(em.bcc_text, '')"),
                            self._email_like_clause("COALESCE(em.label_text, '')"),
                        ]
                        part_sql = "(" + " OR ".join(like_clauses) + ")"
                        part_params.extend([like_value] * len(like_clauses))
                        if self.backend_type == BackendType.SQLITE and text_value:
                            fts_term = self._sqlite_fts_literal_term(text_value)
                            if fts_term:
                                part_sql = (
                                    "("  # nosec B608
                                    "em.id IN (SELECT rowid FROM email_fts WHERE email_fts MATCH ?) "
                                    f"OR {part_sql}"
                                    ")"
                                )
                                part_params = [fts_term, *part_params]

                    if not part_sql:
                        continue
                    if negated:
                        part_sql = f"NOT ({part_sql})"
                    group_parts.append(part_sql)
                    where_params.extend(part_params)

                if group_parts:
                    group_sql_clauses.append("(" + " AND ".join(group_parts) + ")")

            if group_sql_clauses:
                where_clauses.append("(" + " OR ".join(group_sql_clauses) + ")")

            where_sql = " AND ".join(where_clauses)
            base_from = (
                " FROM email_messages em "
                "JOIN Media m ON m.id = em.media_id "
                "WHERE " + where_sql
            )

            with self.transaction() as conn:
                count_row = self._fetchone_with_connection(
                    conn,
                    "SELECT COUNT(*) AS total" + base_from,
                    tuple(where_params),
                )
                total = int((count_row or {}).get("total", 0) or 0)

                rows = self._fetchall_with_connection(
                    conn,
                    (
                        "SELECT "  # nosec B608
                        "em.id AS email_message_id, "
                        "em.media_id AS media_id, "
                        "m.uuid AS media_uuid, "
                        "m.url AS media_url, "
                        "m.title AS media_title, "
                        "em.source_id AS source_id, "
                        "em.source_message_id AS source_message_id, "
                        "em.message_id AS message_id, "
                        "em.subject AS subject, "
                        "em.internal_date AS internal_date, "
                        "em.from_text AS from_text, "
                        "em.to_text AS to_text, "
                        "em.cc_text AS cc_text, "
                        "em.bcc_text AS bcc_text, "
                        "em.label_text AS label_text, "
                        "em.has_attachments AS has_attachments, "
                        "(SELECT COUNT(*) FROM email_attachments ea WHERE ea.email_message_id = em.id) "
                        "AS attachment_count"
                        + base_from +
                        " ORDER BY em.internal_date DESC, em.id DESC "
                        "LIMIT ? OFFSET ?"
                    ),
                    (*where_params, limit_int, offset_int),
                )

            _emit_email_metric_counter(
                "email_native_search_requests_total",
                labels={
                    "phase": "success",
                    "query_present": query_present,
                    "include_deleted": include_deleted_label,
                },
            )
            _emit_email_metric_histogram(
                "email_native_search_results_total",
                float(total),
                labels={
                    "query_present": query_present,
                    "include_deleted": include_deleted_label,
                },
            )
            return rows, total
        except InputError:
            _emit_email_metric_counter(
                "email_native_search_requests_total",
                labels={
                    "phase": "parse_error",
                    "query_present": query_present,
                    "include_deleted": include_deleted_label,
                },
            )
            _emit_email_metric_counter(
                "email_native_search_parse_failures_total",
                labels={
                    "query_present": query_present,
                    "include_deleted": include_deleted_label,
                },
            )
            raise
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            _emit_email_metric_counter(
                "email_native_search_requests_total",
                labels={
                    "phase": "error",
                    "query_present": query_present,
                    "include_deleted": include_deleted_label,
                    "error_type": type(exc).__name__,
                },
            )
            raise
        finally:
            _emit_email_metric_histogram(
                "email_native_search_duration_seconds",
                time.perf_counter() - started_at,
                labels={
                    "query_present": query_present,
                    "include_deleted": include_deleted_label,
                },
            )

    def get_email_message_detail(
        self,
        *,
        email_message_id: int,
        tenant_id: str | None = None,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None:
        """Fetch a normalized email message graph for detail API responses."""

        try:
            message_id_int = int(email_message_id)
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            raise InputError("email_message_id must be an integer.") from exc  # noqa: TRY003

        if message_id_int <= 0:
            raise InputError("email_message_id must be greater than zero.")  # noqa: TRY003

        resolved_tenant = self._resolve_email_tenant_id(tenant_id)

        deleted_clause = "" if include_deleted else "AND m.deleted = 0 "
        with self.transaction() as conn:
            message_row = self._fetchone_with_connection(
                conn,
                (
                    "SELECT "  # nosec B608
                    "em.id AS email_message_id, "
                    "em.media_id AS media_id, "
                    "m.uuid AS media_uuid, "
                    "m.url AS media_url, "
                    "m.title AS media_title, "
                    "em.source_id AS source_id, "
                    "es.provider AS source_provider, "
                    "es.source_key AS source_key, "
                    "es.display_name AS source_display_name, "
                    "em.source_message_id AS source_message_id, "
                    "em.message_id AS message_id, "
                    "em.subject AS subject, "
                    "em.body_text AS body_text, "
                    "em.internal_date AS internal_date, "
                    "em.from_text AS from_text, "
                    "em.to_text AS to_text, "
                    "em.cc_text AS cc_text, "
                    "em.bcc_text AS bcc_text, "
                    "em.label_text AS label_text, "
                    "em.has_attachments AS has_attachments, "
                    "em.raw_metadata_json AS raw_metadata_json "
                    "FROM email_messages em "
                    "JOIN Media m ON m.id = em.media_id "
                    "JOIN email_sources es ON es.id = em.source_id "
                    "WHERE em.id = ? AND em.tenant_id = ? "
                    + deleted_clause +
                    "LIMIT 1"
                ),
                (message_id_int, resolved_tenant),
            )
            if message_row is None:
                return None

            participant_rows = self._fetchall_with_connection(
                conn,
                (
                    "SELECT emp.role AS role, ep.email_normalized AS email, ep.display_name AS display_name "
                    "FROM email_message_participants emp "
                    "JOIN email_participants ep ON ep.id = emp.participant_id "
                    "WHERE emp.email_message_id = ? AND ep.tenant_id = ? "
                    "ORDER BY "
                    "CASE emp.role "
                    "WHEN 'from' THEN 0 "
                    "WHEN 'to' THEN 1 "
                    "WHEN 'cc' THEN 2 "
                    "WHEN 'bcc' THEN 3 "
                    "ELSE 9 END, "
                    "ep.email_normalized ASC"
                ),
                (message_id_int, resolved_tenant),
            )

            label_rows = self._fetchall_with_connection(
                conn,
                (
                    "SELECT el.label_key AS label_key, el.label_name AS label_name "
                    "FROM email_message_labels eml "
                    "JOIN email_labels el ON el.id = eml.label_id "
                    "WHERE eml.email_message_id = ? AND el.tenant_id = ? "
                    "ORDER BY el.label_name ASC"
                ),
                (message_id_int, resolved_tenant),
            )

            attachment_rows = self._fetchall_with_connection(
                conn,
                (
                    "SELECT id, filename, content_type, size_bytes, content_id, disposition, "
                    "extracted_text_available "
                    "FROM email_attachments "
                    "WHERE email_message_id = ? "
                    "ORDER BY id ASC"
                ),
                (message_id_int,),
            )

        participants: dict[str, list[dict[str, str | None]]] = {
            "from": [],
            "to": [],
            "cc": [],
            "bcc": [],
        }
        for row in participant_rows:
            role = str(row.get("role") or "").strip().lower()
            if role not in participants:
                continue
            participants[role].append(
                {
                    "email": row.get("email"),
                    "display_name": row.get("display_name"),
                }
            )

        labels = [
            {
                "label_key": row.get("label_key"),
                "label_name": row.get("label_name"),
            }
            for row in label_rows
        ]

        attachments = [
            {
                "id": row.get("id"),
                "filename": row.get("filename"),
                "content_type": row.get("content_type"),
                "size_bytes": row.get("size_bytes"),
                "content_id": row.get("content_id"),
                "disposition": row.get("disposition"),
                "extracted_text_available": bool(row.get("extracted_text_available")),
            }
            for row in attachment_rows
        ]

        raw_metadata = None
        raw_metadata_json = message_row.get("raw_metadata_json")
        if isinstance(raw_metadata_json, str) and raw_metadata_json.strip():
            try:
                raw_metadata = json.loads(raw_metadata_json)
            except json.JSONDecodeError:
                raw_metadata = None

        return {
            "email_message_id": message_row.get("email_message_id"),
            "message_id": message_row.get("message_id"),
            "source_message_id": message_row.get("source_message_id"),
            "subject": message_row.get("subject"),
            "internal_date": message_row.get("internal_date"),
            "body_text": message_row.get("body_text"),
            "has_attachments": bool(message_row.get("has_attachments")),
            "search_text": {
                "from": message_row.get("from_text"),
                "to": message_row.get("to_text"),
                "cc": message_row.get("cc_text"),
                "bcc": message_row.get("bcc_text"),
                "labels": message_row.get("label_text"),
            },
            "media": {
                "id": message_row.get("media_id"),
                "uuid": message_row.get("media_uuid"),
                "url": message_row.get("media_url"),
                "title": message_row.get("media_title"),
            },
            "source": {
                "id": message_row.get("source_id"),
                "provider": message_row.get("source_provider"),
                "source_key": message_row.get("source_key"),
                "display_name": message_row.get("source_display_name"),
            },
            "participants": participants,
            "labels": labels,
            "attachments": attachments,
            "raw_metadata": raw_metadata,
        }

    def search_claims(
        self,
        query: str,
        *,
        limit: int = 20,
        fallback_to_like: bool = True,
        owner_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search claims using the configured backend."""
        cleaned_query = (query or "").strip()
        if not cleaned_query:
            return []
        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError):
            limit = 20
        results: list[dict[str, Any]] = []
        scope = None
        try:
            scope = get_scope()
        except _MEDIA_NONCRITICAL_EXCEPTIONS as scope_err:
            logging.debug(f"Failed to resolve scope for claims search: {scope_err}")
            scope = None
        try:
            with self.transaction() as conn:
                if self.backend_type == BackendType.SQLITE:
                    # Defensive: ensure the FTS index reflects current Claims content.
                    # In some environments, FTS triggers may not have been applied yet
                    # (e.g., freshly created DBs in tests). A lightweight rebuild ensures
                    # correctness for subsequent MATCH queries.
                    with suppress(sqlite3.Error):
                        conn.execute("INSERT INTO claims_fts(claims_fts) VALUES('rebuild')")
                    conditions: list[str] = ["c.deleted = 0"]
                    params: list[Any] = []
                    if owner_user_id is not None:
                        conditions.append("COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?")
                        params.append(str(owner_user_id))
                    if scope and not scope.is_admin:
                        visibility_parts: list[str] = []
                        user_id_str = str(scope.user_id) if scope.user_id is not None else ""
                        if user_id_str:
                            visibility_parts.append(
                                "(COALESCE(m.visibility, 'personal') = 'personal' "
                                "AND (COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?))"
                            )
                            params.append(user_id_str)
                        if scope.team_ids:
                            team_placeholders = ",".join("?" * len(scope.team_ids))
                            visibility_parts.append(
                                f"(m.visibility = 'team' AND m.team_id IN ({team_placeholders}))"
                            )
                            params.extend(scope.team_ids)
                        if scope.org_ids:
                            org_placeholders = ",".join("?" * len(scope.org_ids))
                            visibility_parts.append(
                                f"(m.visibility = 'org' AND m.org_id IN ({org_placeholders}))"
                            )
                            params.extend(scope.org_ids)
                        if visibility_parts:
                            conditions.append("(" + " OR ".join(visibility_parts) + ")")
                    where_clause = " AND ".join(conditions)
                    sql = (
                        "SELECT c.id, c.media_id, c.chunk_index, c.claim_text, c.claim_cluster_id, "  # nosec B608
                        "       bm25(claims_fts) AS relevance_score "
                        "FROM claims_fts JOIN Claims c ON claims_fts.rowid = c.id "
                        "JOIN Media m ON c.media_id = m.id "
                        "WHERE claims_fts MATCH ? AND "
                        + where_clause +
                        " ORDER BY relevance_score ASC LIMIT ?"
                    )
                    rows = self._fetchall_with_connection(conn, sql, (cleaned_query, *params, limit))
                    results.extend(dict(row) for row in rows)
                elif self.backend_type == BackendType.POSTGRESQL:
                    tsquery = FTSQueryTranslator.normalize_query(cleaned_query, 'postgresql')
                    if tsquery:
                        conditions: list[str] = ["c.deleted IS FALSE"]
                        params: list[Any] = []
                        if owner_user_id is not None:
                            conditions.append("COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?")
                            params.append(str(owner_user_id))
                        if scope and not scope.is_admin:
                            visibility_parts: list[str] = []
                            user_id_str = str(scope.user_id) if scope.user_id is not None else ""
                            if user_id_str:
                                visibility_parts.append(
                                    "(COALESCE(m.visibility, 'personal') = 'personal' "
                                    "AND (COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?))"
                                )
                                params.append(user_id_str)
                            if scope.team_ids:
                                team_placeholders = ",".join("?" * len(scope.team_ids))
                                visibility_parts.append(
                                    f"(m.visibility = 'team' AND m.team_id IN ({team_placeholders}))"
                                )
                                params.extend(scope.team_ids)
                            if scope.org_ids:
                                org_placeholders = ",".join("?" * len(scope.org_ids))
                                visibility_parts.append(
                                    f"(m.visibility = 'org' AND m.org_id IN ({org_placeholders}))"
                                )
                                params.extend(scope.org_ids)
                            if visibility_parts:
                                conditions.append("(" + " OR ".join(visibility_parts) + ")")
                        where_clause = " AND ".join(conditions)
                        sql = (
                            "SELECT c.id, c.media_id, c.chunk_index, c.claim_text, c.claim_cluster_id, "  # nosec B608
                            "       ts_rank(c.claims_fts_tsv, to_tsquery('english', ?)) AS relevance_score "
                            "FROM claims c JOIN media m ON c.media_id = m.id "
                            "WHERE c.claims_fts_tsv @@ to_tsquery('english', ?) AND "
                            + where_clause +
                            " ORDER BY relevance_score DESC LIMIT ?"
                        )
                        rows = self._fetchall_with_connection(conn, sql, (tsquery, tsquery, *params, limit))
                        results.extend(dict(row) for row in rows)
                else:
                    raise NotImplementedError(
                        f"Claims search not implemented for backend {self.backend_type}"
                    )

                if fallback_to_like and not results:
                    like_conditions: list[str] = []
                    like_params: list[Any] = []
                    if owner_user_id is not None:
                        like_conditions.append("COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?")
                        like_params.append(str(owner_user_id))
                    if scope and not scope.is_admin:
                        visibility_parts = []
                        user_id_str = str(scope.user_id) if scope.user_id is not None else ""
                        if user_id_str:
                            visibility_parts.append(
                                "(COALESCE(m.visibility, 'personal') = 'personal' "
                                "AND (COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?))"
                            )
                            like_params.append(user_id_str)
                        if scope.team_ids:
                            team_placeholders = ",".join("?" * len(scope.team_ids))
                            visibility_parts.append(
                                f"(m.visibility = 'team' AND m.team_id IN ({team_placeholders}))"
                            )
                            like_params.extend(scope.team_ids)
                        if scope.org_ids:
                            org_placeholders = ",".join("?" * len(scope.org_ids))
                            visibility_parts.append(
                                f"(m.visibility = 'org' AND m.org_id IN ({org_placeholders}))"
                            )
                            like_params.extend(scope.org_ids)
                        if visibility_parts:
                            like_conditions.append("(" + " OR ".join(visibility_parts) + ")")
                    like_clause = " AND " + " AND ".join(like_conditions) if like_conditions else ""
                    like_pattern = f"%{cleaned_query}%"
                    if self.backend_type == BackendType.POSTGRESQL:
                        like_sql = (
                            "SELECT c.id, c.media_id, c.chunk_index, c.claim_text, c.claim_cluster_id "  # nosec B608
                            "FROM claims c JOIN media m ON c.media_id = m.id "
                            "WHERE c.deleted IS FALSE AND c.claim_text ILIKE ?"
                            + like_clause +
                            " LIMIT ?"
                        )
                    else:
                        like_sql = (
                            "SELECT c.id, c.media_id, c.chunk_index, c.claim_text, c.claim_cluster_id "  # nosec B608
                            "FROM Claims c JOIN Media m ON c.media_id = m.id "
                            "WHERE c.deleted = 0 AND c.claim_text LIKE ?"
                            + like_clause +
                            " LIMIT ?"
                        )
                    fallback_rows = self._fetchall_with_connection(
                        conn,
                        like_sql,
                        (like_pattern, *like_params, limit),
                    )
                    for row in fallback_rows:
                        row_dict = dict(row)
                        row_dict.setdefault('relevance_score', 0.0)
                        results.append(row_dict)
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            logging.error("Failed to search claims: {}", exc, exc_info=True)
            return []
        return results

    # -------------------------
    # Data Tables helpers
    # -------------------------
    def _resolve_data_tables_owner(self, owner_user_id: int | str | None) -> str | None:
        """Resolve the owner user id for data table queries."""
        if owner_user_id is not None:
            return str(owner_user_id)
        try:
            scope = get_scope()
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            logger.debug("Failed to resolve scope for data tables owner")
            return None
        if scope and not scope.is_admin and scope.user_id is not None:
            return str(scope.user_id)
        return None

    def _resolve_data_table_write_client_id(
        self,
        table_id: int,
        *,
        owner_user_id: int | str | None = None,
    ) -> str:
        """Resolve the client_id that should own table child writes."""
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        if owner_filter is not None and owner_filter.strip():
            return owner_filter.strip()

        row = self.execute_query(
            "SELECT client_id FROM data_tables WHERE id = ? LIMIT 1",
            (int(table_id),),
        ).fetchone()
        if not row:
            raise InputError("data_table_not_found")
        client_id = (
            str(row.get("client_id") if isinstance(row, dict) else row[0] if row else "")
            .strip()
        )
        if not client_id:
            raise InputError("data_table_owner_missing")
        return client_id

    def _get_data_table_owner_client_id(self, conn, table_id: int) -> str | None:
        """Fetch the owning client_id for a data table id."""
        row = self._fetchone_with_connection(
            conn,
            "SELECT client_id FROM data_tables WHERE id = ? AND deleted = 0",
            (int(table_id),),
        )
        if not row:
            return None
        return str(row.get("client_id"))

    def create_data_table(
        self,
        *,
        name: str,
        prompt: str,
        description: str | None = None,
        workspace_tag: str | None = None,
        column_hints: str | dict[str, Any] | list[Any] | None = None,
        status: str = "queued",
        row_count: int = 0,
        generation_model: str | None = None,
        table_uuid: str | None = None,
        owner_user_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a data table metadata record and return the row."""
        if not name:
            raise InputError("name is required")  # noqa: TRY003
        if not prompt:
            raise InputError("prompt is required")  # noqa: TRY003

        now = self._get_current_utc_timestamp_str()
        table_uuid = table_uuid or self._generate_uuid()
        owner_client_id = self._resolve_data_tables_owner(owner_user_id) or str(self.client_id)

        column_hints_json = None
        if column_hints is not None:
            if isinstance(column_hints, str):
                try:
                    json.loads(column_hints)
                except json.JSONDecodeError as exc:
                    raise InputError(f"Invalid column_hints JSON: {exc}") from exc  # noqa: TRY003
                column_hints_json = column_hints
            else:
                column_hints_json = json.dumps(column_hints)

        with self.transaction() as conn:
            self._execute_with_connection(
                conn,
                """
                INSERT INTO data_tables (
                    uuid, name, description, workspace_tag, prompt, column_hints_json, status,
                    row_count, generation_model, last_error,
                    created_at, updated_at, last_modified, version, client_id, deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    table_uuid,
                    name,
                    description,
                    workspace_tag,
                    prompt,
                    column_hints_json,
                    status,
                    int(row_count),
                    generation_model,
                    None,
                    now,
                    now,
                    now,
                    1,
                    owner_client_id,
                    0,
                ),
            )
            row = self._fetchone_with_connection(
                conn,
                "SELECT * FROM data_tables WHERE uuid = ?",
                (table_uuid,),
            )
        return row or {}

    def get_data_table(
        self,
        table_id: int,
        *,
        include_deleted: bool = False,
        owner_user_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Fetch a data table by id."""
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        conditions = ["id = ?"]
        params: list[Any] = [int(table_id)]
        if not include_deleted:
            conditions.append("deleted = 0")
        if owner_filter is not None:
            conditions.append("client_id = ?")
            params.append(owner_filter)
        sql = "SELECT * FROM data_tables WHERE " + " AND ".join(conditions) + " LIMIT 1"  # nosec B608
        row = self.execute_query(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def get_data_table_by_uuid(
        self,
        table_uuid: str,
        *,
        include_deleted: bool = False,
        owner_user_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Fetch a data table by uuid."""
        if not table_uuid:
            return None
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        conditions = ["uuid = ?"]
        params: list[Any] = [str(table_uuid)]
        if not include_deleted:
            conditions.append("deleted = 0")
        if owner_filter is not None:
            conditions.append("client_id = ?")
            params.append(owner_filter)
        sql = "SELECT * FROM data_tables WHERE " + " AND ".join(conditions) + " LIMIT 1"  # nosec B608
        row = self.execute_query(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def list_data_tables(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        workspace_tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
        owner_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """List data tables with optional filters."""
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            limit, offset = 50, 0
        limit = max(1, min(500, limit))
        offset = max(0, offset)

        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        conditions: list[str] = []
        params: list[Any] = []
        if not include_deleted:
            conditions.append("deleted = 0")
        if owner_filter is not None:
            conditions.append("client_id = ?")
            params.append(owner_filter)
        if status:
            conditions.append("status = ?")
            params.append(str(status))
        if workspace_tag:
            conditions.append("workspace_tag = ?")
            params.append(str(workspace_tag))
        if search:
            like_op = "ILIKE" if self.backend_type == BackendType.POSTGRESQL else "LIKE"
            conditions.append(f"(name {like_op} ? OR description {like_op} ?)")
            pattern = f"%{search}%"
            params.extend([pattern, pattern])

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = (
            "SELECT * FROM data_tables "  # nosec B608
            f"{where_clause} "
            "ORDER BY updated_at DESC, id DESC "
            "LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def count_data_tables(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        workspace_tag: str | None = None,
        include_deleted: bool = False,
        owner_user_id: int | None = None,
    ) -> int:
        """Count data tables matching optional filters."""
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        conditions: list[str] = []
        params: list[Any] = []
        if not include_deleted:
            conditions.append("deleted = 0")
        if owner_filter is not None:
            conditions.append("client_id = ?")
            params.append(owner_filter)
        if status:
            conditions.append("status = ?")
            params.append(str(status))
        if workspace_tag:
            conditions.append("workspace_tag = ?")
            params.append(str(workspace_tag))
        if search:
            like_op = "ILIKE" if self.backend_type == BackendType.POSTGRESQL else "LIKE"
            conditions.append(f"(name {like_op} ? OR description {like_op} ?)")
            pattern = f"%{search}%"
            params.extend([pattern, pattern])

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT COUNT(*) as total FROM data_tables {where_clause}"  # nosec B608
        row = self.execute_query(sql, tuple(params)).fetchone()
        if not row:
            return 0
        total = row.get("total", 0) if isinstance(row, dict) else row[0] if row else 0
        return int(total or 0)

    def get_data_table_counts(
        self,
        table_ids: list[int],
        *,
        owner_user_id: int | None = None,
    ) -> dict[int, dict[str, int]]:
        """Return column/source counts for the provided table ids."""
        ids = [int(table_id) for table_id in table_ids if table_id is not None]
        if not ids:
            return {}
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        placeholders = ",".join(["?"] * len(ids))
        owner_clause = ""
        params: list[Any] = list(ids)
        if owner_filter is not None:
            owner_clause = " AND dt.client_id = ?"
            params.append(owner_filter)
        columns_sql = (
            "SELECT c.table_id, COUNT(*) as count FROM data_table_columns c "  # nosec B608
            "INNER JOIN data_tables dt ON dt.id = c.table_id "
            f"WHERE c.deleted = 0 AND dt.deleted = 0 AND c.table_id IN ({placeholders}){owner_clause} "
            "GROUP BY c.table_id"
        )
        sources_sql = (
            "SELECT s.table_id, COUNT(*) as count FROM data_table_sources s "  # nosec B608
            "INNER JOIN data_tables dt ON dt.id = s.table_id "
            f"WHERE s.deleted = 0 AND dt.deleted = 0 AND s.table_id IN ({placeholders}){owner_clause} "
            "GROUP BY s.table_id"
        )
        columns_rows = self.execute_query(columns_sql, tuple(params)).fetchall()
        sources_rows = self.execute_query(sources_sql, tuple(params)).fetchall()

        counts: dict[int, dict[str, int]] = {
            table_id: {"column_count": 0, "source_count": 0} for table_id in ids
        }
        for row in columns_rows:
            table_id = int(row.get("table_id") if isinstance(row, dict) else row[0])
            count = int(row.get("count") if isinstance(row, dict) else row[1])
            counts.setdefault(table_id, {})["column_count"] = count
        for row in sources_rows:
            table_id = int(row.get("table_id") if isinstance(row, dict) else row[0])
            count = int(row.get("count") if isinstance(row, dict) else row[1])
            counts.setdefault(table_id, {})["source_count"] = count
        return counts

    def update_data_table(
        self,
        table_id: int,
        *,
        owner_user_id: int | str | None = None,
        name: str | None = None,
        description: str | None = None,
        prompt: str | None = None,
        status: str | None = None,
        row_count: int | None = None,
        generation_model: str | None = None,
        last_error: Any = _DATA_TABLES_UNSET,
        column_hints: str | dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any] | None:
        """Update data table metadata and return the updated row."""
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        update_parts: list[str] = []
        params: list[Any] = []

        if name is not None:
            update_parts.append("name = ?")
            params.append(name)
        if description is not None:
            update_parts.append("description = ?")
            params.append(description)
        if prompt is not None:
            update_parts.append("prompt = ?")
            params.append(prompt)
        if status is not None:
            update_parts.append("status = ?")
            params.append(status)
        if row_count is not None:
            update_parts.append("row_count = ?")
            params.append(int(row_count))
        if generation_model is not None:
            update_parts.append("generation_model = ?")
            params.append(generation_model)
        if last_error is not _DATA_TABLES_UNSET:
            update_parts.append("last_error = ?")
            params.append(last_error)
        if column_hints is not None:
            if isinstance(column_hints, str):
                try:
                    json.loads(column_hints)
                except json.JSONDecodeError as exc:
                    raise InputError(f"Invalid column_hints JSON: {exc}") from exc  # noqa: TRY003
                column_hints_json = column_hints
            else:
                column_hints_json = json.dumps(column_hints)
            update_parts.append("column_hints_json = ?")
            params.append(column_hints_json)

        if not update_parts:
            return self.get_data_table(int(table_id), include_deleted=True, owner_user_id=owner_user_id)

        now = self._get_current_utc_timestamp_str()
        update_parts.append("updated_at = ?")
        params.append(now)
        update_parts.append("last_modified = ?")
        params.append(now)
        update_parts.append("version = version + 1")

        params.append(int(table_id))
        sql = "UPDATE data_tables SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
        if owner_filter is not None:
            sql += " AND client_id = ?"
            params.append(owner_filter)
        self.execute_query(sql, tuple(params), commit=True)
        return self.get_data_table(int(table_id), include_deleted=True, owner_user_id=owner_user_id)

    def soft_delete_data_table(self, table_id: int, owner_user_id: int | None = None) -> bool:
        """Soft delete a data table and its related rows."""
        now = self._get_current_utc_timestamp_str()
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        with self.transaction() as conn:
            params: list[Any] = [now, now, int(table_id)]
            where_clause = "WHERE id = ? AND deleted = 0"
            if owner_filter is not None:
                where_clause += " AND client_id = ?"
                params.append(owner_filter)
            cur = self._execute_with_connection(
                conn,
                """
                UPDATE data_tables
                SET deleted = 1,
                    updated_at = ?,
                    last_modified = ?,
                    version = version + 1
                {where_clause}
                """.format_map(locals()),  # nosec B608
                tuple(params),
            )
            updated = int(getattr(cur, "rowcount", 0) or 0)
            if updated:
                self._soft_delete_data_table_children(
                    conn,
                    int(table_id),
                    now,
                    owner_user_id=owner_user_id,
                )
        return bool(updated)

    def _soft_delete_data_table_children(
        self,
        conn,
        table_id: int,
        now: str,
        *,
        owner_user_id: int | None = None,
    ) -> None:
        """Soft delete data table child records within a transaction."""
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        where_clause = "WHERE table_id = ? AND deleted = 0"
        params: list[Any] = [now, int(table_id)]
        if owner_filter is not None:
            where_clause += " AND client_id = ?"
            params.append(owner_filter)
        for table in ("data_table_columns", "data_table_rows", "data_table_sources"):
            self._execute_with_connection(
                conn,
                """
                UPDATE {table}
                SET deleted = 1,
                    last_modified = ?,
                    version = version + 1
                {where_clause}
                """.format_map(locals()),  # nosec B608
                tuple(params),
            )

    def insert_data_table_columns(
        self,
        table_id: int,
        columns: list[dict[str, Any]],
        *,
        owner_user_id: int | str | None = None,
    ) -> int:
        """Insert data table columns and return count inserted."""
        if not columns:
            return 0
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        if owner_filter is not None:
            owned = self.execute_query(
                "SELECT 1 FROM data_tables WHERE id = ? AND client_id = ? LIMIT 1",
                (int(table_id), owner_filter),
            ).fetchone()
            if not owned:
                return 0
        write_client_id = owner_filter or self._resolve_data_table_write_client_id(
            int(table_id),
            owner_user_id=owner_user_id,
        )
        now = self._get_current_utc_timestamp_str()
        rows: list[tuple] = []
        for idx, column in enumerate(columns):
            name = column.get("name")
            col_type = column.get("type")
            if not name or not col_type:
                raise InputError("column name and type are required")  # noqa: TRY003
            column_id = column.get("column_id") or column.get("id") or self._generate_uuid()
            position = column.get("position", idx)
            rows.append(
                (
                    int(table_id),
                    str(column_id),
                    str(name),
                    str(col_type),
                    column.get("description"),
                    column.get("format"),
                    int(position),
                    now,
                    now,
                    1,
                    write_client_id,
                    0,
                    column.get("prev_version"),
                    column.get("merge_parent_uuid"),
                )
            )
        with self.transaction() as conn:
            self.execute_many(
                """
                INSERT INTO data_table_columns (
                    table_id, column_id, name, type, description, format, position,
                    created_at, last_modified, version, client_id, deleted, prev_version, merge_parent_uuid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
                commit=False,
                connection=conn,
            )
        return len(rows)

    def list_data_table_columns(
        self,
        table_id: int,
        *,
        include_deleted: bool = False,
        owner_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """List columns for a data table."""
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        conditions = ["table_id = ?"]
        params: list[Any] = [int(table_id)]
        if not include_deleted:
            conditions.append("deleted = 0")
        if owner_filter is not None:
            conditions.append("client_id = ?")
            params.append(owner_filter)
        sql = (
            "SELECT * FROM data_table_columns WHERE "  # nosec B608
            + " AND ".join(conditions)
            + " ORDER BY position ASC, id ASC"
        )
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def soft_delete_data_table_columns(
        self,
        table_id: int,
        owner_user_id: int | None = None,
    ) -> int:
        """Soft delete columns for a data table."""
        now = self._get_current_utc_timestamp_str()
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        params: list[Any] = [now, int(table_id)]
        where_clause = "WHERE table_id = ? AND deleted = 0"
        if owner_filter is not None:
            where_clause += " AND client_id = ?"
            params.append(owner_filter)
        cur = self.execute_query(
            """
            UPDATE data_table_columns
            SET deleted = 1,
                last_modified = ?,
                version = version + 1
            {where_clause}
            """.format_map(locals()),  # nosec B608
            tuple(params),
            commit=True,
        )
        return int(getattr(cur, "rowcount", 0) or 0)

    def _normalize_data_table_row_json(
        self,
        row_json: Any,
        *,
        column_ids: set[str] | None = None,
        validate_keys: bool = True,
    ) -> str:
        """Normalize row_json to a JSON string and validate column keys."""
        if row_json is None:
            raise InputError("row_json is required for data table rows")  # noqa: TRY003
        payload = row_json
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise InputError(f"row_json must be valid JSON: {exc}") from exc  # noqa: TRY003

        if validate_keys:
            if column_ids is None:
                raise InputError("column_ids are required for row_json validation")  # noqa: TRY003
            if not isinstance(payload, dict):
                raise InputError("row_json must be an object keyed by column_id")  # noqa: TRY003
            normalized: dict[str, Any] = {str(key): value for key, value in payload.items()}
            invalid = [key for key in normalized if key not in column_ids]
            if invalid:
                raise InputError(f"row_json contains unknown column_id(s): {', '.join(invalid)}")  # noqa: TRY003
            payload = normalized

        if not isinstance(payload, (dict, list)):
            raise InputError("row_json must be an object or array")  # noqa: TRY003
        return json.dumps(payload)

    def insert_data_table_rows(
        self,
        table_id: int,
        rows: list[dict[str, Any]],
        *,
        validate_keys: bool = True,
        owner_user_id: int | str | None = None,
    ) -> int:
        """Insert data table rows and return count inserted."""
        if not rows:
            return 0
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        if owner_filter is not None:
            owned = self.execute_query(
                "SELECT 1 FROM data_tables WHERE id = ? AND client_id = ? LIMIT 1",
                (int(table_id), owner_filter),
            ).fetchone()
            if not owned:
                return 0
        write_client_id = owner_filter or self._resolve_data_table_write_client_id(
            int(table_id),
            owner_user_id=owner_user_id,
        )
        column_ids: set[str] | None = None
        if validate_keys:
            columns = self.list_data_table_columns(int(table_id), owner_user_id=owner_user_id)
            if not columns:
                raise InputError("data_table_columns_required")
            column_ids = {str(col.get("column_id") or "") for col in columns}
            if "" in column_ids:
                column_ids.discard("")
        now = self._get_current_utc_timestamp_str()
        insert_rows: list[tuple] = []
        for idx, row in enumerate(rows):
            row_json = row.get("row_json", row.get("data"))
            row_json = self._normalize_data_table_row_json(
                row_json,
                column_ids=column_ids,
                validate_keys=validate_keys,
            )
            row_id = row.get("row_id") or row.get("id") or self._generate_uuid()
            row_index = row.get("row_index", idx)
            row_hash = row.get("row_hash")
            if row_hash is None:
                row_hash = hashlib.sha256(row_json.encode("utf-8")).hexdigest()
            insert_rows.append(
                (
                    int(table_id),
                    str(row_id),
                    int(row_index),
                    row_json,
                    row_hash,
                    now,
                    now,
                    1,
                    write_client_id,
                    0,
                    row.get("prev_version"),
                    row.get("merge_parent_uuid"),
                )
            )
        with self.transaction() as conn:
            self.execute_many(
                """
                INSERT INTO data_table_rows (
                    table_id, row_id, row_index, row_json, row_hash,
                    created_at, last_modified, version, client_id, deleted, prev_version, merge_parent_uuid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                insert_rows,
                commit=False,
                connection=conn,
            )
        return len(insert_rows)

    def replace_data_table_contents(
        self,
        table_id: int,
        *,
        owner_user_id: int | str,
        columns: list[dict[str, Any]],
        rows: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Replace data table columns and rows, returning counts inserted."""
        owner_value = str(owner_user_id).strip()
        if not owner_value:
            raise InputError("owner_user_id is required")  # noqa: TRY003
        if not columns:
            raise InputError("columns are required")  # noqa: TRY003
        if rows is None:
            raise InputError("rows are required")  # noqa: TRY003

        write_client_id = self._resolve_data_table_write_client_id(
            int(table_id),
            owner_user_id=owner_value,
        )
        now = self._get_current_utc_timestamp_str()
        column_rows: list[tuple] = []
        for idx, column in enumerate(columns):
            name = column.get("name")
            col_type = column.get("type")
            if not name or not col_type:
                raise InputError("column name and type are required")  # noqa: TRY003
            column_id = column.get("column_id") or column.get("id") or self._generate_uuid()
            position = column.get("position", idx)
            column_rows.append(
                (
                    int(table_id),
                    str(column_id),
                    str(name),
                    str(col_type),
                    column.get("description"),
                    column.get("format"),
                    int(position),
                    now,
                    now,
                    1,
                    write_client_id,
                    0,
                    column.get("prev_version"),
                    column.get("merge_parent_uuid"),
                )
            )
        column_ids = {str(row[1]) for row in column_rows}

        row_rows: list[tuple] = []
        for idx, row in enumerate(rows):
            row_json = row.get("row_json", row.get("data"))
            row_json = self._normalize_data_table_row_json(
                row_json,
                column_ids=column_ids,
                validate_keys=True,
            )
            row_id = row.get("row_id") or row.get("id") or self._generate_uuid()
            row_index = row.get("row_index", idx)
            row_hash = row.get("row_hash")
            if row_hash is None:
                row_hash = hashlib.sha256(row_json.encode("utf-8")).hexdigest()
            row_rows.append(
                (
                    int(table_id),
                    str(row_id),
                    int(row_index),
                    row_json,
                    row_hash,
                    now,
                    now,
                    1,
                    write_client_id,
                    0,
                    row.get("prev_version"),
                    row.get("merge_parent_uuid"),
                )
            )

        with self.transaction() as conn:
            actual_owner = self._get_data_table_owner_client_id(conn, int(table_id))
            if not actual_owner:
                raise InputError("data_table_not_found")
            if actual_owner != owner_value:
                raise InputError("data_table_owner_mismatch")
            self._execute_with_connection(
                conn,
                """
                UPDATE data_table_columns
                SET deleted = 1,
                    last_modified = ?,
                    version = version + 1
                WHERE table_id = ? AND deleted = 0
                """,
                (now, int(table_id)),
            )
            self._execute_with_connection(
                conn,
                """
                UPDATE data_table_rows
                SET deleted = 1,
                    last_modified = ?,
                    version = version + 1
                WHERE table_id = ? AND deleted = 0
                """,
                (now, int(table_id)),
            )
            self.execute_many(
                """
                INSERT INTO data_table_columns (
                    table_id, column_id, name, type, description, format, position,
                    created_at, last_modified, version, client_id, deleted, prev_version, merge_parent_uuid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                column_rows,
                commit=False,
                connection=conn,
            )
            self.execute_many(
                """
                INSERT INTO data_table_rows (
                    table_id, row_id, row_index, row_json, row_hash,
                    created_at, last_modified, version, client_id, deleted, prev_version, merge_parent_uuid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row_rows,
                commit=False,
                connection=conn,
            )
        return len(column_rows), len(row_rows)

    def persist_data_table_generation(
        self,
        table_id: int,
        *,
        columns: list[dict[str, Any]],
        rows: list[dict[str, Any]],
        sources: list[dict[str, Any]] | None = None,
        status: str = "ready",
        row_count: int | None = None,
        generation_model: str | None = None,
        last_error: Any = None,
        owner_user_id: int | str | None = None,
    ) -> dict[str, Any] | None:
        """Persist generated table data and update table metadata.

        If owner_user_id is provided, it must match the table owner.
        """
        owner_value = None
        if owner_user_id is not None:
            owner_value = str(owner_user_id).strip()
            if not owner_value:
                raise InputError("owner_user_id is required")  # noqa: TRY003
        if not columns:
            raise InputError("columns are required")  # noqa: TRY003
        if rows is None:
            raise InputError("rows are required")  # noqa: TRY003

        write_client_id = self._resolve_data_table_write_client_id(
            int(table_id),
            owner_user_id=owner_user_id,
        )
        now = self._get_current_utc_timestamp_str()
        column_rows: list[tuple] = []
        for idx, column in enumerate(columns):
            name = column.get("name")
            col_type = column.get("type")
            if not name or not col_type:
                raise InputError("column name and type are required")  # noqa: TRY003
            column_id = column.get("column_id") or column.get("id") or self._generate_uuid()
            position = column.get("position", idx)
            column_rows.append(
                (
                    int(table_id),
                    str(column_id),
                    str(name),
                    str(col_type),
                    column.get("description"),
                    column.get("format"),
                    int(position),
                    now,
                    now,
                    1,
                    write_client_id,
                    0,
                    column.get("prev_version"),
                    column.get("merge_parent_uuid"),
                )
            )
        column_ids = {str(row[1]) for row in column_rows}

        row_rows: list[tuple] = []
        for idx, row in enumerate(rows):
            row_json = row.get("row_json", row.get("data"))
            row_json = self._normalize_data_table_row_json(
                row_json,
                column_ids=column_ids,
                validate_keys=True,
            )
            row_id = row.get("row_id") or row.get("id") or self._generate_uuid()
            row_index = row.get("row_index", idx)
            row_hash = row.get("row_hash")
            if row_hash is None:
                row_hash = hashlib.sha256(row_json.encode("utf-8")).hexdigest()
            row_rows.append(
                (
                    int(table_id),
                    str(row_id),
                    int(row_index),
                    row_json,
                    row_hash,
                    now,
                    now,
                    1,
                    write_client_id,
                    0,
                    row.get("prev_version"),
                    row.get("merge_parent_uuid"),
                )
            )

        source_rows: list[tuple] = []
        if sources is not None:
            for src in sources:
                source_type = src.get("source_type")
                source_id = src.get("source_id")
                if not source_type or source_id is None:
                    raise InputError("source_type and source_id are required")  # noqa: TRY003
                snapshot = src.get("snapshot_json")
                if snapshot is not None and not isinstance(snapshot, str):
                    snapshot = json.dumps(snapshot)
                retrieval = src.get("retrieval_params_json")
                if retrieval is not None and not isinstance(retrieval, str):
                    retrieval = json.dumps(retrieval)
                source_rows.append(
                    (
                        int(table_id),
                        str(source_type),
                        str(source_id),
                        src.get("title"),
                        snapshot,
                        retrieval,
                        now,
                        now,
                        1,
                        write_client_id,
                        0,
                        src.get("prev_version"),
                        src.get("merge_parent_uuid"),
                    )
                )

        update_parts = ["status = ?", "row_count = ?", "last_error = ?"]
        params: list[Any] = [
            status,
            int(row_count if row_count is not None else len(rows)),
            last_error,
        ]
        update_parts.append("updated_at = ?")
        params.append(now)
        update_parts.append("last_modified = ?")
        params.append(now)
        update_parts.append("version = version + 1")
        if generation_model is not None:
            update_parts.append("generation_model = ?")
            params.append(generation_model)
        params.append(int(table_id))

        with self.transaction() as conn:
            if owner_value is not None:
                actual_owner = self._get_data_table_owner_client_id(conn, int(table_id))
                if not actual_owner:
                    raise InputError("data_table_not_found")
                if actual_owner != owner_value:
                    raise InputError("data_table_owner_mismatch")
            self._execute_with_connection(
                conn,
                """
                UPDATE data_table_columns
                SET deleted = 1,
                    last_modified = ?,
                    version = version + 1
                WHERE table_id = ? AND deleted = 0
                """,
                (now, int(table_id)),
            )
            self._execute_with_connection(
                conn,
                """
                UPDATE data_table_rows
                SET deleted = 1,
                    last_modified = ?,
                    version = version + 1
                WHERE table_id = ? AND deleted = 0
                """,
                (now, int(table_id)),
            )
            if sources is not None:
                self._execute_with_connection(
                    conn,
                    """
                    UPDATE data_table_sources
                    SET deleted = 1,
                        last_modified = ?,
                        version = version + 1
                    WHERE table_id = ? AND deleted = 0
                    """,
                    (now, int(table_id)),
                )
            self.execute_many(
                """
                INSERT INTO data_table_columns (
                    table_id, column_id, name, type, description, format, position,
                    created_at, last_modified, version, client_id, deleted, prev_version, merge_parent_uuid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                column_rows,
                commit=False,
                connection=conn,
            )
            self.execute_many(
                """
                INSERT INTO data_table_rows (
                    table_id, row_id, row_index, row_json, row_hash,
                    created_at, last_modified, version, client_id, deleted, prev_version, merge_parent_uuid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row_rows,
                commit=False,
                connection=conn,
            )
            if source_rows:
                self.execute_many(
                    """
                    INSERT INTO data_table_sources (
                        table_id, source_type, source_id, title, snapshot_json, retrieval_params_json,
                        created_at, last_modified, version, client_id, deleted, prev_version, merge_parent_uuid
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    source_rows,
                    commit=False,
                    connection=conn,
                )
            sql = "UPDATE data_tables SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
            self._execute_with_connection(conn, sql, tuple(params))

        return self.get_data_table(int(table_id), include_deleted=True)

    def list_data_table_rows(
        self,
        table_id: int,
        *,
        limit: int = 200,
        offset: int = 0,
        include_deleted: bool = False,
        owner_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """List rows for a data table."""
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            limit, offset = 200, 0
        limit = max(1, min(2000, limit))
        offset = max(0, offset)
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        conditions = ["table_id = ?"]
        params: list[Any] = [int(table_id)]
        if not include_deleted:
            conditions.append("deleted = 0")
        if owner_filter is not None:
            conditions.append("client_id = ?")
            params.append(owner_filter)
        sql = (
            "SELECT * FROM data_table_rows WHERE "  # nosec B608
            + " AND ".join(conditions)
            + " ORDER BY row_index ASC, id ASC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def soft_delete_data_table_rows(
        self,
        table_id: int,
        owner_user_id: int | None = None,
    ) -> int:
        """Soft delete rows for a data table."""
        now = self._get_current_utc_timestamp_str()
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        params: list[Any] = [now, int(table_id)]
        where_clause = "WHERE table_id = ? AND deleted = 0"
        if owner_filter is not None:
            where_clause += " AND client_id = ?"
            params.append(owner_filter)
        cur = self.execute_query(
            """
            UPDATE data_table_rows
            SET deleted = 1,
                last_modified = ?,
                version = version + 1
            {where_clause}
            """.format_map(locals()),  # nosec B608
            tuple(params),
            commit=True,
        )
        return int(getattr(cur, "rowcount", 0) or 0)

    def insert_data_table_sources(
        self,
        table_id: int,
        sources: list[dict[str, Any]],
        *,
        owner_user_id: int | str | None = None,
    ) -> int:
        """Insert sources for a data table and return count inserted."""
        if not sources:
            return 0
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        if owner_filter is not None:
            owned = self.execute_query(
                "SELECT 1 FROM data_tables WHERE id = ? AND client_id = ? LIMIT 1",
                (int(table_id), owner_filter),
            ).fetchone()
            if not owned:
                return 0
        write_client_id = owner_filter or self._resolve_data_table_write_client_id(
            int(table_id),
            owner_user_id=owner_user_id,
        )
        now = self._get_current_utc_timestamp_str()
        rows: list[tuple] = []
        for src in sources:
            source_type = src.get("source_type")
            source_id = src.get("source_id")
            if not source_type or source_id is None:
                raise InputError("source_type and source_id are required")  # noqa: TRY003
            snapshot = src.get("snapshot_json")
            if snapshot is not None and not isinstance(snapshot, str):
                snapshot = json.dumps(snapshot)
            retrieval = src.get("retrieval_params_json")
            if retrieval is not None and not isinstance(retrieval, str):
                retrieval = json.dumps(retrieval)
            rows.append(
                (
                    int(table_id),
                    str(source_type),
                    str(source_id),
                    src.get("title"),
                    snapshot,
                    retrieval,
                    now,
                    now,
                    1,
                    write_client_id,
                    0,
                    src.get("prev_version"),
                    src.get("merge_parent_uuid"),
                )
            )
        with self.transaction() as conn:
            self.execute_many(
                """
                INSERT INTO data_table_sources (
                    table_id, source_type, source_id, title, snapshot_json, retrieval_params_json,
                    created_at, last_modified, version, client_id, deleted, prev_version, merge_parent_uuid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
                commit=False,
                connection=conn,
            )
        return len(rows)

    def list_data_table_sources(
        self,
        table_id: int,
        *,
        include_deleted: bool = False,
        owner_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """List sources for a data table."""
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        conditions = ["table_id = ?"]
        params: list[Any] = [int(table_id)]
        if not include_deleted:
            conditions.append("deleted = 0")
        if owner_filter is not None:
            conditions.append("client_id = ?")
            params.append(owner_filter)
        sql = (
            "SELECT * FROM data_table_sources WHERE "  # nosec B608
            + " AND ".join(conditions)
            + " ORDER BY id ASC"
        )
        rows = self.execute_query(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def soft_delete_data_table_sources(
        self,
        table_id: int,
        owner_user_id: int | None = None,
    ) -> int:
        """Soft delete sources for a data table."""
        now = self._get_current_utc_timestamp_str()
        owner_filter = self._resolve_data_tables_owner(owner_user_id)
        params: list[Any] = [now, int(table_id)]
        where_clause = "WHERE table_id = ? AND deleted = 0"
        if owner_filter is not None:
            where_clause += " AND client_id = ?"
            params.append(owner_filter)
        cur = self.execute_query(
            """
            UPDATE data_table_sources
            SET deleted = 1,
                last_modified = ?,
                version = version + 1
            {where_clause}
            """.format_map(locals()),  # nosec B608
            tuple(params),
            commit=True,
        )
        return int(getattr(cur, "rowcount", 0) or 0)

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
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            # Re-raise as DatabaseError for consistent error semantics
            pass
            raise DatabaseError(f"Database initialization failed: {e}") from e  # noqa: TRY003
        return self

    def _generate_uuid(self) -> str:
        """
        Internal helper to generate a new UUID string.

        Returns:
            str: A unique UUID version 4 string.
        """
        return str(uuid.uuid4())

    def _get_next_version(self, conn: sqlite3.Connection, table: str, id_col: str, id_val: Any) -> tuple[int, int] | None:
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
            if not (_SAFE_IDENTIFIER_RE.fullmatch(table or "") and _SAFE_IDENTIFIER_RE.fullmatch(id_col or "")):
                raise DatabaseError(  # noqa: TRY003
                    f"Unsafe identifier in version lookup: table={table!r}, column={id_col!r}"
                )
            cursor = conn.execute(f"SELECT version FROM {table} WHERE {id_col} = ? AND deleted = 0", (id_val,))  # nosec B608
            result = cursor.fetchone()
            if result:
                current_version = result['version']
                if isinstance(current_version, int):
                    return current_version, current_version + 1
                else:
                    logging.error(f"Invalid non-integer version '{current_version}' found for {table} {id_col}={id_val}")
                    return None
        except sqlite3.Error as e:
            logging.exception(f"Database error fetching version for {table} {id_col}={id_val}")
            raise DatabaseError(f"Failed to fetch current version: {e}") from e  # noqa: TRY003
        return None

    # --- Internal Sync Logging Helper ---
    def _log_sync_event(self, conn: sqlite3.Connection, entity: str, entity_uuid: str, operation: str, version: int, payload: dict | None = None):
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
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
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
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logging.error(
                f"Failed to insert sync log event for {entity} {entity_uuid}: {e}", exc_info=True
            )
            raise DatabaseError(f"Failed to log sync event: {e}") from e  # noqa: TRY003

    # --- NEW: Internal FTS Helper Methods ---
    def _update_fts_media(self, conn: sqlite3.Connection, media_id: int, title: str, content: str | None):
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
                from tldw_Server_API.app.core.RAG.rag_service.synonyms_registry import (
                    get_corpus_synonyms,  # type: ignore
                )
                corpus = os.getenv("DEFAULT_FTS_CORPUS", "").strip() or None
                syn_map = get_corpus_synonyms(corpus)
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                syn_map = {}
            expanded_terms: list[str] = []
            if syn_map:
                try:
                    import re as _re
                    tokens = {t for t in _re.split(r"\W+", f"{title} {content}".lower()) if t}
                    for t in tokens:
                        al = syn_map.get(t)
                        if al:
                            expanded_terms.extend(a for a in al if a)
                    # Cap expansion to avoid index bloat
                    max_terms = int(os.getenv("FTS_SYNONYM_EXPANSION_LIMIT", "200") or 200)
                    if len(expanded_terms) > max_terms:
                        expanded_terms = expanded_terms[:max_terms]
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    expanded_terms = []
            exp_str = (" " + " ".join(expanded_terms)) if expanded_terms else ""
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO media_fts (rowid, title, content) VALUES (?, ?, ?)",
                    (media_id, title, f"{content}{exp_str}"),
                )
                logging.debug("Updated SQLite FTS entry for Media ID {}", media_id)
            except sqlite3.Error as e:
                logging.error("Failed to update media_fts for Media ID {}: {}", media_id, e, exc_info=True)
                raise DatabaseError(f"Failed to update FTS for Media ID {media_id}: {e}") from e  # noqa: TRY003
            return

        if self.backend_type == BackendType.POSTGRESQL:
            # Use fielded weights: title=A (highest), content=C (lower)
            try:
                from tldw_Server_API.app.core.testing import env_flag_enabled

                enable_syn = env_flag_enabled("PG_FTS_ENABLE_SYNONYMS")
                if enable_syn:
                    # Best-effort create synonyms support
                    try:
                        ensure_fn = getattr(self.backend, 'ensure_synonyms_support', None)
                        if callable(ensure_fn):
                            ensure_fn(connection=conn)
                    except _MEDIA_NONCRITICAL_EXCEPTIONS as _syn_err:
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
                logging.debug("Updated PostgreSQL FTS vector for Media ID {}", media_id)
            except DatabaseError as exc:
                logging.error("Failed to update PostgreSQL FTS for Media ID {}: {}", media_id, exc, exc_info=True)
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
                logging.debug("Deleted SQLite FTS entry for Media ID {}", media_id)
            except sqlite3.Error as e:
                logging.error("Failed to delete from media_fts for Media ID {}: {}", media_id, e, exc_info=True)
                raise DatabaseError(f"Failed to delete FTS for Media ID {media_id}: {e}") from e  # noqa: TRY003
            return

        if self.backend_type == BackendType.POSTGRESQL:
            try:
                self._execute_with_connection(
                    conn,
                    "UPDATE media SET media_fts_tsv = NULL WHERE id = ?",
                    (media_id,),
                )
                logging.debug("Cleared PostgreSQL FTS vector for Media ID {}", media_id)
            except DatabaseError as exc:
                logging.error("Failed to clear PostgreSQL FTS for Media ID {}: {}", media_id, exc, exc_info=True)
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
                logging.debug("Updated SQLite FTS entry for Keyword ID {}", keyword_id)
            except sqlite3.Error as e:
                logging.error("Failed to update keyword_fts for Keyword ID {}: {}", keyword_id, e, exc_info=True)
                raise DatabaseError(f"Failed to update FTS for Keyword ID {keyword_id}: {e}") from e  # noqa: TRY003
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
                logging.debug("Updated PostgreSQL FTS vector for Keyword ID {}", keyword_id)
            except DatabaseError as exc:
                logging.error("Failed to update PostgreSQL FTS for Keyword ID {}: {}", keyword_id, exc, exc_info=True)
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
                logging.debug("Deleted SQLite FTS entry for Keyword ID {}", keyword_id)
            except sqlite3.Error as e:
                logging.error("Failed to delete from keyword_fts for Keyword ID {}: {}", keyword_id, e, exc_info=True)
                raise DatabaseError(f"Failed to delete FTS for Keyword ID {keyword_id}: {e}") from e  # noqa: TRY003
            return

        if self.backend_type == BackendType.POSTGRESQL:
            try:
                self._execute_with_connection(
                    conn,
                    "UPDATE keywords SET keyword_fts_tsv = NULL WHERE id = ?",
                    (keyword_id,),
                )
                logging.debug("Cleared PostgreSQL FTS vector for Keyword ID {}", keyword_id)
            except DatabaseError as exc:
                logging.error("Failed to clear PostgreSQL FTS for Keyword ID {}: {}", keyword_id, exc, exc_info=True)
                raise
            return

    def sync_refresh_fts_for_entity(
        self,
        conn,
        *,
        entity: str,
        entity_uuid: str,
        operation: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Refresh FTS state for sync-applied Media/Keywords mutations inside a transaction."""
        payload = payload or {}

        if entity == "Media":
            row = self._fetchone_with_connection(
                conn,
                "SELECT id, title, content, deleted FROM Media WHERE uuid = ?",
                (entity_uuid,),
            )
            if not row:
                logging.warning(
                    "sync_refresh_fts_for_entity: Media row not found for uuid={} operation={}",
                    entity_uuid,
                    operation,
                )
                return

            media_id = int(row["id"])
            if operation == "delete" or bool(row.get("deleted", 0)):
                self._delete_fts_media(conn, media_id)
                return

            if operation in {"create", "update"}:
                if operation == "update" and not any(k in payload for k in ("title", "content", "deleted")):
                    return
                self._update_fts_media(
                    conn,
                    media_id,
                    str(row.get("title") or ""),
                    row.get("content"),
                )
            return

        if entity == "Keywords":
            row = self._fetchone_with_connection(
                conn,
                "SELECT id, keyword, deleted FROM Keywords WHERE uuid = ?",
                (entity_uuid,),
            )
            if not row:
                logging.warning(
                    "sync_refresh_fts_for_entity: Keyword row not found for uuid={} operation={}",
                    entity_uuid,
                    operation,
                )
                return

            keyword_id = int(row["id"])
            if operation == "delete" or bool(row.get("deleted", 0)):
                self._delete_fts_keyword(conn, keyword_id)
                return

            if operation in {"create", "update"}:
                if operation == "update" and not any(k in payload for k in ("keyword", "deleted")):
                    return
                self._update_fts_keyword(conn, keyword_id, str(row.get("keyword") or ""))
            return

        # In Media_DB_v2.py (within the Database class)

        # Add 'media_ids_filter' to the method signature
        # from typing import List, Tuple, Dict, Any, Optional, Union # Ensure Union is imported

    def search_media_db(
        self,
        search_query: str | None, # Main text for FTS/LIKE (can be pre-formatted for exact phrase)
        search_fields: list[str] | None = None,
        media_types: list[str] | None = None,
        date_range: dict[str, datetime] | None = None, # Expects datetime objects
        must_have_keywords: list[str] | None = None,
        must_not_have_keywords: list[str] | None = None,
        sort_by: str | None = "last_modified_desc", # Default sort order
        boost_fields: dict[str, float] | None = None,
        media_ids_filter: list[int | str] | None = None,
        page: int = 1,
        results_per_page: int = 20,
        include_trash: bool = False,
        include_deleted: bool = False
    ) -> tuple[list[dict[str, Any]], int]:
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
            boost_fields (Optional[Dict[str, float]]): Optional relevance weights for
                FTS fields. Supported keys are:
                - 'title': Weight for title matches.
                - 'content': Weight for content matches.
                Values are clamped to [0.05, 50.0]. When omitted, backend defaults apply.
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
            raise ValueError("Page number must be 1 or greater")  # noqa: TRY003
        if results_per_page < 1:
            raise ValueError("Results per page must be 1 or greater")  # noqa: TRY003

        if search_query and not search_fields:
            search_fields = ["title", "content"] # Default fields for search_query
        elif not search_fields: # Ensure search_fields is a list even if empty
            search_fields = []

        valid_text_search_fields = {"title", "content", "author", "type"}
        sanitized_text_search_fields = [f for f in search_fields if f in valid_text_search_fields]
        supplied_boost_fields = boost_fields if isinstance(boost_fields, dict) else None
        boost_fields_supplied = bool(supplied_boost_fields)

        def _sanitize_field_boost(field_name: str, default_value: float = 1.0) -> float:
            if not supplied_boost_fields:
                return default_value
            raw_value = supplied_boost_fields.get(field_name, default_value)
            try:
                parsed_value = float(raw_value)
            except (TypeError, ValueError):
                logging.debug(
                    "Invalid boost_fields value for '{}': {}. Using default {}.",
                    field_name,
                    raw_value,
                    default_value,
                )
                return default_value
            if not isfinite(parsed_value):
                logging.debug(
                    "Non-finite boost_fields value for '{}': {}. Using default {}.",
                    field_name,
                    raw_value,
                    default_value,
                )
                return default_value
            return max(0.05, min(50.0, parsed_value))

        title_boost = _sanitize_field_boost("title")
        content_boost = _sanitize_field_boost("content")

        # Optional hardening: clamp very long FTS inputs to avoid pathological queries
        if search_query:
            try:
                import os as _os
                max_chars = int((_os.getenv("FTS_QUERY_MAX_CHARS") or "1000").strip() or 1000)
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                max_chars = 1000
            if isinstance(search_query, str) and len(search_query) > max_chars:
                logging.warning(
                    "Clamping search_query from {} to {} chars for FTS hardening",
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
        fts_condition_index: int | None = None
        fts_param_index: int | None = None
        fts_relevance_added = False

        fts_select_params: list[Any] = []
        fts_condition_params: list[Any] = []
        postgres_tsquery: str | None = None

        def _is_sqlite_fts_query_error(err: Exception) -> bool:
            if self.backend_type != BackendType.SQLITE or fts_condition_index is None:
                return False
            msg = str(err).lower()
            return (
                "unable to use function match" in msg
                or "no such column" in msg
                or "no such table: media_fts" in msg
                or "fts5: syntax error" in msg
                or ("malformed" in msg and "match" in msg)
            )

        # Basic filters
        if not include_deleted:
            conditions.append("m.deleted = 0")
        if not include_trash:
            conditions.append("m.is_trash = 0")

        # Visibility filtering for SQLite (PostgreSQL uses RLS policies)
        if self.backend_type == BackendType.SQLITE:
            try:
                scope = get_scope()
            except _MEDIA_NONCRITICAL_EXCEPTIONS as scope_err:
                logging.debug(f"Failed to resolve scope for SQLite visibility filter; falling back to no scope: {scope_err}")
                scope = None

            if scope and not scope.is_admin:
                # Build visibility conditions for non-admin users
                visibility_parts = []

                # Personal: visibility is 'personal' and user is the owner
                user_id_str = str(scope.user_id) if scope.user_id is not None else ""
                if user_id_str:
                    visibility_parts.append(
                        "(COALESCE(m.visibility, 'personal') = 'personal' "
                        "AND (COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?))"
                    )
                    params.append(user_id_str)

                # Team: visibility is 'team' and user is a member of the team
                if scope.team_ids:
                    team_placeholders = ','.join('?' * len(scope.team_ids))
                    visibility_parts.append(
                        f"(m.visibility = 'team' AND m.team_id IN ({team_placeholders}))"
                    )
                    params.extend(scope.team_ids)

                # Org: visibility is 'org' and user is a member of the org
                if scope.org_ids:
                    org_placeholders = ','.join('?' * len(scope.org_ids))
                    visibility_parts.append(
                        f"(m.visibility = 'org' AND m.org_id IN ({org_placeholders}))"
                    )
                    params.extend(scope.org_ids)

                if visibility_parts:
                    conditions.append(f"({' OR '.join(visibility_parts)})")
                else:
                    # Fail closed for non-admin scopes with no visibility identifiers
                    # (no user_id, team_ids, or org_ids): return no rows.
                    conditions.append("(0 = 1)")

        # Media IDs Filter
        if media_ids_filter:
            if not all(isinstance(mid, (int, str)) for mid in media_ids_filter):
                raise ValueError("media_ids_filter must be a list of ints or strings.")  # noqa: TRY003
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
                raise ValueError("media_types must be a list of strings.")  # noqa: TRY003
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
                    raise ValueError("date_range['start_date'] must be a datetime object.")  # noqa: TRY003
                conditions.append("m.ingestion_date >= ?")
                params.append(start_date.isoformat())
            if end_date:
                if not isinstance(end_date, datetime):
                    raise ValueError("date_range['end_date'] must be a datetime object.")  # noqa: TRY003
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
            conditions.append(
                """
                (SELECT COUNT(DISTINCT k_mh.id)
                 FROM MediaKeywords mk_mh
                 JOIN Keywords k_mh ON mk_mh.keyword_id = k_mh.id
                 WHERE mk_mh.media_id = m.id AND k_mh.deleted = 0 AND LOWER(k_mh.keyword) IN ({kw_mh_placeholders})
                ) = ?
            """.format_map(locals())  # nosec B608
            )
            params.extend(cleaned_must_have)
            params.append(len(cleaned_must_have))

        # Must Not Have Keywords
        cleaned_must_not_have = [k.strip().lower() for k in must_not_have_keywords if k and k.strip()] if must_not_have_keywords else []
        if cleaned_must_not_have:
            kw_mnh_placeholders = ','.join('?' * len(cleaned_must_not_have))
            conditions.append(
                """
                NOT EXISTS (
                    SELECT 1
                    FROM MediaKeywords mk_mnh
                    JOIN Keywords k_mnh ON mk_mnh.keyword_id = k_mnh.id
                    WHERE mk_mnh.media_id = m.id AND k_mnh.deleted = 0 AND LOWER(k_mnh.keyword) IN ({kw_mnh_placeholders})
                )
            """.format_map(locals())  # nosec B608
            )
            params.extend(cleaned_must_not_have)

        # Text Search Logic (FTS or LIKE)
        fts_search_active = False
        if search_query:  # search_query is the actual text to match (e.g., "my query" or "\"exact phrase\"")
            like_conditions = []
            like_params = []

            like_search_query = search_query.strip('"') if search_query.startswith('"') and search_query.endswith('"') else search_query

            if any(f in sanitized_text_search_fields for f in ["title", "content"]):
                fts_search_active = True
                fts_query_parts: list[str] = []

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
                    logging.warning("FTS requested for unsupported backend {}", self.backend_type)
                    fts_search_active = False

                title_content_like_parts: list[str] = []
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
                like_parts: list[str] = []
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
                    if boost_fields_supplied:
                        base_select_parts.append(
                            f"bm25(media_fts, {title_boost:.6f}, {content_boost:.6f}) AS relevance_score"
                        )
                    else:
                        base_select_parts.append("bm25(media_fts) AS relevance_score")
                    fts_relevance_added = True
                order_by_clause_str = "ORDER BY relevance_score ASC, m.last_modified DESC, m.id DESC"
            elif self.backend_type == BackendType.POSTGRESQL and postgres_tsquery:
                if not any("relevance_score" in part for part in base_select_parts):
                    if boost_fields_supplied:
                        # PostgreSQL ts_rank weights are ordered as {D, C, B, A}.
                        postgres_weights_literal = (
                            f"{content_boost:.6f},1.000000,{content_boost:.6f},{title_boost:.6f}"
                        )
                        base_select_parts.append(
                            "ts_rank("
                            f"ARRAY[{postgres_weights_literal}]::float4[], "
                            "m.media_fts_tsv, to_tsquery('english', ?)"
                            ") AS relevance_score"
                        )
                    else:
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
            except (sqlite3.OperationalError, DatabaseError) as e:
                if _is_sqlite_fts_query_error(e):
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
                except (sqlite3.OperationalError, DatabaseError) as e:
                    # Handle specific FTS MATCH errors in results query
                    if _is_sqlite_fts_query_error(e):
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
                logging.exception(f"FTS table 'media_fts' missing in database '{self.db_path_str}'. Search will fail.")
                raise DatabaseError(f"FTS table 'media_fts' not found in {self.db_path_str}.") from e  # noqa: TRY003
            logging.error(f"Database error during media search in '{self.db_path_str}': {e}", exc_info=True)
            raise DatabaseError(f"Failed to search media in {self.db_path_str}: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logging.error(f"Unexpected error during media search in '{self.db_path_str}': {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred during media search: {e}") from e  # noqa: TRY003

    # --- Public Mutating Methods (Modified for Python Sync/FTS Logging) ---

    def search_by_safe_metadata(
        self,
        filters: list[dict[str, Any]] | None = None,
        match_all: bool = True,
        page: int = 1,
        per_page: int = 20,
        group_by_media: bool = True,
        text_query: str | None = None,
        media_types: list[str] | None = None,
        must_have_keywords: list[str] | None = None,
        must_not_have_keywords: list[str] | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        sort_by: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Search by fields inside DocumentVersions.safe_metadata and identifiers table.

        - filters: [{field, op, value}] where op in (eq, contains, icontains, startswith, endswith)
        - Known identifier fields (doi, pmid, pmcid, arxiv_id, s2_paper_id) are matched via DocumentVersionIdentifiers.
        - Other fields fallback to LIKE search against the JSON string in dv.safe_metadata.
        - When group_by_media, returns latest matching version per media.
        """
        try:
            offset = (max(1, page) - 1) * per_page
            clauses: list[str] = ["dv.deleted = 0", "m.deleted = 0"]
            params: list[Any] = []
            join_ident = False

            id_fields = {"doi","pmid","pmcid","arxiv_id","s2_paper_id"}
            ops_sql = {
                'eq': lambda col: (f"{col} = ?", lambda v: v),
                'contains': lambda col: (f"{col} LIKE ?", lambda v: f"%{v}%"),
                'icontains': lambda col: (f"LOWER({col}) LIKE ?", lambda v: f"%{str(v).lower()}%"),
                'startswith': lambda col: (f"{col} LIKE ?", lambda v: f"{v}%"),
                'endswith': lambda col: (f"{col} LIKE ?", lambda v: f"%{v}"),
            }

            filter_exprs: list[str] = []
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
                            if op == 'contains':
                                like_val = f"%{val}%"
                            elif op == 'startswith':
                                like_val = f"{val}%"
                            elif op == 'endswith':
                                like_val = f"%{val}"
                            else:
                                like_val = f"%{val}%"
                            params.append(like_val)

            if filter_exprs:
                join_op = " AND " if match_all else " OR "
                clauses.append("(" + join_op.join(filter_exprs) + ")")

            normalized_text_query = (text_query or "").strip()
            if normalized_text_query:
                clauses.append(
                    "(LOWER(COALESCE(m.title, '')) LIKE ? OR LOWER(COALESCE(dv.safe_metadata, '')) LIKE ?)"
                )
                text_query_like = f"%{normalized_text_query.lower()}%"
                params.extend([text_query_like, text_query_like])

            normalized_media_types = [
                str(media_type).strip().lower()
                for media_type in (media_types or [])
                if str(media_type).strip()
            ]
            if normalized_media_types:
                media_type_placeholders = ",".join("?" * len(normalized_media_types))
                clauses.append(f"LOWER(m.type) IN ({media_type_placeholders})")
                params.extend(normalized_media_types)

            cleaned_must_have = [
                str(keyword).strip().lower()
                for keyword in (must_have_keywords or [])
                if str(keyword).strip()
            ]
            if cleaned_must_have:
                kw_mh_placeholders = ",".join("?" * len(cleaned_must_have))
                clauses.append(
                    """
                (SELECT COUNT(DISTINCT k_mh.id)
                 FROM MediaKeywords mk_mh
                 JOIN Keywords k_mh ON mk_mh.keyword_id = k_mh.id
                 WHERE mk_mh.media_id = m.id AND k_mh.deleted = 0 AND LOWER(k_mh.keyword) IN ({kw_mh_placeholders})
                ) = ?
            """.format_map(locals())  # nosec B608
                )
                params.extend(cleaned_must_have)
                params.append(len(cleaned_must_have))

            cleaned_must_not_have = [
                str(keyword).strip().lower()
                for keyword in (must_not_have_keywords or [])
                if str(keyword).strip()
            ]
            if cleaned_must_not_have:
                kw_mnh_placeholders = ",".join("?" * len(cleaned_must_not_have))
                clauses.append(
                    """
                NOT EXISTS (
                    SELECT 1
                    FROM MediaKeywords mk_mnh
                    JOIN Keywords k_mnh ON mk_mnh.keyword_id = k_mnh.id
                    WHERE mk_mnh.media_id = m.id AND k_mnh.deleted = 0 AND LOWER(k_mnh.keyword) IN ({kw_mnh_placeholders})
                )
            """.format_map(locals())  # nosec B608
                )
                params.extend(cleaned_must_not_have)

            normalized_date_start = (date_start or "").strip()
            if normalized_date_start:
                clauses.append("dv.created_at >= ?")
                params.append(normalized_date_start)

            normalized_date_end = (date_end or "").strip()
            if normalized_date_end:
                clauses.append("dv.created_at <= ?")
                params.append(normalized_date_end)

            base_from = "FROM DocumentVersions dv JOIN Media m ON dv.media_id = m.id"
            if join_ident:
                base_from += " LEFT JOIN DocumentVersionIdentifiers dvi ON dvi.dv_id = dv.id"

            # Count
            if group_by_media:
                count_sql = (
                    f"SELECT COUNT(DISTINCT m.id) AS total_count {base_from} "
                    f"WHERE {' AND '.join(clauses)}"
                )
            else:
                count_sql = (
                    f"SELECT COUNT(*) AS total_count {base_from} "
                    f"WHERE {' AND '.join(clauses)}"
                )
            count_cursor = self.execute_query(count_sql, tuple(params))
            count_row = count_cursor.fetchone()
            total = count_row['total_count'] if count_row else 0

            if total == 0:
                return [], 0

            select_cols = "m.id AS media_id, m.title, m.type, dv.version_number, dv.created_at, dv.safe_metadata"
            normalized_sort_by = (sort_by or "").strip().lower()
            if normalized_sort_by == "date_desc":
                order_clause = "ORDER BY dv.created_at DESC, m.id DESC"
            elif normalized_sort_by == "date_asc":
                order_clause = "ORDER BY dv.created_at ASC, m.id ASC"
            elif normalized_sort_by == "title_asc":
                if self.backend_type == BackendType.POSTGRESQL:
                    order_clause = "ORDER BY LOWER(m.title) ASC, m.title ASC, m.id ASC"
                else:
                    order_clause = "ORDER BY m.title COLLATE NOCASE ASC, m.id ASC"
            elif normalized_sort_by == "title_desc":
                if self.backend_type == BackendType.POSTGRESQL:
                    order_clause = "ORDER BY LOWER(m.title) DESC, m.title DESC, m.id DESC"
                else:
                    order_clause = "ORDER BY m.title COLLATE NOCASE DESC, m.id DESC"
            else:
                order_clause = "ORDER BY m.last_modified DESC, m.id DESC"
            if group_by_media:
                results_sql = f"""
                    SELECT {select_cols}
                    {base_from}
                    WHERE {' AND '.join(clauses)}
                    GROUP BY m.id
                    {order_clause}
                    LIMIT ? OFFSET ?
                """
                res_params = tuple(params + [per_page, offset])
            else:
                results_sql = f"""
                    SELECT {select_cols}
                    {base_from}
                    WHERE {' AND '.join(clauses)}
                    {order_clause}
                    LIMIT ? OFFSET ?
                """
                res_params = tuple(params + [per_page, offset])

            cur = self.execute_query(results_sql, res_params)
            rows = [dict(r) for r in cur.fetchall()]
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logging.error(f"Metadata search failed: {e}", exc_info=True)
            raise DatabaseError(f"Failed metadata search: {e}") from e  # noqa: TRY003
        else:
            return rows, total
    def add_keyword(self, keyword: str, conn: Any | None = None) -> tuple[int | None, str | None]:
        return KeywordsRepository.from_legacy_db(self).add(keyword, conn=conn)

    def fetch_media_for_keywords(self, keywords: list[str], include_trash: bool = False) -> dict[
        str, list[dict[str, Any]]]:
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
            raise TypeError("Input 'keywords' must be a list of strings.")  # noqa: TRY003

        if not keywords:
            logger.debug("fetch_media_for_keywords called with an empty list of keywords.")
            return {}

        # Normalize keywords: lowercase, strip whitespace, filter out empty strings, and ensure uniqueness.
        # Sort for consistent query parameter order (good for logging/debugging, though IN order doesn't matter for SQL).
        potential_keywords = [k.strip().lower() for k in keywords if k and k.strip()]
        if not potential_keywords:
            logger.debug("fetch_media_for_keywords: no valid keywords after initial cleaning and stripping.")
            return {}

        unique_clean_keywords = sorted(set(potential_keywords))

        if not unique_clean_keywords:  # Should be redundant due to above check, but defensive.
            logger.debug("fetch_media_for_keywords: no unique valid keywords remain.")
            return {}

        placeholders = ','.join('?' * len(unique_clean_keywords))

        media_conditions = ["m.deleted = ?"]
        media_params: list[Any] = [False]
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
        query = """
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
        """.format_map(locals())  # nosec B608

        params = tuple(media_params + unique_clean_keywords + [False])

        logger.debug(
            f"Executing fetch_media_for_keywords query for keywords: {unique_clean_keywords}, include_trash: {include_trash}")

        # Initialize results dictionary. Keys will be the cleaned, unique input keywords.
        # If a keyword has no matching media, its list will remain empty.
        results_by_keyword: dict[str, list[dict[str, Any]]] = {kw: [] for kw in unique_clean_keywords}

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
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error fetching media for keywords from DB {self.db_path_str}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while fetching media for keywords: {e}") from e  # noqa: TRY003
        else:
            return results_by_keyword

    def get_sync_log_entries(self, since_change_id: int = 0, limit: int | None = None) -> list[dict]:
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
        except DatabaseError:
            raise
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.exception(f"Error fetching sync log entries from DB '{self.db_path_str}'")
            raise DatabaseError("Failed to fetch sync log entries") from e  # noqa: TRY003
        else:
            return results

    def delete_sync_log_entries(self, change_ids: list[int]) -> int:
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
            raise ValueError("change_ids must be a list of integers.")  # noqa: TRY003
        placeholders = ','.join('?' * len(change_ids))
        query = f"DELETE FROM sync_log WHERE change_id IN ({placeholders})"  # nosec B608
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
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.exception(f"Unexpected error deleting sync log entries from DB '{self.db_path_str}'")
            raise DatabaseError(f"Unexpected error deleting sync log entries: {e}") from e  # noqa: TRY003

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
            raise ValueError("change_id_threshold must be a non-negative integer.")  # noqa: TRY003
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
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.exception(
                f"Unexpected error deleting sync log entries before {change_id_threshold} from DB '{self.db_path_str}'"
            )
            raise DatabaseError(f"Unexpected error deleting sync log entries before threshold: {e}") from e  # noqa: TRY003

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
                    raise ConflictError(entity="Media", identifier=media_id)  # noqa: TRY301

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
                            f"DELETE FROM MediaKeywords WHERE media_id = ? AND keyword_id IN ({placeholders})",  # nosec B608
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
                            f"SELECT id, {uuid_col} AS uuid, version FROM {table} WHERE {fk_col} = ? AND deleted = 0",  # nosec B608
                            (media_id,),
                        )
                        if not children:
                            continue
                        # Pass current_time for last_modified in child update
                        update_sql = f"UPDATE {table} SET deleted = 1, last_modified = ?, version = ?, client_id = ? WHERE id = ? AND version = ? AND deleted = 0"  # nosec B608
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
                from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import (
                    invalidate_intra_doc_vectors,  # lazy import
                )
                invalidate_intra_doc_vectors(str(media_id))
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                pass
        except (ConflictError, DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error soft deleting media ID {media_id}: {e}", exc_info=True)
            if isinstance(e, (ConflictError, DatabaseError)):
                raise
            else:
                raise DatabaseError(f"Failed to soft delete media: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error soft deleting media ID {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error during soft delete: {e}") from e  # noqa: TRY003
        else:
            return True

    def share_media(
        self,
        media_id: int,
        visibility: str,
        *,
        org_id: int | None = None,
        team_id: int | None = None,
    ) -> bool:
        """
        Share media by changing its visibility scope.

        Args:
            media_id: ID of the media to share
            visibility: New visibility level ('personal', 'team', 'org')
            org_id: Organization ID (required for 'org' visibility)
            team_id: Team ID (required for 'team' visibility)

        Returns:
            True if the media was updated successfully

        Raises:
            InputError: If visibility is invalid or required scope IDs are missing
            DatabaseError: If the update fails
        """
        valid_visibilities = ('personal', 'team', 'org')
        if visibility not in valid_visibilities:
            raise InputError(f"Invalid visibility '{visibility}'. Must be one of: {valid_visibilities}")  # noqa: TRY003

        if visibility == 'team' and team_id is None:
            raise InputError("team_id is required for 'team' visibility")  # noqa: TRY003
        if visibility == 'org' and org_id is None:
            raise InputError("org_id is required for 'org' visibility")  # noqa: TRY003

        now = self._get_current_utc_timestamp_str()

        try:
            with self.transaction() as conn:
                # Get current media record
                row = self._fetchone_with_connection(
                    conn,
                    "SELECT id, uuid, version, visibility, org_id, team_id FROM Media WHERE id = ? AND deleted = 0",
                    (media_id,),
                )
                if not row:
                    raise InputError(f"Media ID {media_id} not found or deleted")  # noqa: TRY003, TRY301

                media_uuid = row['uuid']
                current_version = row['version']
                new_version = current_version + 1

                # Determine new org_id and team_id based on visibility
                new_org_id = org_id if visibility in ('team', 'org') else None
                new_team_id = team_id if visibility == 'team' else None

                # Update the record
                update_sql = """
                    UPDATE Media
                    SET visibility = ?, org_id = ?, team_id = ?, version = ?, last_modified = ?, client_id = ?
                    WHERE id = ? AND version = ?
                """
                cursor = self._execute_with_connection(
                    conn,
                    update_sql,
                    (visibility, new_org_id, new_team_id, new_version, now, self.client_id, media_id, current_version),
                )
                if cursor.rowcount == 0:
                    raise ConflictError(f"Concurrent modification detected for media ID {media_id}", entity="Media", identifier=media_id)  # noqa: TRY003, TRY301

                # Log sync event
                payload = {
                    "visibility": visibility,
                    "org_id": new_org_id,
                    "team_id": new_team_id,
                    "version": new_version,
                    "last_modified": now,
                }
                self._log_sync_event(conn, "Media", media_uuid, "update", new_version, payload)

                logger.info(f"Shared media ID {media_id} with visibility '{visibility}'")
                return True

        except (InputError, ConflictError, DatabaseError) as e:
            logger.error(f"Error sharing media ID {media_id}: {e}", exc_info=True)
            raise
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error sharing media ID {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to share media: {e}") from e  # noqa: TRY003

    def unshare_media(self, media_id: int) -> bool:
        """
        Revert media to personal visibility.

        This removes team/org sharing and makes the content private to the owner.

        Args:
            media_id: ID of the media to unshare

        Returns:
            True if the media was updated successfully
        """
        return self.share_media(media_id, visibility='personal')

    def get_media_visibility(self, media_id: int) -> dict[str, Any] | None:
        """
        Get the current visibility settings for a media item.

        Args:
            media_id: ID of the media to check

        Returns:
            Dict with visibility, org_id, team_id, owner_user_id or None if not found
        """
        cursor = self.execute_query(
            "SELECT visibility, org_id, team_id, owner_user_id, client_id "
            "FROM Media WHERE id = ? AND deleted = 0",
            (media_id,),
        )
        row = cursor.fetchone() if cursor else None
        if not row:
            return None

        return {
            "visibility": row.get("visibility", "personal"),
            "org_id": row.get("org_id"),
            "team_id": row.get("team_id"),
            "owner_user_id": row.get("owner_user_id"),
            "client_id": row.get("client_id"),
        }

    def add_media_with_keywords(
            self,
            *,
            url: str | None = None,
            title: str | None = None,
            media_type: str | None = None,
            content: str | None = None,
            keywords: list[str] | None = None,
            prompt: str | None = None,
            analysis_content: str | None = None,
            safe_metadata: str | None = None,
            source_hash: str | None = None,
            transcription_model: str | None = None,
            author: str | None = None,
            ingestion_date: str | None = None,
            overwrite: bool = False,
            chunk_options: dict | None = None,
            chunks: list[dict[str, Any]] | None = None,
            visibility: str | None = None,
            owner_user_id: int | None = None,
    ) -> tuple[int | None, str | None, str]:
        """Compatibility shim while media ingestion persistence moves into repositories."""
        return MediaRepository.from_legacy_db(self).add_media_with_keywords(
            url=url,
            title=title,
            media_type=media_type,
            content=content,
            keywords=keywords,
            prompt=prompt,
            analysis_content=analysis_content,
            safe_metadata=safe_metadata,
            source_hash=source_hash,
            transcription_model=transcription_model,
            author=author,
            ingestion_date=ingestion_date,
            overwrite=overwrite,
            chunk_options=chunk_options,
            chunks=chunks,
            visibility=visibility,
            owner_user_id=owner_user_id,
        )

    # ------------------------
    # DocumentStructureIndex
    # ------------------------

    def _write_structure_index_records(self, conn, media_id: int, records: list[dict[str, Any]]) -> int:
        """Internal: insert rows into DocumentStructureIndex for a media item.

        Expects records with keys: kind, level, title, start_char, end_char, order_index, path.
        Clears existing rows for the media_id first (soft clears by hard delete since index is derived).
        """
        try:
            # Remove previous index (derived data)
            self._execute_with_connection(
                conn,
                "DELETE FROM DocumentStructureIndex WHERE media_id = ?",
                (media_id,),
            )
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logging.warning(f"Failed to clear old structure index for media_id={media_id}: {e}")
        if not records:
            return 0
        now = self._get_current_utc_timestamp_str()
        client_id = self.client_id
        inserted = 0
        for rec in records:
            try:
                self._execute_with_connection(
                    conn,
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
            except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
                logging.warning(f"Skipping invalid structure record for media_id={media_id}: {e}")
        return inserted

    def write_document_structure_index(self, media_id: int, records: list[dict[str, Any]]) -> int:
        """Public: replace DocumentStructureIndex for a media item with provided records.

        Suitable for callers that pre-compute structure externally.
        """
        if not media_id:
            raise InputError("media_id required for structure index write")  # noqa: TRY003
        with self.transaction() as conn:
            return self._write_structure_index_records(conn, media_id, records)

    def delete_document_structure_for_media(self, media_id: int) -> int:
        """Delete structure index rows for a given media item. Returns deleted row count."""
        if not media_id:
            return 0
        with self.transaction() as conn:
            cur = self._execute_with_connection(
                conn,
                "DELETE FROM DocumentStructureIndex WHERE media_id = ?",
                (media_id,),
            )
            return int(getattr(cur, "rowcount", 0) or 0)

    # =========================================================================
    # Chunking Templates Methods (moved earlier to ensure availability)
    # =========================================================================

    def create_chunking_template(self,
                                name: str,
                                template_json: str,
                                description: str | None = None,
                                is_builtin: bool = False,
                                tags: list[str] | None = None,
                                user_id: str | None = None) -> dict[str, Any]:
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
            raise InputError(f"Invalid template JSON: {e}") from e  # noqa: TRY003

        current_time = self._get_current_utc_timestamp_str()

        with self.transaction() as conn:
            existing = self._fetchone_with_connection(
                conn,
                "SELECT 1 FROM ChunkingTemplates WHERE name = ? AND deleted = ? LIMIT 1",
                (name, False),
            )
            if existing:
                raise InputError(f"Template with name '{name}' already exists")  # noqa: TRY003

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
                raise DatabaseError("Failed to create chunking template.")  # noqa: TRY003

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
                             template_id: int | None = None,
                             name: str | None = None,
                             uuid: str | None = None,
                             include_deleted: bool = False) -> dict[str, Any] | None:
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
            raise InputError("Must provide template_id, name, or uuid")  # noqa: TRY003
        params: list[Any] = []
        conditions: list[str] = []

        if template_id is not None:
            conditions.append("id = ?")
            params.append(template_id)
        if name:
            conditions.append("name = ?")
            params.append(name)
        if uuid:
            conditions.append("uuid = ?")
            params.append(uuid)

        query = f"SELECT * FROM ChunkingTemplates WHERE ({' OR '.join(conditions)})"  # nosec B608
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
                               tags: list[str] | None = None,
                               user_id: str | None = None,
                               include_deleted: bool = False) -> list[dict[str, Any]]:
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

        conditions: list[str] = []
        params: list[Any] = []

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
                                template_id: int | None = None,
                                name: str | None = None,
                                uuid: str | None = None,
                                template_json: str | None = None,
                                description: str | None = None,
                                tags: list[str] | None = None) -> bool:
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
            raise InputError("Cannot modify built-in templates")  # noqa: TRY003

        # Validate new JSON if provided
        if template_json:
            try:
                json.loads(template_json)
            except json.JSONDecodeError as e:
                raise InputError(f"Invalid template JSON: {e}") from e  # noqa: TRY003

        updates: list[str] = []
        params: list[Any] = []

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

        updates_sql = ', '.join(updates)
        update_sql = """
            UPDATE ChunkingTemplates
            SET {updates_sql}
            WHERE id = ? AND deleted = ?
        """.format_map(locals())  # nosec B608

        with self.transaction() as conn:
            cursor = self._execute_with_connection(conn, update_sql, tuple(params))
            if cursor.rowcount == 0:
                return False

        logger.info(f"Updated chunking template ID {template['id']}")
        return True

    def delete_chunking_template(self,
                                template_id: int | None = None,
                                name: str | None = None,
                                uuid: str | None = None,
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
            raise InputError("Cannot delete built-in templates")  # noqa: TRY003

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

    def seed_builtin_templates(self, templates: list[dict[str, Any]]) -> int:
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
                except _MEDIA_NONCRITICAL_EXCEPTIONS:
                    logger.exception(f"Failed to seed template {template['name']}")
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

    def lookup_section_for_offset(self, media_id: int, char_offset: int) -> dict[str, Any] | None:
        """Return the most specific section covering char_offset for media_id."""
        if media_id is None or char_offset is None:
            return None
        bool_false = False if self.backend_type == BackendType.POSTGRESQL else 0
        query = (
            "SELECT id, title, level, start_char, end_char FROM DocumentStructureIndex "
            "WHERE media_id = ? AND deleted = ? AND kind IN ('section','header') "
            "AND start_char <= ? AND end_char > ? ORDER BY COALESCE(level, 0) DESC, start_char DESC LIMIT 1"
        )
        try:
            with self.transaction() as conn:
                cur = self._execute_with_connection(
                    conn,
                    query,
                    (media_id, bool_false, char_offset, char_offset),
                )
                row = cur.fetchone()
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            return None
        if not row:
            return None
        if isinstance(row, dict):
            return row
        return {"id": row["id"], "title": row["title"], "level": row["level"], "start_char": row["start_char"], "end_char": row["end_char"]}

    def lookup_section_by_heading(self, media_id: int, heading: str) -> tuple[int, int, str] | None:
        """Best-effort lookup of a section by case-insensitive title match."""
        if not media_id or not heading:
            return None
        try:
            bool_false = False if self.backend_type == BackendType.POSTGRESQL else 0
            pattern = f"%{heading.strip()}%"
            with self.transaction() as conn:
                cur = self._execute_with_connection(
                    conn,
                    "SELECT start_char, end_char, title FROM DocumentStructureIndex "
                    "WHERE media_id = ? AND deleted = ? AND kind IN ('section','header') AND LOWER(title) LIKE LOWER(?) "
                    "ORDER BY COALESCE(level,0) DESC, (end_char - start_char) DESC LIMIT 1",
                    (media_id, bool_false, pattern),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return (int(row["start_char"]), int(row["end_char"]), str(row["title"]))
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            return None


    def create_document_version(self, media_id: int, content: str, prompt: str | None = None, analysis_content: str | None = None, safe_metadata: str | None = None) -> dict[str, Any]:
        return DocumentVersionsRepository.from_legacy_db(self).create(
            media_id=media_id,
            content=content,
            prompt=prompt,
            analysis_content=analysis_content,
            safe_metadata=safe_metadata,
        )

    def update_keywords_for_media(
        self,
        media_id: int,
        keywords: list[str],
        conn: Any | None = None,
    ):
        return KeywordsRepository.from_legacy_db(self).replace_keywords(
            media_id=media_id,
            keywords=keywords,
            conn=conn,
        )

    def soft_delete_keyword(self, keyword: str) -> bool:
        return KeywordsRepository.from_legacy_db(self).soft_delete(keyword)

    def soft_delete_document_version(self, version_uuid: str) -> bool:
        return DocumentVersionsRepository.from_legacy_db(self).soft_delete(version_uuid)

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
                    raise ConflictError("Media", media_id)  # noqa: TRY301

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
                raise
            else:
                raise DatabaseError(f"Failed mark as trash: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error marking media {media_id} trash: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected mark trash error: {e}") from e  # noqa: TRY003

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
                    raise ConflictError("Media", media_id)  # noqa: TRY301

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
                raise
            else:
                raise DatabaseError(f"Failed restore trash: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error restoring media {media_id} trash: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected restore trash error: {e}") from e  # noqa: TRY003

    def apply_synced_document_content_update(
        self,
        *,
        media_id: int,
        content: str,
        prompt: str | None = None,
        analysis_content: str | None = None,
        safe_metadata: str | None = None,
    ) -> dict[str, Any]:
        """
        Apply an externally-sourced document content update atomically.

        This helper keeps file-sync reconciliation aligned with the main media
        update semantics by updating the active ``Media`` row, refreshing FTS,
        and creating a new ``DocumentVersion`` in one transaction.
        """
        if content is None:
            raise InputError("Content is required for synced document updates.")  # noqa: TRY003

        client_id = self.client_id
        current_time = self._get_current_utc_timestamp_str()

        try:
            with self.transaction() as conn:
                media_info = self._fetchone_with_connection(
                    conn,
                    "SELECT uuid, version, title FROM Media WHERE id = ? AND deleted = 0",
                    (media_id,),
                )
                if not media_info:
                    raise InputError(f"Media {media_id} not found or deleted.")  # noqa: TRY003, TRY301

                media_uuid = media_info["uuid"]
                current_media_version = media_info["version"]
                current_title = media_info["title"]
                new_media_version = current_media_version + 1
                new_content_hash = hashlib.sha256(content.encode()).hexdigest()

                update_cursor = self._execute_with_connection(
                    conn,
                    """
                    UPDATE Media
                    SET content = ?,
                        content_hash = ?,
                        last_modified = ?,
                        version = ?,
                        client_id = ?,
                        chunking_status = 'pending',
                        vector_processing = 0
                    WHERE id = ? AND version = ?
                    """,
                    (
                        content,
                        new_content_hash,
                        current_time,
                        new_media_version,
                        client_id,
                        media_id,
                        current_media_version,
                    ),
                )
                if getattr(update_cursor, "rowcount", 0) == 0:
                    raise ConflictError("Media", media_id)  # noqa: TRY301

                new_doc_version_info = self.create_document_version(
                    media_id=media_id,
                    content=content,
                    prompt=prompt,
                    analysis_content=analysis_content,
                    safe_metadata=safe_metadata,
                )

                updated_media_data = self._fetchone_with_connection(
                    conn,
                    "SELECT * FROM Media WHERE id = ?",
                    (media_id,),
                ) or {}
                updated_media_data["created_doc_ver_uuid"] = new_doc_version_info.get("uuid")
                updated_media_data["created_doc_ver_num"] = new_doc_version_info.get("version_number")
                self._log_sync_event(
                    conn,
                    "Media",
                    media_uuid,
                    "update",
                    new_media_version,
                    updated_media_data,
                )
                self._update_fts_media(conn, media_id, current_title, content)

            logger.info(
                "Applied synced content update for media {}. New doc version: {}, new media version: {}",
                media_id,
                new_doc_version_info.get("version_number"),
                new_media_version,
            )
            try:
                if _CollectionsDB is not None and client_id is not None:
                    _CollectionsDB.from_backend(user_id=str(client_id), backend=self.backend).mark_highlights_stale_if_content_changed(
                        media_id,
                        new_content_hash,
                    )
            except _MEDIA_NONCRITICAL_EXCEPTIONS as _anch_err:
                logger.debug("Highlight re-anchoring hook (sync update) failed: {}", _anch_err)
            try:
                from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import (
                    invalidate_intra_doc_vectors,  # lazy import
                )

                invalidate_intra_doc_vectors(str(media_id))
            except _MEDIA_NONCRITICAL_EXCEPTIONS as _rag_err:
                logger.debug("Intra-doc vector invalidation skipped for media {}: {}", media_id, _rag_err)
        except (InputError, ConflictError, DatabaseError, sqlite3.Error, TypeError) as e:
            logger.error(f"Synced content update error media {media_id}: {e}", exc_info=True)
            if isinstance(e, (InputError, ConflictError, DatabaseError, TypeError)):
                raise
            raise DatabaseError(f"Synced content update failed: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected synced content update error media {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected synced content update error: {e}") from e  # noqa: TRY003
        else:
            return {
                "media_id": media_id,
                "content_hash": new_content_hash,
                "new_media_version": new_media_version,
                "document_version_number": new_doc_version_info.get("version_number"),
                "document_version_uuid": new_doc_version_info.get("uuid"),
            }

    def rollback_to_version(self, media_id: int, target_version_number: int) -> dict[str, Any]:
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
            raise ValueError("Target version invalid.")  # noqa: TRY003
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
                    raise ConflictError("Media", media_id)  # noqa: TRY301

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
            except _MEDIA_NONCRITICAL_EXCEPTIONS as _anch_err:
                logging.debug(f"Highlight re-anchoring hook (rollback) failed: {_anch_err}")
            # Invalidate agentic intra-doc vectors after content rollback
            try:
                from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import (
                    invalidate_intra_doc_vectors,  # lazy import
                )
                invalidate_intra_doc_vectors(str(media_id))
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                pass
        except (InputError, ValueError, ConflictError, DatabaseError, sqlite3.Error, TypeError) as e:
            logger.error(f"Rollback error media {media_id}: {e}", exc_info=True)
            if isinstance(e, (InputError, ValueError, ConflictError, DatabaseError, TypeError)):
                raise
            else:
                raise DatabaseError(f"DB error during rollback: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected rollback error media {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected rollback error: {e}") from e  # noqa: TRY003
        else:
            return {
                'success': f'Rolled back to version {target_version_number}. State saved as new version {new_doc_version_number}.',
                'new_document_version_number': new_doc_version_number,
                'new_document_version_uuid': new_doc_version_uuid,
                'new_media_version': new_media_version,
            }

    def get_all_document_versions(
        self,  # Add self as the first parameter
        media_id: int,
        include_content: bool = False,
        include_deleted: bool = False,
        limit: int | None = None,
        offset: int | None = 0,
    ) -> list[dict[str, Any]]:
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
            raise TypeError("media_id must be an integer.")  # noqa: TRY003
        if not isinstance(include_content, bool):
            raise TypeError("include_content must be a boolean.")  # noqa: TRY003
        if not isinstance(include_deleted, bool):
            raise TypeError("include_deleted must be a boolean.")  # noqa: TRY003
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise ValueError("Limit must be a positive integer.")  # noqa: TRY003
        if offset is not None and (not isinstance(offset, int) or offset < 0):
            raise ValueError("Offset must be a non-negative integer.")  # noqa: TRY003

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

            final_query = """
                SELECT {select_clause}
                FROM DocumentVersions dv
                JOIN Media m ON dv.media_id = m.id
                WHERE {where_clause}
                ORDER BY dv.version_number DESC
                {limit_offset_clause}
            """.format_map(locals())  # nosec B608

            # --- Execution ---
            logging.debug(f"Executing get_all_document_versions query | Params: {params}")
            # Use self.execute_query
            cursor = self.execute_query(final_query, tuple(params))
            results_raw = cursor.fetchall()

            versions_list = [dict(row) for row in results_raw]

            logging.debug(f"Found {len(versions_list)} versions for media_id={media_id}")
        except sqlite3.Error as e:
            # Use self.db_path_str
            logging.error(f"SQLite error retrieving versions for media_id {media_id} from {self.db_path_str}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to retrieve document versions: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            # Use self.db_path_str
            pass
            logging.error(f"Unexpected error retrieving versions for media_id {media_id} from {self.db_path_str}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred: {e}") from e  # noqa: TRY003
        else:
            return versions_list

    def process_unvectorized_chunks(self, media_id: int, chunks: list[dict[str, Any]], batch_size: int = 100):
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
                raise InputError(f"Cannot add chunks: Parent Media {media_id} not found or deleted.")  # noqa: TRY003, TRY301
            with self.transaction() as conn:
                media_info = self._fetchone_with_connection(
                    conn,
                    "SELECT uuid FROM Media WHERE id = ? AND deleted = 0",
                    (media_id,),
                )
                if not media_info:
                    raise InputError(f"Cannot add chunks: Parent Media ID {media_id} UUID not found.")  # noqa: TRY003, TRY301
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
                raise
            else:
                raise DatabaseError(f"Failed process chunks: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected chunk processing error media {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected chunk error: {e}") from e  # noqa: TRY003

    def clear_unvectorized_chunks(self, media_id: int) -> int:
        """
        Delete all unvectorized chunks for the media item.

        Note: This is a hard delete with no sync-log events because these
        chunks are derived artifacts recreated during reprocessing.

        Args:
            media_id (int): The ID of the parent Media item.

        Returns:
            int: Number of rows deleted.

        Raises:
            InputError: If the media item is missing or deleted.
            DatabaseError: For database errors during deletion.
        """
        if not isinstance(media_id, int):
            raise InputError("media_id must be an integer.")  # noqa: TRY003
        try:
            with self.transaction() as conn:
                media_row = self._fetchone_with_connection(
                    conn,
                    "SELECT id FROM Media WHERE id = ? AND deleted = 0",
                    (media_id,),
                )
                if not media_row:
                    raise InputError(f"Cannot clear chunks: Parent Media {media_id} not found or deleted.")  # noqa: TRY003, TRY301
                cursor = self._execute_with_connection(
                    conn,
                    "DELETE FROM UnvectorizedMediaChunks WHERE media_id = ?",
                    (media_id,),
                )
                deleted = cursor.rowcount if cursor.rowcount is not None else 0
            logger.info(
                "Cleared {} unvectorized chunks for media {}.",
                deleted,
                media_id,
            )
        except InputError:
            raise
        except (DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error clearing unvectorized chunks for media {media_id}: {e}", exc_info=True)
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(f"Failed to clear unvectorized chunks: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error clearing unvectorized chunks for media {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error clearing unvectorized chunks: {e}") from e  # noqa: TRY003
        else:
            return deleted

    def update_media_reprocess_state(
        self,
        media_id: int,
        *,
        chunking_status: str | None,
        reset_vector_processing: bool,
    ) -> None:
        """
        Update media processing state with sync logging.

        Increments the media version, updates last_modified/client_id, and optionally
        sets chunking_status and resets vector_processing.

        Args:
            media_id (int): Media item ID.
            chunking_status (Optional[str]): New chunking status; None leaves unchanged.
            reset_vector_processing (bool): Whether to reset vector_processing to 0.

        Raises:
            InputError: If the media item is missing or inactive.
            ConflictError: If the media row was updated concurrently.
            DatabaseError: For database errors during the update.
        """
        try:
            with self.transaction() as conn:
                row = self._fetchone_with_connection(
                    conn,
                    "SELECT uuid, version FROM Media WHERE id = ? AND deleted = 0 AND is_trash = 0",
                    (media_id,),
                )
                if not row:
                    raise InputError(f"Media {media_id} not found or inactive.")  # noqa: TRY003, TRY301
                media_uuid = row["uuid"]
                current_version = row["version"]
                next_version = current_version + 1
                now = self._get_current_utc_timestamp_str()

                set_parts = ["last_modified = ?", "version = ?", "client_id = ?"]
                params: list[Any] = [now, next_version, self.client_id]
                payload: dict[str, Any] = {"last_modified": now}

                if chunking_status is not None:
                    set_parts.append("chunking_status = ?")
                    params.append(chunking_status)
                    payload["chunking_status"] = chunking_status

                if reset_vector_processing:
                    set_parts.append("vector_processing = ?")
                    params.append(0)
                    payload["vector_processing"] = 0

                update_sql = f"UPDATE Media SET {', '.join(set_parts)} WHERE id = ? AND version = ?"  # nosec B608
                update_params = (*params, media_id, current_version)
                cursor = self._execute_with_connection(conn, update_sql, update_params)
                if cursor.rowcount == 0:
                    raise ConflictError("Media", media_id)  # noqa: TRY301

                self._log_sync_event(conn, "Media", media_uuid, "update", next_version, payload)
        except (InputError, ConflictError):
            raise
        except (DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error updating reprocess state for media {media_id}: {e}", exc_info=True)
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(f"Failed updating reprocess state: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error updating reprocess state for media {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error updating reprocess state: {e}") from e  # noqa: TRY003

    def mark_embeddings_error(self, media_id: int, error_message: str) -> None:
        """
        Mark embeddings processing as failed for a media item.

        Args:
            media_id (int): Media item ID.
            error_message (str): Error description to store in chunking_status.

        Raises:
            InputError: If the media item is missing or inactive.
            ConflictError: If the media row was updated concurrently.
            DatabaseError: For database errors during the update.
        """
        try:
            with self.transaction() as conn:
                row = self._fetchone_with_connection(
                    conn,
                    "SELECT uuid, version FROM Media WHERE id = ? AND deleted = 0 AND is_trash = 0",
                    (media_id,),
                )
                if not row:
                    raise InputError(f"Media {media_id} not found or inactive.")  # noqa: TRY003, TRY301
                media_uuid = row["uuid"]
                current_version = row["version"]
                next_version = current_version + 1
                now = self._get_current_utc_timestamp_str()

                safe_message = str(error_message).replace("\r", " ").replace("\n", " ").strip()
                if not safe_message:
                    safe_message = "unknown error"
                max_error_len = 500
                if len(safe_message) > max_error_len:
                    safe_message = f"{safe_message[: max_error_len - 3]}..."
                error_status = f"embeddings_error: {safe_message}"
                set_parts = [
                    "last_modified = ?",
                    "version = ?",
                    "client_id = ?",
                    "vector_processing = ?",
                    "chunking_status = ?",
                ]
                params: list[Any] = [
                    now,
                    next_version,
                    self.client_id,
                    -1,
                    error_status,
                ]
                payload: dict[str, Any] = {
                    "last_modified": now,
                    "vector_processing": -1,
                    "chunking_status": error_status,
                }

                update_sql = f"UPDATE Media SET {', '.join(set_parts)} WHERE id = ? AND version = ?"  # nosec B608
                update_params = (*params, media_id, current_version)
                cursor = self._execute_with_connection(conn, update_sql, update_params)
                if cursor.rowcount == 0:
                    raise ConflictError("Media", media_id)  # noqa: TRY301

                self._log_sync_event(conn, "Media", media_uuid, "update", next_version, payload)
        except (InputError, ConflictError):
            raise
        except (DatabaseError, sqlite3.Error) as e:
            logger.error(f"Error marking embeddings error for media {media_id}: {e}", exc_info=True)
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(f"Failed marking embeddings error: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error marking embeddings error for media {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error marking embeddings error: {e}") from e  # noqa: TRY003

    # --- Read Methods (Ensure they filter by deleted=0) ---
    def fetch_all_keywords(self) -> list[str]:
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
            query = f"SELECT keyword FROM Keywords WHERE deleted = ? ORDER BY {order_expr}"  # nosec B608
            cursor = self.execute_query(query, (False,))
            return [row['keyword'] for row in cursor.fetchall()]
        except DatabaseError:
            logger.exception("Error fetching keywords")
            raise

    def get_paginated_media_list(self, page: int = 1, results_per_page: int = 10) -> tuple[
        list[dict[str, Any]], int, int, int]:
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
            raise ValueError("Page number must be 1 or greater.")  # noqa: TRY003
        if results_per_page < 1:
            raise ValueError("Results per page must be 1 or greater.")  # noqa: TRY003

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

            results_data: list[dict[str, Any]] = []
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
        except DatabaseError:
            raise
        except sqlite3.Error as e:
            logging.error(f"SQLite error during DB pagination: {e}", exc_info=True)
            raise DatabaseError(f"Failed DB pagination query: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logging.error(f"Unexpected error during DB pagination: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error during DB pagination: {e}") from e  # noqa: TRY003
        else:
            return results_data, total_pages, page, total_items

    def get_paginated_trash_list(self, page: int = 1, results_per_page: int = 10) -> tuple[
        list[dict[str, Any]], int, int, int]:
        """
        Fetches a paginated list of trashed media items (id, title, type, uuid).

        Filters for items where deleted = 0 and is_trash = 1.
        Returns data suitable for constructing MediaListItem objects.
        """
        if page < 1:
            raise ValueError("Page number must be 1 or greater.")  # noqa: TRY003
        if results_per_page < 1:
            raise ValueError("Results per page must be 1 or greater.")  # noqa: TRY003

        logging.debug(
            f"DB: Fetching paginated trash list: page={page}, rpp={results_per_page} from {self.db_path_str}"
        )
        offset = (page - 1) * results_per_page

        try:
            count_cursor = self.execute_query(
                "SELECT COUNT(*) AS total_items FROM Media WHERE deleted = 0 AND is_trash = 1"
            )
            count_row = count_cursor.fetchone()
            total_items = count_row["total_items"] if count_row else 0

            results_data: list[dict[str, Any]] = []
            if total_items > 0:
                items_cursor = self.execute_query(
                    """
                    SELECT id, title, type, uuid
                    FROM Media
                    WHERE deleted = 0
                      AND is_trash = 1
                    ORDER BY trash_date DESC, last_modified DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (results_per_page, offset),
                )
                results_data = [dict(row) for row in items_cursor.fetchall()]

            total_pages = ceil(total_items / results_per_page) if total_items > 0 else 0
            if page > total_pages and total_pages == 0:
                results_data = []
        except DatabaseError:
            raise
        except sqlite3.Error as e:
            logging.error(f"SQLite error during trash pagination: {e}", exc_info=True)
            raise DatabaseError(f"Failed trash pagination query: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logging.error(f"Unexpected error during trash pagination: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error during trash pagination: {e}") from e  # noqa: TRY003
        else:
            return results_data, total_pages, page, total_items

    def get_media_by_id(self, media_id: int, include_deleted=False, include_trash=False) -> dict | None:
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
            raise InputError("media_id must be an integer.")  # noqa: TRY003

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
            raise DatabaseError(f"Failed to fetch media by ID: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error fetching media by ID {media_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error fetching media by ID: {e}") from e  # noqa: TRY003

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
        except sqlite3.Error:
            logger.exception(f"Error checking unvectorized chunks for media {media_id}")
            return False

    def get_unvectorized_chunk_count(self, media_id: int) -> int | None:
        """Return active UnvectorizedMediaChunks count for a media item, or None on query failure."""
        try:
            media_id_int = int(media_id)
        except (TypeError, ValueError):
            logger.warning(f"Invalid media_id for chunk count lookup: {media_id}")
            return None

        try:
            cur = self.execute_query(
                "SELECT COUNT(*) AS chunk_count FROM UnvectorizedMediaChunks "
                "WHERE media_id = ? AND deleted = 0",
                (media_id_int,),
            )
            row = cur.fetchone()
            if not row:
                return 0

            if isinstance(row, dict):
                return int(row.get("chunk_count", 0) or 0)
            with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                return int(row["chunk_count"] or 0)
            with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                return int(row[0] or 0)
            return 0
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            logger.exception(f"Error fetching unvectorized chunk count for media {media_id_int}")
            return None

    def get_unvectorized_anchor_index_for_offset(self, media_id: int, approx_offset: int) -> int | None:
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
        except sqlite3.Error:
            logger.exception(f"Error locating anchor chunk for media {media_id} at offset {approx_offset}")
            return None
        else:
            return None

    def get_unvectorized_chunk_index_by_uuid(self, media_id: int, chunk_uuid: str) -> int | None:
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
        except sqlite3.Error:
            logger.exception(f"Error fetching chunk_index by UUID for media {media_id}")
            return None

    def get_unvectorized_chunk_by_index(self, media_id: int, chunk_index: int) -> dict[str, Any] | None:
        """Return a single unvectorized chunk row for a media_id/chunk_index."""
        try:
            cur = self.execute_query(
                """
                SELECT chunk_index, chunk_text, start_char, end_char, chunk_type
                FROM UnvectorizedMediaChunks
                WHERE media_id = ? AND chunk_index = ? AND deleted = 0
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(media_id), int(chunk_index)),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            logger.exception(f"Error fetching chunk_index {chunk_index} for media {media_id}")
            return None

    def get_unvectorized_chunks_in_range(self, media_id: int, start_index: int, end_index: int) -> list[dict[str, Any]]:
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
        except sqlite3.Error:
            logger.exception(
                f"Error fetching chunk range [{start_index},{end_index}] for media {media_id}"
            )
            return []


# ----------------------------------------------------------------------------
# Composite helper: Full media details (active-only)
# ----------------------------------------------------------------------------
# Add similar get_media_by_uuid, get_media_by_url, get_media_by_hash, get_media_by_title
# Ensure they include the include_deleted and include_trash filters correctly.
def get_media_by_uuid(self, media_uuid: str, include_deleted=False, include_trash=False) -> dict | None:
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
        raise InputError("media_uuid cannot be empty.")  # noqa: TRY003
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
        logger.exception(f"Error fetching media by UUID {media_uuid}")
        raise DatabaseError(f"Failed fetch media by UUID: {e}") from e  # noqa: TRY003

def get_media_by_url(self, url: str, include_deleted=False, include_trash=False) -> dict | None:
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
        raise InputError("url cannot be empty or None.")  # noqa: TRY003

    url_candidates = media_dedupe_url_candidates(url)
    if not url_candidates:
        raise InputError("url cannot be empty or None.")  # noqa: TRY003

    if len(url_candidates) == 1:
        query = "SELECT * FROM Media WHERE url = ?"
        params = [url_candidates[0]]
    else:
        placeholders = ", ".join(["?"] * len(url_candidates))
        query = f"SELECT * FROM Media WHERE url IN ({placeholders})"  # nosec B608
        params = list(url_candidates)

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
        raise DatabaseError(f"Failed to fetch media by URL: {e}") from e  # noqa: TRY003
    except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Unexpected error fetching media by URL '{url}': {e}", exc_info=True)
        raise DatabaseError(f"Unexpected error fetching media by URL: {e}") from e  # noqa: TRY003

def get_media_by_hash(self, content_hash: str, include_deleted=False, include_trash=False) -> dict | None:
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
        raise InputError("content_hash cannot be empty or None.")  # noqa: TRY003

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
        raise DatabaseError(f"Failed to fetch media by hash: {e}") from e  # noqa: TRY003
    except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Unexpected error fetching media by hash '{content_hash[:10]}...': {e}", exc_info=True)
        raise DatabaseError(f"Unexpected error fetching media by hash: {e}") from e  # noqa: TRY003

def get_media_by_title(self, title: str, include_deleted=False, include_trash=False) -> dict | None:
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
        raise InputError("title cannot be empty or None.")  # noqa: TRY003

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
        raise DatabaseError(f"Failed to fetch media by title: {e}") from e  # noqa: TRY003
    except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Unexpected error fetching media by title '{title}': {e}", exc_info=True)
        raise DatabaseError(f"Unexpected error fetching media by title: {e}") from e  # noqa: TRY003

def get_paginated_files(self, page: int = 1, results_per_page: int = 50) -> tuple[list[sqlite3.Row], int, int, int]:
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
        raise ValueError("Page number must be 1 or greater.")  # noqa: TRY003
    if results_per_page < 1:
        raise ValueError("Results per page must be 1 or greater.")  # noqa: TRY003

    # Use self.db_path_str for logging context
    logging.debug(
        f"Fetching paginated files: page={page}, results_per_page={results_per_page} from DB: {self.db_path_str} (Active Only)")

    offset = (page - 1) * results_per_page
    total_items = 0
    results: list[sqlite3.Row] = []  # Type hint for clarity

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
    except DatabaseError as e:
        logging.error(f"Database error in get_paginated_files for DB {self.db_path_str}: {e}", exc_info=True)
        # Re-raise the specific error for the caller to handle
        raise
    # Catch potential underlying SQLite errors if not wrapped by execute_query
    except sqlite3.Error as e:
        logging.error(f"SQLite error during pagination query in {self.db_path_str}: {e}", exc_info=True)
        raise DatabaseError(f"Failed pagination query: {e}") from e  # noqa: TRY003
    # Catch unexpected errors
    except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
        logging.error(f"Unexpected error in get_paginated_files for DB {self.db_path_str}: {e}", exc_info=True)
        # Wrap unexpected errors in DatabaseError
        raise DatabaseError(f"Unexpected error during pagination: {e}") from e  # noqa: TRY003
    else:
        return results, total_pages, page, total_items

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
            raise ValueError("Backup path cannot be the same as the source database path.")  # noqa: TRY003, TRY301

        src_conn = self.get_connection()

        backup_db_path = Path(backup_file_path)
        backup_db_path.parent.mkdir(parents=True, exist_ok=True)

        backup_conn = sqlite3.connect(backup_file_path)

        logger.debug(f"Source DB connection: {src_conn}")
        logger.debug(f"Backup DB connection: {backup_conn} to file {backup_file_path}")

        src_conn.backup(backup_conn, pages=0, progress=None)
        logger.info(f"Database backup successful from '{self.db_path_str}' to '{backup_file_path}'")
    except sqlite3.Error as e:
        logger.error(f"SQLite error during database backup: {e}", exc_info=True)
        return False
    except ValueError as ve:
        logger.error(f"ValueError during database backup: {ve}", exc_info=True)
        return False
    except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Unexpected error during database backup: {e}", exc_info=True)
        return False
    else:
        return True
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
            "Use DB_Backups.create_postgres_backup(backend, backup_dir) to invoke pg_dump. Target requested: {}",
            backup_file_path,
        )
        return False

    logging.warning(
        "Automatic backups are only supported for SQLite. Backend {} is not handled (target: {}).",
        self.backend_type,
        backup_file_path,
    )
    return False


MediaDatabase.backup_database = backup_database
MediaDatabase._backup_non_sqlite_database = _backup_non_sqlite_database


def get_distinct_media_types(self, include_deleted=False, include_trash=False) -> list[str]:
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

    query = f"SELECT DISTINCT type FROM Media WHERE {where_clause} ORDER BY type ASC"  # nosec B608
    try:
        cursor = self.execute_query(query)
        results = [row['type'] for row in cursor.fetchall() if row['type']]
        logger.info(f"Found {len(results)} distinct media types: {results}")
    except sqlite3.Error as e:
        logger.error(f"Error fetching distinct media types from DB {self.db_path_str}: {e}", exc_info=True)
        raise DatabaseError(f"Failed to fetch distinct media types: {e}") from e  # noqa: TRY003
    except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Unexpected error fetching distinct media types from DB {self.db_path_str}: {e}",
                     exc_info=True)
        raise DatabaseError(f"An unexpected error occurred while fetching distinct media types: {e}") from e  # noqa: TRY003
    else:
        return results

def add_media_chunk(self, media_id: int, chunk_text: str, start_index: int, end_index: int, chunk_id: str) -> dict | None:
    return ChunksRepository.from_legacy_db(self).add(
        media_id=media_id,
        chunk_text=chunk_text,
        start_index=start_index,
        end_index=end_index,
        chunk_id=chunk_id,
    )

def add_media_chunks_in_batches(self, media_id: int, chunks_to_add: list[dict[str, Any]],
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
                    logging.exception(
                        f"Media ID {media_id}: Skipping chunk due to missing key in input data: {chunk_item}"
                    )
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
            except InputError:  # e.g., if media_id is invalid, or chunk structure within adapted_batch is wrong
                logging.exception(f"Media ID {media_id}: Input error during an internal batch insertion")
                log_counter("add_media_chunks_in_batches_batch_error",
                            labels={"media_id": media_id, "error_type": "InputError"})
                raise  # Re-raise to halt the entire operation
            except DatabaseError:  # For other database-related errors from self.batch_insert_chunks
                logging.exception(f"Media ID {media_id}: Database error during an internal batch insertion")
                log_counter("add_media_chunks_in_batches_batch_error",
                            labels={"media_id": media_id, "error_type": "DatabaseError"})
                raise  # Re-raise
            except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
                # Catch any other unexpected errors from self.batch_insert_chunks
                pass
                logging.error(f"Media ID {media_id}: Unexpected error during an internal batch insertion: {e}",
                              exc_info=True)
                log_counter("add_media_chunks_in_batches_batch_error",
                            labels={"media_id": media_id, "error_type": type(e).__name__})
                raise  # Re-raise

        logging.info(
            f"Media ID {media_id}: Finished processing chunk list. Total chunks from input: {total_chunks_in_input}. Successfully processed and attempted for insertion: {successfully_processed_count}."
        )
        duration = time.time() - start_time
        log_histogram("add_media_chunks_in_batches_duration", duration, labels={"media_id": media_id})
        log_counter("add_media_chunks_in_batches_success_overall", labels={"media_id": media_id})
    except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
        # Catches errors from the outer loop logic or re-raised errors from the inner try-except block
        pass
        duration = time.time() - start_time
        # Log duration even if the overall process failed
        log_histogram("add_media_chunks_in_batches_duration", duration, labels={"media_id": media_id})
        log_counter("add_media_chunks_in_batches_error_overall",
                    labels={"media_id": media_id, "error_type": type(e).__name__})
        logging.error(f"Media ID {media_id}: Error processing the list of chunks: {e}", exc_info=True)
        raise  # Re-raise the caught exception to inform the caller
    else:
        return successfully_processed_count

def batch_insert_chunks(self, media_id: int, chunks: list[dict]) -> int:
    return ChunksRepository.from_legacy_db(self).batch_insert(media_id=media_id, chunks=chunks)

def process_chunks(self, media_id: int, chunks: list[dict[str, Any]], batch_size: int = 100):
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
        raise InputError(f"Parent Media ID {media_id} not found or is deleted.")  # noqa: TRY003

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
                logging.exception(f"Database integrity error inserting chunk batch for media_id {media_id}")
                log_counter("process_chunks_batch_error",
                            labels={"media_id": media_id, "error_type": "IntegrityError"})
                # Re-raise to stop processing further batches, as this indicates a critical issue.
                raise DatabaseError(  # noqa: TRY003
                    f"Integrity error during chunk batch insertion for media_id {media_id}: {e}") from e
            except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
                # Catch other errors from DB operation or sync logging
                pass
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

    except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
        # Catches errors from loop setup or re-raised errors from batch processing
        pass
        duration = time.time() - start_time
        # Log duration even if the overall process failed or exited early
        log_histogram("process_chunks_duration", duration, labels={"media_id": media_id})
        log_counter("process_chunks_error", labels={"media_id": media_id, "error_type": type(e).__name__})
        logging.error(f"Overall error processing chunks for media_id {media_id}: {e}", exc_info=True)

        # Re-raise the exception so the caller is aware of the failure.
        # Wrap in DatabaseError if it's not already one of our specific DB errors.
        if not isinstance(e, (DatabaseError, InputError)):  # Check if e is already a known custom error
            raise DatabaseError(  # noqa: TRY003
                f"An unexpected error occurred while processing chunks for media_id {media_id}: {e}") from e
        else:
            raise


MediaDatabase.add_media_chunks_in_batches = add_media_chunks_in_batches
MediaDatabase.batch_insert_chunks = batch_insert_chunks
MediaDatabase.process_chunks = process_chunks

# =========================================================================
# Standalone Functions (REQUIRE db_instance passed explicitly)
# =========================================================================
# These generally call instance methods now, which handle logging/FTS internally.


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
    except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
        logger.exception("create_incremental_backup failed")
        return f"Failed to create incremental backup: {e}"


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
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                pass
    except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
        logger.exception("rotate_backups failed")
        return f"Failed to rotate backups: {e}"
    else:
        return f"Removed {removed} old backups."


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
        logger.error(f"Integrity check FAILED for {db_path}: {result}")
    except sqlite3.Error as e:
        logger.error(f"Error during integrity check for {db_path}: {e}", exc_info=True)
        return False
    else:
        return False
    finally:
        if conn:
            try:
                conn.close()
            except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
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
    except (ValueError, TypeError):
        return False
    else:
        return True


# Runtime compatibility patch: ensure get_media_by_title exists on MediaDatabase
try:
    _ = MediaDatabase.get_media_by_title
except _MEDIA_NONCRITICAL_EXCEPTIONS:
    _ = None
if not _:
    def _get_media_by_title(self, title: str, include_deleted: bool = False, include_trash: bool = False) -> dict | None:
        """Fetch the most recently modified active media by exact title.

        Mirrors other getter helpers. Ordered by last_modified DESC to prefer latest.
        """
        if not title:
            raise InputError("title cannot be empty or None.")  # noqa: TRY003

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
            raise DatabaseError(f"Failed to fetch media by title: {e}") from e  # noqa: TRY003
        except _MEDIA_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Unexpected error fetching media by title '{title}': {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error fetching media by title: {e}") from e  # noqa: TRY003

    MediaDatabase.get_media_by_title = _get_media_by_title

#
# End of Media_DB_v2.py
#######################################################################################################################
