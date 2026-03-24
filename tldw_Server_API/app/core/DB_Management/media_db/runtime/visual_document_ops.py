"""Package-owned VisualDocuments helpers."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timezone
import json
from typing import Any
import uuid

from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError


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
        with suppress(Exception):
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
    except Exception as exc:
        raise DatabaseError(f"Failed to insert VisualDocument: {exc}") from exc  # noqa: TRY003
    return new_uuid


def list_visual_documents_for_media(
    self,
    media_id: int,
    *,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
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
    conn = self.get_connection()
    try:
        if hard_delete:
            self._execute_with_connection(
                conn,
                "DELETE FROM VisualDocuments WHERE media_id = :media_id",
                {"media_id": media_id},
            )
            with suppress(Exception):
                self._log_sync_event(
                    conn,
                    "VisualDocuments",
                    f"media:{media_id}",
                    "delete",
                    1,
                    json.dumps({"media_id": media_id, "mode": "hard"}),
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
            with suppress(Exception):
                self._log_sync_event(
                    conn,
                    "VisualDocuments",
                    v_uuid,
                    "delete",
                    new_version,
                    json.dumps({"media_id": media_id}),
                )
    except Exception as exc:
        raise DatabaseError(f"Failed to delete VisualDocuments for media_id={media_id}: {exc}") from exc  # noqa: TRY003
