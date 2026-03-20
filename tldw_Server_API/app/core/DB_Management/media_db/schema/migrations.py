"""Migration helpers extracted from Media DB schema bootstrap."""

from __future__ import annotations

from typing import Any, Protocol


PostgresMigrationMap = dict[int, Any]


class SupportsPostgresMigrations(Protocol):
    """Protocol for legacy DB objects that still own PostgreSQL migrations."""

    def _get_postgres_migrations(self) -> PostgresMigrationMap: ...

    def _run_postgres_migrations(
        self,
        conn: Any,
        current_version: int,
        target_version: int,
    ) -> None: ...


def get_postgres_migrations(db: SupportsPostgresMigrations) -> PostgresMigrationMap:
    """Return the PostgreSQL migration mapping owned by the current DB object."""

    return db._get_postgres_migrations()


def run_postgres_migrations(
    db: SupportsPostgresMigrations,
    conn: Any,
    current_version: int,
    target_version: int,
) -> None:
    """Run PostgreSQL migrations via the current DB object."""

    db._run_postgres_migrations(conn, current_version, target_version)
