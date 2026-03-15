"""FTS schema helpers."""


def ensure_sqlite_fts_structures(db, conn) -> None:
    """Ensure the SQLite FTS structures owned by the legacy Media DB object."""

    db._ensure_fts_structures(conn)


def ensure_postgres_fts(db, conn) -> None:
    """Ensure the PostgreSQL FTS structures owned by the legacy Media DB object."""

    db._ensure_postgres_fts(conn)
