"""Package-owned FTS schema helpers."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseError as BackendDatabaseError,
)
from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError

try:
    from loguru import logger
except ImportError:  # pragma: no cover - defensive fallback
    import logging

    logger = logging.getLogger("media_db_fts_structures")


def ensure_fts_structures(db: Any, conn: Any) -> None:
    """Ensure backend-specific FTS structures exist."""

    if db.backend_type == BackendType.SQLITE:
        ensure_sqlite_fts(db, conn)
    elif db.backend_type == BackendType.POSTGRESQL:
        ensure_postgres_fts(db, conn)
    else:
        raise NotImplementedError(
            f"FTS bootstrap not implemented for backend {db.backend_type}"
        )


def ensure_sqlite_fts(db: Any, conn: Any) -> None:
    """Ensure SQLite FTS tables and triggers exist and are queryable."""

    conn.executescript(db._FTS_TABLES_SQL)
    conn.executescript(db._CLAIMS_FTS_TRIGGERS_SQL)
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


def ensure_postgres_fts(db: Any, conn: Any) -> None:
    """Ensure PostgreSQL FTS tables exist for core content surfaces."""

    backend = db.backend
    backend.create_fts_table(
        table_name="media_fts",
        source_table="media",
        columns=["title", "content"],
        connection=conn,
    )
    backend.create_fts_table(
        table_name="keyword_fts",
        source_table="keywords",
        columns=["keyword"],
        connection=conn,
    )
    backend.create_fts_table(
        table_name="claims_fts",
        source_table="claims",
        columns=["claim_text"],
        connection=conn,
    )
    try:
        backend.create_fts_table(
            table_name="unvectorized_chunks_fts",
            source_table="unvectorizedmediachunks",
            columns=["chunk_text"],
            connection=conn,
        )
    except BackendDatabaseError as exc:
        logger.warning(f"Failed to ensure Postgres chunk-level FTS: {exc}")


__all__ = [
    "ensure_fts_structures",
    "ensure_postgres_fts",
    "ensure_sqlite_fts",
]
