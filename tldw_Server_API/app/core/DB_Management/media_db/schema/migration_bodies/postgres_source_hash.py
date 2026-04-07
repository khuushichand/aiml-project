"""PostgreSQL source-hash migration body helpers."""

from __future__ import annotations

from typing import Any, Protocol


class PostgresSourceHashBody(Protocol):
    """Protocol for DB objects that can ensure PostgreSQL source-hash state."""

    def _ensure_postgres_source_hash_column(self, conn: Any) -> None: ...


def run_postgres_migrate_to_v16(db: PostgresSourceHashBody, conn: Any) -> None:
    """Run the PostgreSQL v16 source-hash migration body."""

    db._ensure_postgres_source_hash_column(conn)


__all__ = [
    "PostgresSourceHashBody",
    "run_postgres_migrate_to_v16",
]
