"""PostgreSQL schema-version helper."""

from __future__ import annotations

from typing import Any, Protocol


class _SchemaVersionBackend(Protocol):
    """Backend protocol for PostgreSQL schema-version updates."""

    def execute(
        self,
        query: str,
        params: tuple[object, ...],
        *,
        connection: object,
    ) -> object: ...


class PostgresSchemaVersionDB(Protocol):
    """Protocol for DB objects exposing a PostgreSQL backend."""

    backend: _SchemaVersionBackend


def update_schema_version_postgres(
    db: PostgresSchemaVersionDB,
    conn: Any,
    version: int,
) -> None:
    """Update PostgreSQL schema_version to the supplied version."""

    db.backend.execute(
        "UPDATE schema_version SET version = %s",
        (version,),
        connection=conn,
    )


__all__ = [
    "PostgresSchemaVersionDB",
    "update_schema_version_postgres",
]
