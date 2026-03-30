"""PostgreSQL schema bootstrap implementation for Media DB."""

from __future__ import annotations

from tldw_Server_API.app.core.DB_Management.media_db.schema.backends import (
    postgres_helpers as postgres_helpers_module,
)


def initialize_postgres_schema(
    db: postgres_helpers_module.SupportsPostgresPostCoreStructures,
) -> None:
    """Initialize or migrate the PostgreSQL schema through the package coordinator."""

    postgres_helpers_module.bootstrap_postgres_schema(db)
