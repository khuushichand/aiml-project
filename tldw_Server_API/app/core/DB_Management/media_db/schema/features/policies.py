"""Policy schema helpers."""


def ensure_postgres_policies(db, conn) -> None:
    """Ensure the PostgreSQL row-level security policies owned by the legacy DB object."""

    db._ensure_postgres_rls(conn)
