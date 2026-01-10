import os
from typing import Optional

import pytest


# Import or skip if psycopg not available
psycopg = pytest.importorskip("psycopg")
import socket
from urllib.parse import urlparse, urlunparse


# Resolve a DSN for Postgres tests from env, preferring the general test DSNs.
# If none are set, build a DSN using the centralized helper so we honor
# POSTGRES_* fallbacks (e.g., container env like tldw/tldw/tldw_content).
pg_dsn: Optional[str] = None
def _normalize_dsn(dsn: str) -> str:
    try:
        p = urlparse(dsn)
        host = p.hostname
        port = p.port or 5432
        # If no host or an unresolvable host is provided, fall back to 127.0.0.1
        needs_fallback = False
        if not host:
            needs_fallback = True
        else:
            try:
                socket.getaddrinfo(host, port)
            except Exception:
                needs_fallback = True
        if needs_fallback:
            # Rebuild DSN with 127.0.0.1 while preserving user/pass/db/port
            netloc = p.netloc
            # netloc could be 'user:pass@host:port' or similar
            # Recompose with host replaced
            userinfo = ''
            if '@' in netloc:
                userinfo, _ = netloc.split('@', 1)
            new_netloc = f"{userinfo+'@' if userinfo else ''}127.0.0.1:{port}"
            p = p._replace(netloc=new_netloc)
            return urlunparse(p)
        return dsn
    except Exception:
        return dsn

try:
    from tldw_Server_API.tests.helpers.pg_env import get_pg_env
    pg_dsn = _normalize_dsn(get_pg_env().dsn)
except Exception:
    pg_dsn = None


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
    # Skip cleanly when a proper Postgres DSN is not provided
    if not dsn or not str(dsn).lower().startswith("postgres"):
        pytest.skip("Postgres DSN not configured; skipping Postgres jobs tests")

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
