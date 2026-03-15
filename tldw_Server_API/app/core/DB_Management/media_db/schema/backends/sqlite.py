"""SQLite schema bootstrap implementation for Media DB."""


def initialize_sqlite_schema(db) -> None:
    """Initialize or migrate the SQLite schema using the legacy implementation."""

    db._initialize_schema_sqlite()
