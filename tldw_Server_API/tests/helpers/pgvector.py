"""
pgvector pytest helpers
=======================

This module provides lightweight fixtures to exercise the PGVectorAdapter in tests.

How DSN is resolved
- The session fixture `pgvector_dsn` resolves a connection string from, in order:
  1) `PG_TEST_DSN`
  2) `PGVECTOR_DSN`
  3) `JOBS_DB_URL`
  If none are set, tests that depend on pgvector are skipped.

Example DSN values
- Local Docker service (used by CI pgvector-local job):
  PG_TEST_DSN=postgresql://postgres:postgres@localhost:5432/tldw

- With pgbouncer (optional):
  PG_TEST_DSN=postgresql://postgres:postgres@localhost:6432/tldw

What the fixture does
- Verifies connectivity and ensures the `vector` extension exists via
  `CREATE EXTENSION IF NOT EXISTS vector` (best-effort).
- A function-scoped `pgvector_temp_table` fixture creates a scratch table
  with `embedding vector(8)` and drops it after the test.

Troubleshooting
- Connection refused: ensure Postgres is running and the port matches your DSN.
- Authentication failed: verify user/password match the database setup.
- Extension missing: install pgvector in the target database or use the CI
  job that starts `pgvector/pgvector:pg18`.
- Tests skipped: export `PG_TEST_DSN` or `PGVECTOR_DSN` before running pytest.

Notes
- These fixtures use psycopg (v3) if available; if `psycopg` cannot be
  imported, dependent tests are skipped.
"""

import os
from typing import Optional

import pytest


# Optional psycopg import; skip fixtures if not installed
psycopg = pytest.importorskip("psycopg")


def _resolve_pgvector_dsn() -> Optional[str]:
    # Prefer explicit PG_TEST_DSN, then PGVECTOR_DSN, then JOBS_DB_URL
    return (
        os.getenv("PG_TEST_DSN")
        or os.getenv("PGVECTOR_DSN")
        or os.getenv("JOBS_DB_URL")
    )


def _ensure_extension(conn) -> None:
    try:
        with conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        # Best-effort
        pass


@pytest.fixture(scope="session")
def pgvector_dsn() -> Optional[str]:
    dsn = _resolve_pgvector_dsn()
    if not dsn:
        pytest.skip("PG_TEST_DSN/PGVECTOR_DSN not set; skipping pgvector tests")
    # Try a quick connectivity check
    try:
        with psycopg.connect(dsn) as conn:
            _ensure_extension(conn)
    except Exception as e:
        pytest.skip(f"pgvector DSN unreachable: {e}")
    return dsn


@pytest.fixture(scope="function")
def pgvector_temp_table(pgvector_dsn):
    """Create a temporary collection table for tests; cleanup on teardown."""
    name = "vs_test_pgvector_pytest"
    try:
        with psycopg.connect(pgvector_dsn) as conn:
            with conn, conn.cursor() as cur:
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {name} (id TEXT PRIMARY KEY, content TEXT, metadata JSONB, embedding vector(8))"
                )
    except Exception:
        pytest.skip("Failed to create pgvector test table")
    yield name
    try:
        with psycopg.connect(pgvector_dsn) as conn:
            with conn, conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {name}")
    except Exception:
        pass
