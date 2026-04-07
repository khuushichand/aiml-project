"""SQLite schema bootstrap implementation for Media DB."""

from __future__ import annotations

from tldw_Server_API.app.core.DB_Management.media_db.schema.backends import (
    sqlite_helpers as sqlite_helpers_module,
)


def initialize_sqlite_schema(
    db: sqlite_helpers_module.SupportsSqlitePostCoreStructures,
) -> None:
    """Initialize or migrate the SQLite schema through the package coordinator."""

    sqlite_helpers_module.bootstrap_sqlite_schema(db)
