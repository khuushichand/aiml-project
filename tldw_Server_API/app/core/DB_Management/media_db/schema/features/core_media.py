"""Core media schema helpers."""


def apply_sqlite_core_media_schema(db, conn) -> None:
    """Apply the SQLite base schema owned by the legacy Media DB object."""

    db._apply_schema_v1_sqlite(conn)


def apply_postgres_core_media_schema(db, conn) -> None:
    """Apply the PostgreSQL base schema owned by the legacy Media DB object."""

    db._apply_schema_v1_postgres(conn)
