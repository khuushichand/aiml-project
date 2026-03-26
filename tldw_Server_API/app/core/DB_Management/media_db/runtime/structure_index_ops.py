"""Package-owned DocumentStructureIndex write helpers."""

from __future__ import annotations

import logging
from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)

_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def _write_structure_index_records(
    self,
    conn,
    media_id: int,
    records: list[dict[str, Any]],
) -> int:
    """Clear and rewrite derived structure-index rows for a media item."""
    try:
        self._execute_with_connection(
            conn,
            "DELETE FROM DocumentStructureIndex WHERE media_id = ?",
            (media_id,),
        )
    except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
        logging.warning("Failed to clear old structure index for media_id=%s: %s", media_id, exc)
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
                    rec.get("parent_id"),
                    rec.get("kind") or "section",
                    rec.get("level"),
                    rec.get("title"),
                    rec.get("start_char"),
                    rec.get("end_char"),
                    rec.get("order_index"),
                    rec.get("path"),
                    now,
                    now,
                    1,
                    client_id,
                    0 if self.backend_type == BackendType.SQLITE else False,
                ),
            )
            inserted += 1
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            logging.warning("Skipping invalid structure record for media_id=%s: %s", media_id, exc)
    return inserted


def write_document_structure_index(
    self,
    media_id: int,
    records: list[dict[str, Any]],
) -> int:
    """Replace DocumentStructureIndex rows for the supplied media item."""
    if not media_id:
        raise InputError("media_id required for structure index write")  # noqa: TRY003
    with self.transaction() as conn:
        return self._write_structure_index_records(conn, media_id, records)


def delete_document_structure_for_media(self, media_id: int) -> int:
    """Delete all structure-index rows for the supplied media item."""
    if not media_id:
        return 0
    with self.transaction() as conn:
        cur = self._execute_with_connection(
            conn,
            "DELETE FROM DocumentStructureIndex WHERE media_id = ?",
            (media_id,),
        )
        return int(getattr(cur, "rowcount", 0) or 0)


__all__ = [
    "_write_structure_index_records",
    "write_document_structure_index",
    "delete_document_structure_for_media",
]
