"""SQLite schema-version lookup helper."""

from __future__ import annotations

import sqlite3
from typing import Any, Protocol

from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError


class SqliteSchemaVersionDB(Protocol):
    """Protocol for DB objects exposing SQLite schema-version lookup."""


def get_db_version(
    db: SqliteSchemaVersionDB,
    conn: sqlite3.Connection | Any,
) -> int:
    """Return the current SQLite schema version for the supplied connection."""

    del db

    try:
        cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
        result = cursor.fetchone()
        return result["version"] if result else 0
    except sqlite3.Error as exc:
        if "no such table: schema_version" in str(exc):
            return 0
        raise DatabaseError(f"Could not determine database schema version: {exc}") from exc


__all__ = ["SqliteSchemaVersionDB", "get_db_version"]
