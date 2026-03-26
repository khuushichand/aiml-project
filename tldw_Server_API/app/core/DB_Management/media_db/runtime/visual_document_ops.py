"""Package-owned VisualDocuments helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
import uuid

from loguru import logger

from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError


def _safe_log_visual_document_sync_event(
    self,
    conn: Any,
    *,
    media_id: int,
    entity_uuid: str,
    operation: str,
    version: int,
    payload: str,
) -> None:
    try:
        self._log_sync_event(
            conn,
            "VisualDocuments",
            entity_uuid,
            operation,
            version,
            payload,
        )
    except Exception as exc:
        logger.warning(
            "Failed to record VisualDocuments sync event for media_id={} operation={} entity_uuid={}: {}",
            media_id,
            operation,
            entity_uuid,
            exc,
        )


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
    """Insert a visual-document row and emit a best-effort sync-log entry."""
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
    placeholders = ", ".join([f":{key}" for key in data])
    columns = ", ".join(data.keys())
    sql = f"INSERT INTO VisualDocuments ({columns}) VALUES ({placeholders})"  # nosec B608
    try:
        self._execute_with_connection(conn, sql, data)
        _safe_log_visual_document_sync_event(
            self,
            conn,
            media_id=media_id,
            entity_uuid=new_uuid,
            operation="create",
            version=1,
            payload=json.dumps(
                {
                    "media_id": media_id,
                    "caption": caption or "",
                    "ocr_text": ocr_text or "",
                }
            ),
        )
    except Exception as exc:
        raise DatabaseError(f"Failed to insert VisualDocument: {exc}") from exc  # noqa: TRY003
    return new_uuid


def list_visual_documents_for_media(
    self,
    media_id: int,
    *,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    """Return visual-document rows for a media item ordered by document position."""
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
    except Exception as exc:
        raise DatabaseError(f"Failed to list VisualDocuments for media_id={media_id}: {exc}") from exc  # noqa: TRY003


def soft_delete_visual_documents_for_media(
    self,
    media_id: int,
    *,
    hard_delete: bool = False,
) -> None:
    """Delete or soft-delete visual-document rows for a media item."""
    conn = self.get_connection()
    try:
        if hard_delete:
            self._execute_with_connection(
                conn,
                "DELETE FROM VisualDocuments WHERE media_id = :media_id",
                {"media_id": media_id},
            )
            _safe_log_visual_document_sync_event(
                self,
                conn,
                media_id=media_id,
                entity_uuid=f"media:{media_id}",
                operation="delete",
                version=1,
                payload=json.dumps({"media_id": media_id, "mode": "hard"}),
            )
            return

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
            _safe_log_visual_document_sync_event(
                self,
                conn,
                media_id=media_id,
                entity_uuid=v_uuid,
                operation="delete",
                version=new_version,
                payload=json.dumps({"media_id": media_id}),
            )
    except Exception as exc:
        raise DatabaseError(f"Failed to delete VisualDocuments for media_id={media_id}: {exc}") from exc  # noqa: TRY003
