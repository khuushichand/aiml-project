"""SlidesDatabase: per-user SQLite storage for presentations."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar


class SlidesDatabaseError(Exception):
    """Base exception for SlidesDatabase."""


class SchemaError(SlidesDatabaseError):
    """Raised when schema migrations fail."""


class ConflictError(SlidesDatabaseError):
    """Raised when optimistic locking fails or duplicates exist."""

    def __init__(self, message: str, *, entity: str | None = None, identifier: str | None = None):
        super().__init__(message)
        self.entity = entity
        self.identifier = identifier


class InputError(ValueError):
    """Raised for invalid inputs."""


@dataclass
class PresentationRow:
    id: str
    title: str
    description: str | None
    theme: str
    marp_theme: str | None
    template_id: str | None
    settings: str | None
    slides: str
    slides_text: str
    source_type: str | None
    source_ref: str | None
    source_query: str | None
    custom_css: str | None
    created_at: str
    last_modified: str
    deleted: int
    client_id: str
    version: int


@dataclass
class PresentationVersionRow:
    presentation_id: str
    version: int
    payload_json: str
    created_at: str
    client_id: str


class SlidesDatabase:
    _SCHEMA_VERSION = 1
    _schema_init_paths: ClassVar[set[str]] = set()

    def __init__(self, db_path: str | Path, client_id: str) -> None:
        if not client_id:
            raise ValueError("client_id is required")
        self.client_id = str(client_id)
        if isinstance(db_path, Path):
            self.db_path = db_path.resolve()
            self._db_path_str = str(self.db_path)
        else:
            self._db_path_str = str(db_path)
            self.db_path = Path(self._db_path_str).resolve() if self._db_path_str != ":memory:" else Path(":memory:")
        self._local = threading.local()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        if self._db_path_str in self._schema_init_paths:
            return
        conn = self.get_connection()
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY NOT NULL
                );
                INSERT OR IGNORE INTO schema_version (version) VALUES (0);

                CREATE TABLE IF NOT EXISTS presentations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    theme TEXT DEFAULT 'black',
                    marp_theme TEXT,
                    template_id TEXT,
                    settings TEXT,
                    slides TEXT NOT NULL,
                    slides_text TEXT NOT NULL,
                    source_type TEXT,
                    source_ref TEXT,
                    source_query TEXT,
                    custom_css TEXT,
                    created_at DATETIME NOT NULL,
                    last_modified DATETIME NOT NULL,
                    deleted INTEGER DEFAULT 0,
                    client_id TEXT NOT NULL,
                    version INTEGER DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_presentations_deleted ON presentations(deleted);
                CREATE INDEX IF NOT EXISTS idx_presentations_created ON presentations(created_at);

                CREATE TABLE IF NOT EXISTS presentations_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    presentation_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    client_id TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_presentations_versions_unique
                    ON presentations_versions(presentation_id, version);
                CREATE INDEX IF NOT EXISTS idx_presentations_versions_pid
                    ON presentations_versions(presentation_id);
                CREATE INDEX IF NOT EXISTS idx_presentations_versions_created
                    ON presentations_versions(created_at);

                CREATE VIRTUAL TABLE IF NOT EXISTS presentations_fts USING fts5(
                    title,
                    slides_text,
                    content=presentations,
                    content_rowid=rowid
                );

                CREATE TRIGGER IF NOT EXISTS presentations_ai AFTER INSERT ON presentations BEGIN
                  INSERT INTO presentations_fts(rowid, title, slides_text)
                  VALUES (new.rowid, new.title, new.slides_text);
                END;

                CREATE TRIGGER IF NOT EXISTS presentations_ad AFTER DELETE ON presentations BEGIN
                  INSERT INTO presentations_fts(presentations_fts, rowid, title, slides_text)
                  VALUES ('delete', old.rowid, old.title, old.slides_text);
                END;

                CREATE TRIGGER IF NOT EXISTS presentations_au AFTER UPDATE ON presentations BEGIN
                  INSERT INTO presentations_fts(presentations_fts, rowid, title, slides_text)
                  VALUES ('delete', old.rowid, old.title, old.slides_text);
                  INSERT INTO presentations_fts(rowid, title, slides_text)
                  VALUES (new.rowid, new.title, new.slides_text);
                END;

                CREATE TABLE IF NOT EXISTS sync_log (
                    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity TEXT NOT NULL,
                    entity_uuid TEXT NOT NULL,
                    operation TEXT NOT NULL CHECK(operation IN ('create','update','delete','restore')),
                    timestamp DATETIME NOT NULL,
                    client_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_sync_log_ts ON sync_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_sync_log_entity_uuid ON sync_log(entity_uuid);
                CREATE INDEX IF NOT EXISTS idx_sync_log_client_id ON sync_log(client_id);
                """
            )
            self._ensure_marp_theme_column(conn)
            self._ensure_template_id_column(conn)
            conn.commit()
            self._schema_init_paths.add(self._db_path_str)
        except sqlite3.Error as exc:
            conn.rollback()
            raise SchemaError(f"Failed to initialize Slides DB schema: {exc}") from exc

    def get_connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path_str, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.connection = conn
        return conn

    def close_connection(self) -> None:
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            conn.close()
            self._local.connection = None

    @contextmanager
    def transaction(self) -> Iterable[sqlite3.Connection]:
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _insert_sync_log(
        self,
        *,
        entity_uuid: str,
        operation: str,
        version: int,
        payload: dict[str, Any] | None = None,
    ) -> None:
        payload_json = json.dumps(payload) if payload is not None else None
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO sync_log (entity, entity_uuid, operation, timestamp, client_id, version, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "presentations",
                    entity_uuid,
                    operation,
                    self._utcnow_iso(),
                    self.client_id,
                    version,
                    payload_json,
                ),
            )

    @staticmethod
    def _ensure_marp_theme_column(conn: sqlite3.Connection) -> None:
        columns = conn.execute("PRAGMA table_info(presentations)").fetchall()
        if any(col["name"] == "marp_theme" for col in columns):
            return
        conn.execute("ALTER TABLE presentations ADD COLUMN marp_theme TEXT")

    @staticmethod
    def _ensure_template_id_column(conn: sqlite3.Connection) -> None:
        columns = conn.execute("PRAGMA table_info(presentations)").fetchall()
        if any(col["name"] == "template_id" for col in columns):
            return
        conn.execute("ALTER TABLE presentations ADD COLUMN template_id TEXT")

    @staticmethod
    def _fetch_presentation_by_id(
        conn: sqlite3.Connection, presentation_id: str, include_deleted: bool
    ) -> PresentationRow:
        query = "SELECT * FROM presentations WHERE id = ?"
        params: list[Any] = [presentation_id]
        if not include_deleted:
            query += " AND deleted = 0"
        row = conn.execute(query, tuple(params)).fetchone()
        if not row:
            raise KeyError("presentation_not_found")
        return PresentationRow(**dict(row))

    @staticmethod
    def _build_version_payload(row: PresentationRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "title": row.title,
            "description": row.description,
            "theme": row.theme,
            "marp_theme": row.marp_theme,
            "template_id": row.template_id,
            "settings": row.settings,
            "slides": row.slides,
            "custom_css": row.custom_css,
            "source_type": row.source_type,
            "source_ref": row.source_ref,
            "source_query": row.source_query,
            "created_at": row.created_at,
            "last_modified": row.last_modified,
            "deleted": int(row.deleted or 0),
            "client_id": row.client_id,
            "version": int(row.version),
        }

    def _insert_version_snapshot(self, conn: sqlite3.Connection, row: PresentationRow) -> None:
        payload_json = json.dumps(self._build_version_payload(row), ensure_ascii=True)
        conn.execute(
            """
            INSERT INTO presentations_versions (
                presentation_id, version, payload_json, created_at, client_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                row.id,
                int(row.version),
                payload_json,
                row.last_modified,
                row.client_id,
            ),
        )

    def create_presentation(
        self,
        *,
        presentation_id: str | None,
        title: str,
        description: str | None,
        theme: str,
        marp_theme: str | None,
        settings: str | None,
        template_id: str | None = None,
        slides: str,
        slides_text: str,
        source_type: str | None,
        source_ref: str | None,
        source_query: str | None,
        custom_css: str | None,
    ) -> PresentationRow:
        if not title:
            raise InputError("title is required")
        pres_id = presentation_id or str(uuid.uuid4())
        now = self._utcnow_iso()
        try:
            with self.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO presentations (
                        id, title, description, theme, marp_theme, template_id, settings, slides, slides_text,
                        source_type, source_ref, source_query, custom_css,
                        created_at, last_modified, deleted, client_id, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1)
                    """,
                    (
                        pres_id,
                        title,
                        description,
                        theme,
                        marp_theme,
                        template_id,
                        settings,
                        slides,
                        slides_text,
                        source_type,
                        source_ref,
                        source_query,
                        custom_css,
                        now,
                        now,
                        self.client_id,
                    ),
                )
                row = self._fetch_presentation_by_id(conn, pres_id, include_deleted=True)
                self._insert_version_snapshot(conn, row)
            self._insert_sync_log(
                entity_uuid=pres_id,
                operation="create",
                version=1,
                payload={"title": title, "theme": theme},
            )
            return row
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() or "PRIMARY" in str(exc).upper():
                raise ConflictError("presentation already exists", entity="presentations", identifier=pres_id) from exc
            raise SlidesDatabaseError(f"Failed to create presentation: {exc}") from exc

    def get_presentation_by_id(self, presentation_id: str, *, include_deleted: bool = False) -> PresentationRow:
        conn = self.get_connection()
        return self._fetch_presentation_by_id(conn, presentation_id, include_deleted)

    def list_presentations(
        self,
        *,
        limit: int,
        offset: int,
        include_deleted: bool,
        sort_column: str,
        sort_direction: str,
    ) -> tuple[list[PresentationRow], int]:
        if limit < 1:
            raise InputError("limit must be >= 1")
        allowed_columns = {
            "created_at": "created_at",
            "last_modified": "last_modified",
            "title": "title",
        }
        safe_column = allowed_columns.get(sort_column, "created_at")
        safe_direction = "DESC" if sort_direction.upper() == "DESC" else "ASC"
        where = "" if include_deleted else "WHERE deleted = 0"
        query = (
            f"SELECT * FROM presentations {where} ORDER BY {safe_column} {safe_direction} LIMIT ? OFFSET ?"
        )
        count_query = f"SELECT COUNT(*) AS cnt FROM presentations {where}"
        conn = self.get_connection()
        rows = conn.execute(query, (limit, offset)).fetchall()
        count_row = conn.execute(count_query).fetchone()
        total = int(count_row["cnt"]) if count_row else 0
        return [PresentationRow(**dict(row)) for row in rows], total

    def search_presentations(
        self,
        *,
        query: str,
        limit: int,
        offset: int,
        include_deleted: bool,
    ) -> tuple[list[PresentationRow], int]:
        if not query:
            raise InputError("query is required")
        if limit < 1:
            raise InputError("limit must be >= 1")
        where = "" if include_deleted else "AND p.deleted = 0"
        sql = (
            "SELECT p.* FROM presentations p "
            "JOIN presentations_fts fts ON p.rowid = fts.rowid "
            "WHERE presentations_fts MATCH ? "
            f"{where} "
            "ORDER BY p.last_modified DESC LIMIT ? OFFSET ?"
        )
        count_sql = (
            "SELECT COUNT(*) AS cnt FROM presentations p "
            "JOIN presentations_fts fts ON p.rowid = fts.rowid "
            "WHERE presentations_fts MATCH ? "
            f"{where}"
        )
        conn = self.get_connection()
        rows = conn.execute(sql, (query, limit, offset)).fetchall()
        count_row = conn.execute(count_sql, (query,)).fetchone()
        total = int(count_row["cnt"]) if count_row else 0
        return [PresentationRow(**dict(row)) for row in rows], total

    def update_presentation(
        self,
        *,
        presentation_id: str,
        update_fields: dict[str, Any],
        expected_version: int,
        operation: str = "update",
    ) -> PresentationRow:
        if not update_fields:
            raise InputError("update_fields is required")
        allowed = {
            "title",
            "description",
            "theme",
            "marp_theme",
            "template_id",
            "settings",
            "slides",
            "slides_text",
            "source_type",
            "source_ref",
            "source_query",
            "custom_css",
            "deleted",
        }
        sets: list[str] = []
        params: list[Any] = []
        for key, value in update_fields.items():
            if key not in allowed:
                continue
            sets.append(f"{key} = ?")
            params.append(value)
        if not sets:
            raise InputError("no valid fields to update")
        next_version = expected_version + 1
        sets.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        params.extend([self._utcnow_iso(), next_version, self.client_id, presentation_id, expected_version])
        # Column names come from the allowlist above; values are always bound params.
        sql = f"UPDATE presentations SET {', '.join(sets)} WHERE id = ? AND version = ?"
        with self.transaction() as conn:
            cur = conn.execute(sql, tuple(params))
            if cur.rowcount == 0:
                existing = conn.execute("SELECT version FROM presentations WHERE id = ?", (presentation_id,)).fetchone()
                if not existing:
                    raise KeyError("presentation_not_found")
                raise ConflictError("version_conflict", entity="presentations", identifier=presentation_id)
            row = self._fetch_presentation_by_id(conn, presentation_id, include_deleted=True)
            self._insert_version_snapshot(conn, row)
        self._insert_sync_log(
            entity_uuid=presentation_id,
            operation=operation,
            version=next_version,
            payload={"fields": list(update_fields.keys())},
        )
        return row

    def list_presentation_versions(
        self,
        *,
        presentation_id: str,
        limit: int,
        offset: int,
    ) -> tuple[list[PresentationVersionRow], int]:
        if limit < 1:
            raise InputError("limit must be >= 1")
        conn = self.get_connection()
        rows = conn.execute(
            """
            SELECT presentation_id, version, payload_json, created_at, client_id
            FROM presentations_versions
            WHERE presentation_id = ?
            ORDER BY version DESC
            LIMIT ? OFFSET ?
            """,
            (presentation_id, limit, offset),
        ).fetchall()
        count_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM presentations_versions WHERE presentation_id = ?",
            (presentation_id,),
        ).fetchone()
        total = int(count_row["cnt"]) if count_row else 0
        return [PresentationVersionRow(**dict(row)) for row in rows], total

    def get_presentation_version(
        self,
        *,
        presentation_id: str,
        version: int,
    ) -> PresentationVersionRow:
        conn = self.get_connection()
        row = conn.execute(
            """
            SELECT presentation_id, version, payload_json, created_at, client_id
            FROM presentations_versions
            WHERE presentation_id = ? AND version = ?
            """,
            (presentation_id, version),
        ).fetchone()
        if not row:
            raise KeyError("presentation_version_not_found")
        return PresentationVersionRow(**dict(row))

    def soft_delete_presentation(self, presentation_id: str, expected_version: int) -> PresentationRow:
        return self.update_presentation(
            presentation_id=presentation_id,
            update_fields={"deleted": 1},
            expected_version=expected_version,
            operation="delete",
        )

    def restore_presentation(self, presentation_id: str, expected_version: int) -> PresentationRow:
        return self.update_presentation(
            presentation_id=presentation_id,
            update_fields={"deleted": 0},
            expected_version=expected_version,
            operation="restore",
        )
