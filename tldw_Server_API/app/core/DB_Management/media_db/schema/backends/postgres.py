"""PostgreSQL schema bootstrap implementation for Media DB."""


def initialize_postgres_schema(db) -> None:
    """Initialize or migrate the PostgreSQL schema using the legacy implementation."""

    db._initialize_schema_postgres()
