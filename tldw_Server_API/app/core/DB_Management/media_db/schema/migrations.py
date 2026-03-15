"""Migration helpers extracted from Media DB schema bootstrap."""


def get_postgres_migrations(db):
    """Return the PostgreSQL migration mapping owned by the current DB object."""

    return db._get_postgres_migrations()


def run_postgres_migrations(db, conn, current_version: int, target_version: int) -> None:
    """Run PostgreSQL migrations via the current DB object."""

    db._run_postgres_migrations(conn, current_version, target_version)
