"""PostgreSQL sequence-sync migration body helpers."""

from __future__ import annotations

from typing import Any, Protocol


class PostgresSequenceSyncBody(Protocol):
    """Protocol for DB objects that can run PostgreSQL sequence synchronization."""

    def _sync_postgres_sequences(self, conn: Any) -> None: ...


def run_postgres_migrate_to_v18(db: PostgresSequenceSyncBody, conn: Any) -> None:
    """Run the PostgreSQL v18 sequence-sync migration body."""

    db._sync_postgres_sequences(conn)


__all__ = [
    "PostgresSequenceSyncBody",
    "run_postgres_migrate_to_v18",
]
