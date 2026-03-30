"""PostgreSQL data-tables migration body helpers."""

from __future__ import annotations

from typing import Any, Protocol


class PostgresDataTablesBody(Protocol):
    """Protocol for DB objects that can ensure PostgreSQL data-table state."""

    def _ensure_postgres_data_tables(self, conn: Any) -> None: ...


def run_postgres_migrate_to_v14(db: PostgresDataTablesBody, conn: Any) -> None:
    """Run the PostgreSQL v14 data-tables migration body."""

    db._ensure_postgres_data_tables(conn)


def run_postgres_migrate_to_v15(db: PostgresDataTablesBody, conn: Any) -> None:
    """Run the PostgreSQL v15 data-tables migration body."""

    db._ensure_postgres_data_tables(conn)


__all__ = [
    "PostgresDataTablesBody",
    "run_postgres_migrate_to_v14",
    "run_postgres_migrate_to_v15",
]
