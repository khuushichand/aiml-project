"""PostgreSQL claims migration body helpers."""

from __future__ import annotations

from typing import Any, Protocol


class PostgresClaimsBody(Protocol):
    """Protocol for DB objects that can ensure PostgreSQL claims state."""

    def _ensure_postgres_claims_tables(self, conn: Any) -> None: ...
    def _ensure_postgres_claims_extensions(self, conn: Any) -> None: ...


def run_postgres_migrate_to_v10(db: PostgresClaimsBody, conn: Any) -> None:
    """Run the PostgreSQL v10 claims migration body."""

    db._ensure_postgres_claims_tables(conn)
    db._ensure_postgres_claims_extensions(conn)


def run_postgres_migrate_to_v17(db: PostgresClaimsBody, conn: Any) -> None:
    """Run the PostgreSQL v17 claims migration body."""

    db._ensure_postgres_claims_tables(conn)
    db._ensure_postgres_claims_extensions(conn)


__all__ = [
    "PostgresClaimsBody",
    "run_postgres_migrate_to_v10",
    "run_postgres_migrate_to_v17",
]
