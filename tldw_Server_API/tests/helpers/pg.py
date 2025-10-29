import os
from typing import Optional

import pytest


# Import or skip if psycopg not available
psycopg = pytest.importorskip("psycopg")


# Resolve a DSN for Postgres tests from env, preferring the general test DSNs.
# Order of precedence aligns with the AuthNZ/general fixtures so Jobs PG tests
# can reuse the same cluster without extra env wiring.
pg_dsn: Optional[str] = (
    os.getenv("TEST_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or os.getenv("JOBS_DB_URL")
    or os.getenv("POSTGRES_TEST_DSN")
)


def ensure_db_exists(dsn: str) -> None:
    """Ensure the target database exists by connecting to /postgres and creating it if missing."""
    try:
        base = dsn.rsplit("/", 1)[0] + "/postgres"
        db_name = dsn.rsplit("/", 1)[1].split("?")[0]
        with psycopg.connect(base, autocommit=True) as _conn:
            with _conn.cursor() as _cur:
                _cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db_name,))
                if _cur.fetchone() is None:
                    _cur.execute(f"CREATE DATABASE {db_name}")
    except Exception:
        # Best effort; let schema ensure fail if truly unavailable
        pass


def truncate_jobs_table(dsn: str) -> None:
    """Truncate jobs table and reset identity for clean test state."""
    with psycopg.connect(dsn) as conn:
        with conn, conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE jobs RESTART IDENTITY")


@pytest.fixture(scope="module")
def pg_schema_and_cleanup():
    """Shared PG fixture: ensure DB, ensure schema, and truncate jobs table.

    Sets standard test env defaults for reliable behavior.
    """
    # Standardize env defaults used by tests
    os.environ.setdefault("TEST_MODE", "true")
    os.environ.setdefault("AUTH_MODE", "single_user")

    # Determine DSN
    dsn = pg_dsn
    if not dsn:
        pytest.skip("JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests")

    # Ensure DB exists and schema is created
    ensure_db_exists(dsn)
    try:
        from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
        ensure_jobs_tables_pg(dsn)
    except Exception:
        # If migrations aren't importable, let tests fail naturally
        pass

    # Clean slate
    truncate_jobs_table(dsn)

    # Yield to tests
    yield

    # Optional final cleanup per module (avoid leaving residue between modules)
    try:
        truncate_jobs_table(dsn)
    except Exception:
        pass
