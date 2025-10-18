"""
Collections_DB - Persistence for Content Collections feature slices.

Scope:
- Output Templates (CRUD + lookup for preview)
- Reading Highlights (CRUD + maintenance helpers)

Notes:
- Uses DatabaseBackendFactory to support SQLite (default) and future PG.
- Stores data in the per-user Media database by default to colocate content artifacts.
- All methods are idempotent and should avoid raising on existing schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from .backends.base import DatabaseBackend, DatabaseConfig, BackendType, DatabaseError
from .backends.factory import DatabaseBackendFactory
from .db_path_utils import DatabasePaths


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


@dataclass
class OutputTemplateRow:
    id: int
    user_id: str
    name: str
    type: str
    format: str
    body: str
    description: Optional[str]
    is_default: bool
    created_at: str
    updated_at: str
    metadata_json: Optional[str] = None


@dataclass
class HighlightRow:
    id: int
    user_id: str
    item_id: int
    quote: str
    start_offset: Optional[int]
    end_offset: Optional[int]
    color: Optional[str]
    note: Optional[str]
    created_at: str
    anchor_strategy: str
    content_hash_ref: Optional[str]
    context_before: Optional[str]
    context_after: Optional[str]
    state: str


class CollectionsDatabase:
    """Adapter for Collections tables stored in the per-user Media DB."""

    def __init__(self, user_id: int | str, backend: Optional[DatabaseBackend] = None):
        self.user_id = str(user_id)
        if backend is None:
            db_path = str(DatabasePaths.get_media_db_path(int(user_id)))
            cfg = DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=db_path)
            backend = DatabaseBackendFactory.create_backend(cfg)
        self.backend = backend
        self.ensure_schema()

    @classmethod
    def for_user(cls, user_id: int | str) -> "CollectionsDatabase":
        return cls(user_id=user_id)

    @classmethod
    def from_backend(cls, user_id: int | str, backend: DatabaseBackend) -> "CollectionsDatabase":
        """Construct using an existing backend (avoids path resolution and int casting)."""
        return cls(user_id=user_id, backend=backend)

    def ensure_schema(self) -> None:
        """Create tables if they do not already exist."""
        # SQLite-compatible DDL; also acceptable on Postgres for basic types
        ddl = """
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
            updated_at TEXT NOT NULL,
            metadata_json TEXT
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

        CREATE TABLE IF NOT EXISTS outputs (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            job_id INTEGER,
            run_id INTEGER,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            format TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            media_item_id INTEGER,
            chatbook_path TEXT,
            deleted INTEGER NOT NULL DEFAULT 0,
            deleted_at TEXT,
            retention_until TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_outputs_user ON outputs(user_id);
        CREATE INDEX IF NOT EXISTS idx_outputs_run ON outputs(run_id);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_outputs_user_title_format ON outputs(user_id, title, format) WHERE deleted = 0;
        """
        try:
            self.backend.create_tables(ddl)
        except Exception as e:
            logger.error(f"Collections schema init failed: {e}")
            raise
        # Backfill columns for existing tables
        try:
            # Attempt to add metadata_json if missing
            self.backend.execute("ALTER TABLE output_templates ADD COLUMN metadata_json TEXT", tuple())
        except Exception:
            pass
        # Outputs table backfills
        try:
            self.backend.execute("ALTER TABLE outputs ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0", tuple())
        except Exception:
            pass
        try:
            self.backend.execute("ALTER TABLE outputs ADD COLUMN deleted_at TEXT", tuple())
        except Exception:
            pass
        try:
            self.backend.execute("ALTER TABLE outputs ADD COLUMN retention_until TEXT", tuple())
        except Exception:
            pass
        try:
            self.backend.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_outputs_user_title_format ON outputs(user_id, title, format) WHERE deleted = 0", tuple())
        except Exception:
            pass

    # ------------------------
    # Output Templates API
    # ------------------------
    def list_output_templates(self, q: Optional[str], limit: int, offset: int) -> Tuple[List[OutputTemplateRow], int]:
        where = ["user_id = ?"]
        params: List[Any] = [self.user_id]
        if q:
            where.append("(name LIKE ? OR description LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])
        where_sql = " AND ".join(where)

        count_q = f"SELECT COUNT(*) AS cnt FROM output_templates WHERE {where_sql}"
        total = int(self.backend.execute(count_q, tuple(params)).scalar or 0)

        select_q = (
            f"SELECT id, user_id, name, type, format, body, description, is_default, created_at, updated_at, metadata_json "
            f"FROM output_templates WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        rows = self.backend.execute(select_q, tuple(params + [limit, offset])).rows
        mapped = [OutputTemplateRow(**{**r, "is_default": bool(r.get("is_default", 0))}) for r in rows]
        return mapped, total

    def create_output_template(self, name: str, type_: str, format_: str, body: str, description: Optional[str], is_default: bool, metadata_json: Optional[str] = None) -> OutputTemplateRow:
        now = _utcnow_iso()
        q = (
            "INSERT INTO output_templates (user_id, name, type, format, body, description, is_default, created_at, updated_at, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (self.user_id, name, type_, format_, body, description, 1 if is_default else 0, now, now, metadata_json)
        res = self.backend.execute(q, params)
        new_id = int(res.lastrowid or 0)
        return self.get_output_template(new_id)

    def get_output_template(self, template_id: int) -> OutputTemplateRow:
        q = (
            "SELECT id, user_id, name, type, format, body, description, is_default, created_at, updated_at, metadata_json "
            "FROM output_templates WHERE id = ? AND user_id = ?"
        )
        row = self.backend.execute(q, (template_id, self.user_id)).first
        if not row:
            raise KeyError("template_not_found")
        row["is_default"] = bool(row.get("is_default", 0))
        return OutputTemplateRow(**row)

    def update_output_template(self, template_id: int, patch: Dict[str, Any]) -> OutputTemplateRow:
        if not patch:
            return self.get_output_template(template_id)
        fields = []
        params: List[Any] = []
        for key in ("name", "type", "format", "body", "description", "is_default", "metadata_json"):
            if key in patch and patch[key] is not None:
                fields.append(f"{key} = ?")
                val = patch[key]
                if key == "is_default":
                    val = 1 if bool(val) else 0
                params.append(val)
        fields.append("updated_at = ?")
        params.append(_utcnow_iso())
        params.extend([template_id, self.user_id])
        q = f"UPDATE output_templates SET {', '.join(fields)} WHERE id = ? AND user_id = ?"
        res = self.backend.execute(q, tuple(params))
        if res.rowcount <= 0:
            raise KeyError("template_not_found")
        return self.get_output_template(template_id)

    def delete_output_template(self, template_id: int) -> bool:
        q = "DELETE FROM output_templates WHERE id = ? AND user_id = ?"
        res = self.backend.execute(q, (template_id, self.user_id))
        return res.rowcount > 0

    # ------------------------
    # Highlights API
    # ------------------------
    def create_highlight(
        self,
        item_id: int,
        quote: str,
        start_offset: Optional[int],
        end_offset: Optional[int],
        color: Optional[str],
        note: Optional[str],
        anchor_strategy: str = "fuzzy_quote",
        content_hash_ref: Optional[str] = None,
        context_before: Optional[str] = None,
        context_after: Optional[str] = None,
        state: str = "active",
    ) -> HighlightRow:
        now = _utcnow_iso()
        q = (
            "INSERT INTO reading_highlights (user_id, item_id, quote, start_offset, end_offset, color, note, created_at, "
            "anchor_strategy, content_hash_ref, context_before, context_after, state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            self.user_id,
            item_id,
            quote,
            start_offset,
            end_offset,
            color,
            note,
            now,
            anchor_strategy,
            content_hash_ref,
            context_before,
            context_after,
            state,
        )
        res = self.backend.execute(q, params)
        new_id = int(res.lastrowid or 0)
        return self.get_highlight(new_id)

    def list_highlights_by_item(self, item_id: int) -> List[HighlightRow]:
        q = (
            "SELECT id, user_id, item_id, quote, start_offset, end_offset, color, note, created_at, "
            "anchor_strategy, content_hash_ref, context_before, context_after, state "
            "FROM reading_highlights WHERE user_id = ? AND item_id = ? ORDER BY created_at ASC"
        )
        rows = self.backend.execute(q, (self.user_id, item_id)).rows
        return [HighlightRow(**row) for row in rows]

    def get_highlight(self, highlight_id: int) -> HighlightRow:
        q = (
            "SELECT id, user_id, item_id, quote, start_offset, end_offset, color, note, created_at, "
            "anchor_strategy, content_hash_ref, context_before, context_after, state "
            "FROM reading_highlights WHERE id = ? AND user_id = ?"
        )
        row = self.backend.execute(q, (highlight_id, self.user_id)).first
        if not row:
            raise KeyError("highlight_not_found")
        return HighlightRow(**row)

    def update_highlight(self, highlight_id: int, patch: Dict[str, Any]) -> HighlightRow:
        if not patch:
            return self.get_highlight(highlight_id)
        fields = []
        params: List[Any] = []
        for key in ("color", "note", "state"):
            if key in patch and patch[key] is not None:
                fields.append(f"{key} = ?")
                params.append(patch[key])
        if not fields:
            return self.get_highlight(highlight_id)
        params.extend([highlight_id, self.user_id])
        q = f"UPDATE reading_highlights SET {', '.join(fields)} WHERE id = ? AND user_id = ?"
        res = self.backend.execute(q, tuple(params))
        if res.rowcount <= 0:
            raise KeyError("highlight_not_found")
        return self.get_highlight(highlight_id)

    def delete_highlight(self, highlight_id: int) -> bool:
        q = "DELETE FROM reading_highlights WHERE id = ? AND user_id = ?"
        res = self.backend.execute(q, (highlight_id, self.user_id))
        return res.rowcount > 0

    # ------------------------
    # Maintenance hooks
    # ------------------------
    def mark_highlights_stale_if_content_changed(self, item_id: int, new_content_hash: Optional[str]) -> int:
        """Mark highlights as stale if their stored content_hash_ref doesn't match new hash.

        Returns number of rows updated. Intended to be called by item update pipeline.
        """
        if not new_content_hash:
            return 0
        q = (
            "UPDATE reading_highlights SET state = 'stale' WHERE user_id = ? AND item_id = ? "
            "AND content_hash_ref IS NOT NULL AND content_hash_ref <> ?"
        )
        res = self.backend.execute(q, (self.user_id, item_id, new_content_hash))
        return int(res.rowcount or 0)

    # ------------------------
    # Outputs artifacts API
    # ------------------------
    @dataclass
    class OutputArtifactRow:
        id: int
        user_id: str
        job_id: Optional[int]
        run_id: Optional[int]
        type: str
        title: str
        format: str
        storage_path: str
        metadata_json: Optional[str]
        created_at: str
        media_item_id: Optional[int]
        chatbook_path: Optional[str]

    def create_output_artifact(
        self,
        *,
        type_: str,
        title: str,
        format_: str,
        storage_path: str,
        metadata_json: Optional[str] = None,
        job_id: Optional[int] = None,
        run_id: Optional[int] = None,
        media_item_id: Optional[int] = None,
        chatbook_path: Optional[str] = None,
        retention_until: Optional[str] = None,
    ) -> "CollectionsDatabase.OutputArtifactRow":
        now = _utcnow_iso()
        q = (
            "INSERT INTO outputs (user_id, job_id, run_id, type, title, format, storage_path, metadata_json, created_at, media_item_id, chatbook_path, deleted, deleted_at, retention_until) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)"
        )
        params = (
            self.user_id,
            job_id,
            run_id,
            type_,
            title,
            format_,
            storage_path,
            metadata_json,
            now,
            media_item_id,
            chatbook_path,
            retention_until,
        )
        res = self.backend.execute(q, params)
        new_id = int(res.lastrowid or 0)
        return self.get_output_artifact(new_id)

    def get_output_artifact(self, output_id: int, include_deleted: bool = False) -> "CollectionsDatabase.OutputArtifactRow":
        cond = "id = ? AND user_id = ?" + ("" if include_deleted else " AND deleted = 0")
        q = (
            "SELECT id, user_id, job_id, run_id, type, title, format, storage_path, metadata_json, created_at, media_item_id, chatbook_path "
            f"FROM outputs WHERE {cond}"
        )
        row = self.backend.execute(q, (output_id, self.user_id)).first
        if not row:
            raise KeyError("output_not_found")
        return CollectionsDatabase.OutputArtifactRow(**row)

    def delete_output_artifact(self, output_id: int, *, hard: bool = False) -> bool:
        if hard:
            q = "DELETE FROM outputs WHERE id = ? AND user_id = ?"
            res = self.backend.execute(q, (output_id, self.user_id))
            return res.rowcount > 0
        q = "UPDATE outputs SET deleted = 1, deleted_at = ? WHERE id = ? AND user_id = ? AND deleted = 0"
        res = self.backend.execute(q, (_utcnow_iso(), output_id, self.user_id))
        return res.rowcount > 0

    def get_output_artifact_by_title(self, title: str, format_: Optional[str] = None, include_deleted: bool = False) -> "CollectionsDatabase.OutputArtifactRow":
        where = ["user_id = ?", "title = ?"]
        params: list[Any] = [self.user_id, title]
        if format_:
            where.append("format = ?")
            params.append(format_)
        if not include_deleted:
            where.append("deleted = 0")
        q = (
            "SELECT id, user_id, job_id, run_id, type, title, format, storage_path, metadata_json, created_at, media_item_id, chatbook_path "
            f"FROM outputs WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT 1"
        )
        row = self.backend.execute(q, tuple(params)).first
        if not row:
            raise KeyError("output_not_found")
        return CollectionsDatabase.OutputArtifactRow(**row)

    def list_output_artifacts(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        job_id: Optional[int] = None,
        run_id: Optional[int] = None,
        type_: Optional[str] = None,
        include_deleted: bool = False,
        only_deleted: bool = False,
    ) -> tuple[list["CollectionsDatabase.OutputArtifactRow"], int]:
        where = ["user_id = ?"]
        params: list[Any] = [self.user_id]
        if only_deleted:
            where.append("deleted = 1")
        elif not include_deleted:
            where.append("deleted = 0")
        if job_id is not None:
            where.append("job_id = ?")
            params.append(job_id)
        if run_id is not None:
            where.append("run_id = ?")
            params.append(run_id)
        if type_:
            where.append("type = ?")
            params.append(type_)
        where_sql = " AND ".join(where)

        cq = f"SELECT COUNT(*) AS cnt FROM outputs WHERE {where_sql}"
        total = int(self.backend.execute(cq, tuple(params)).scalar or 0)
        sq = (
            "SELECT id, user_id, job_id, run_id, type, title, format, storage_path, metadata_json, created_at, media_item_id, chatbook_path "
            f"FROM outputs WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        rows = self.backend.execute(sq, tuple(params + [limit, offset])).rows
        return [CollectionsDatabase.OutputArtifactRow(**row) for row in rows], total

    def rename_output_artifact(self, output_id: int, new_title: str, new_storage_path: Optional[str] = None) -> "CollectionsDatabase.OutputArtifactRow":
        fields = ["title = ?"]
        params: list[Any] = [new_title]
        if new_storage_path is not None:
            fields.append("storage_path = ?")
            params.append(new_storage_path)
        params.extend([output_id, self.user_id])
        q = f"UPDATE outputs SET {', '.join(fields)} WHERE id = ? AND user_id = ? AND deleted = 0"
        res = self.backend.execute(q, tuple(params))
        if res.rowcount <= 0:
            raise KeyError("output_not_found")
        return self.get_output_artifact(output_id)

    def purge_expired_outputs(self) -> int:
        """Hard delete expired/retained outputs. Returns number of rows removed."""
        now = _utcnow_iso()
        # Hard delete those with retention_until past
        r1 = self.backend.execute(
            "DELETE FROM outputs WHERE user_id = ? AND retention_until IS NOT NULL AND retention_until <= ?",
            (self.user_id, now),
        )
        # Soft-deleted older than 30 days
        try:
            r2 = self.backend.execute(
                "DELETE FROM outputs WHERE user_id = ? AND deleted = 1 AND deleted_at IS NOT NULL AND julianday(?) - julianday(deleted_at) >= 30",
                (self.user_id, now),
            )
            return int((r1.rowcount or 0) + (r2.rowcount or 0))
        except Exception:
            return int(r1.rowcount or 0)
