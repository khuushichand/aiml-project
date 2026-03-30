"""FTS schema feature wrappers."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db.schema.fts_structures import (
    ensure_fts_structures as _ensure_fts_structures,
    ensure_postgres_fts as _ensure_postgres_fts,
)


def ensure_sqlite_fts_structures(db: Any, conn: Any) -> None:
    """Ensure the SQLite FTS structures through the package helper."""

    _ensure_fts_structures(db, conn)


def ensure_postgres_fts(db: Any, conn: Any) -> None:
    """Ensure the PostgreSQL FTS structures through the package helper."""

    _ensure_postgres_fts(db, conn)
