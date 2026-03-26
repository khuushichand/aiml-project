"""PostgreSQL migration body for schema v22 email-native objects."""

from __future__ import annotations

from typing import Any, Protocol


class PostgresEmailSchemaBody(Protocol):
    """DB surface required by the v22 migration helper."""

    def _ensure_postgres_email_schema(self, conn: Any) -> None: ...


def run_postgres_migrate_to_v22(db: PostgresEmailSchemaBody, conn: Any) -> None:
    """Ensure email-native schema and lookup indexes exist for PostgreSQL."""

    db._ensure_postgres_email_schema(conn)


__all__ = ["PostgresEmailSchemaBody", "run_postgres_migrate_to_v22"]
