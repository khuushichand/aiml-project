"""PostgreSQL MediaFiles migration body helpers."""

from __future__ import annotations

from typing import Any, Protocol

from loguru import logger

from tldw_Server_API.app.core.DB_Management.backends.base import (
    DatabaseError as BackendDatabaseError,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)


class _MediaFilesBackend(Protocol):
    """Backend protocol for MediaFiles migration execution."""

    def execute(
        self,
        query: str,
        params: tuple[object, ...] | None = None,
        *,
        connection: object,
    ) -> object: ...


class PostgresMediaFilesBody(Protocol):
    """Protocol for DB objects that can run the PostgreSQL v11 migration body."""

    _MEDIA_FILES_TABLE_SQL: str
    backend: _MediaFilesBackend

    def _convert_sqlite_sql_to_postgres_statements(self, sql: str) -> list[str]: ...


def run_postgres_migrate_to_v11(db: PostgresMediaFilesBody, conn: Any) -> None:
    """Run the PostgreSQL v11 MediaFiles migration body."""

    try:
        statements = db._convert_sqlite_sql_to_postgres_statements(
            db._MEDIA_FILES_TABLE_SQL
        )
        for stmt in statements:
            try:
                db.backend.execute(stmt, connection=conn)
            except BackendDatabaseError as exc:
                logger.warning(
                    "Could not apply MediaFiles migration statement on PostgreSQL: {}",
                    exc,
                )
    except MEDIA_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning("MediaFiles Postgres migration v11 failed: {}", exc)


__all__ = [
    "PostgresMediaFilesBody",
    "run_postgres_migrate_to_v11",
]
