"""FTS schema helpers."""

from __future__ import annotations

from typing import Any, Protocol


class _SQLiteFtsOwner(Protocol):
    def _ensure_fts_structures(self, conn: Any) -> None: ...


class _PostgresFtsOwner(Protocol):
    def _ensure_postgres_fts(self, conn: Any) -> None: ...


def ensure_sqlite_fts_structures(db: _SQLiteFtsOwner, conn: Any) -> None:
    """Ensure the SQLite FTS structures owned by the legacy Media DB object."""

    db._ensure_fts_structures(conn)


def ensure_postgres_fts(db: _PostgresFtsOwner, conn: Any) -> None:
    """Ensure the PostgreSQL FTS structures owned by the legacy Media DB object."""

    db._ensure_postgres_fts(conn)
