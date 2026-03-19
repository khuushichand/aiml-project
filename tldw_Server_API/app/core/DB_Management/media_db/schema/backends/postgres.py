"""PostgreSQL schema bootstrap implementation for Media DB."""

from __future__ import annotations

from typing import Protocol


class _PostgresSchemaInitializable(Protocol):
    def _initialize_schema_postgres(self) -> None: ...


def initialize_postgres_schema(db: _PostgresSchemaInitializable) -> None:
    """Initialize or migrate the PostgreSQL schema using the legacy implementation."""

    db._initialize_schema_postgres()
