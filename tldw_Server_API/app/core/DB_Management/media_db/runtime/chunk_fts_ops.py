"""Chunk-level FTS helper operations for the package-native Media DB runtime."""

from __future__ import annotations

from loguru import logger as logging
from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)

_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def ensure_chunk_fts(self: Any) -> None:
    """Ensure the chunk-level FTS virtual table exists for SQLite backends."""

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
            except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
                logging.debug(f"ensure_chunk_fts rebuild skipped or failed: {exc}")
    except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
        logging.debug(f"ensure_chunk_fts skipped or failed: {exc}")


def maybe_rebuild_chunk_fts_if_empty(self: Any) -> None:
    """Rebuild the chunk-level FTS table when it exists but has no rows."""

    try:
        if self.backend_type != BackendType.SQLITE:
            return
        try:
            cur = self.execute_query("SELECT count(*) AS c FROM unvectorized_chunks_fts")
            row = cur.fetchone()
            count_val = (row[0] if row and not isinstance(row, dict) else (row.get("c") if row else 0)) or 0
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            self.ensure_chunk_fts()
            cur = self.execute_query("SELECT count(*) AS c FROM unvectorized_chunks_fts")
            row = cur.fetchone()
            count_val = (row[0] if row and not isinstance(row, dict) else (row.get("c") if row else 0)) or 0

        if int(count_val) == 0:
            self.execute_query(
                "INSERT INTO unvectorized_chunks_fts(unvectorized_chunks_fts) VALUES('rebuild')",
                commit=True,
            )
    except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
        logging.debug(f"maybe_rebuild_chunk_fts_if_empty skipped or failed: {exc}")


__all__ = [
    "ensure_chunk_fts",
    "maybe_rebuild_chunk_fts_if_empty",
]
