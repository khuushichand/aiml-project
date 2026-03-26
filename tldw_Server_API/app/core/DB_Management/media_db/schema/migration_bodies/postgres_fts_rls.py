"""PostgreSQL FTS/RLS migration body helpers."""

from __future__ import annotations

from typing import Any, Protocol


class PostgresFTSRLSBody(Protocol):
    """Protocol for DB objects that can ensure PostgreSQL FTS and RLS state."""

    def _ensure_postgres_fts(self, conn: Any) -> None: ...
    def _ensure_postgres_rls(self, conn: Any) -> None: ...


def run_postgres_migrate_to_v19(db: PostgresFTSRLSBody, conn: Any) -> None:
    """Run the PostgreSQL v19 FTS/RLS migration body."""

    db._ensure_postgres_fts(conn)
    db._ensure_postgres_rls(conn)


__all__ = [
    "PostgresFTSRLSBody",
    "run_postgres_migrate_to_v19",
]
