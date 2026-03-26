"""PostgreSQL collections migration body helpers."""

from __future__ import annotations

from typing import Any, Protocol


class PostgresCollectionsBody(Protocol):
    """Protocol for DB objects that can ensure PostgreSQL collections state."""

    def _ensure_postgres_collections_tables(self, conn: Any) -> None: ...


def run_postgres_migrate_to_v12(db: PostgresCollectionsBody, conn: Any) -> None:
    """Run the PostgreSQL v12 collections migration body."""

    db._ensure_postgres_collections_tables(conn)


def run_postgres_migrate_to_v13(db: PostgresCollectionsBody, conn: Any) -> None:
    """Run the PostgreSQL v13 collections migration body."""

    db._ensure_postgres_collections_tables(conn)


__all__ = [
    "PostgresCollectionsBody",
    "run_postgres_migrate_to_v12",
    "run_postgres_migrate_to_v13",
]
