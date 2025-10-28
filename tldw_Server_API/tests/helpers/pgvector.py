"""
pgvector pytest helpers
=======================

This module provides lightweight fixtures to exercise the PGVectorAdapter in tests.

How DSN is resolved (tests only)
- The session fixture `pgvector_dsn` resolves a connection string from, in order:
  1) `PG_TEST_DSN`
  2) `PGVECTOR_DSN`
  3) `JOBS_DB_URL`
  If none are set, tests that depend on pgvector are skipped. Tests do NOT read user-facing config files.

Example DSN values
- Local Docker service (default in compose):
  PG_TEST_DSN=postgresql://tldw_user:TestPassword123!@localhost:5432/tldw_users

What the fixture does
- Verifies connectivity and ensures the `vector` extension exists via
  `CREATE EXTENSION IF NOT EXISTS vector` (best-effort).
- A function-scoped `pgvector_temp_table` fixture creates a scratch table
  with `embedding vector(8)` and drops it after the test.

Troubleshooting
- Connection refused: ensure Postgres is running and the port matches your DSN.
- Authentication failed: verify user/password match the database setup.
- Extension missing: install pgvector in the target database or start the pgvector image.
- Tests skipped: set one of the DSN sources above.
"""

import os
from typing import Optional

import pytest


def _resolve_pgvector_dsn() -> Optional[str]:
    # Tests rely on environment variables only; do not read user-facing config.
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
    # Optional psycopg import here so we don't abort collection if missing
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not installed; skipping pgvector tests")
    dsn = _resolve_pgvector_dsn()
    if not dsn:
        pytest.skip("No pgvector DSN found (PG_TEST_DSN/PGVECTOR_DSN/JOBS_DB_URL or config)")
    # Try a quick connectivity check
    try:
        with psycopg.connect(dsn) as conn:
            _ensure_extension(conn)
    except Exception as e:
        pytest.skip(f"pgvector DSN unreachable: {e}")

    # Expose the resolved DSN to the environment and app settings so endpoints default to PG
    prev_pgvector_dsn = os.getenv("PGVECTOR_DSN")
    os.environ["PGVECTOR_DSN"] = dsn
    # Patch app settings to use pgvector by default for these tests
    try:
        from tldw_Server_API.app.core.config import settings as app_settings
        prev_rag = app_settings.get("RAG", None)
        rag_cfg = dict(prev_rag or {})
        rag_cfg["vector_store_type"] = "pgvector"
        pg_cfg = dict(rag_cfg.get("pgvector", {})) if isinstance(rag_cfg.get("pgvector"), dict) else {}
        pg_cfg["dsn"] = dsn
        rag_cfg["pgvector"] = pg_cfg
        app_settings["RAG"] = rag_cfg
    except Exception:
        prev_rag = None
    try:
        yield dsn
    finally:
        if prev_pgvector_dsn is None:
            os.environ.pop("PGVECTOR_DSN", None)
        else:
            os.environ["PGVECTOR_DSN"] = prev_pgvector_dsn
        # Restore previous RAG config
        try:
            if prev_rag is None:
                # Best-effort: remove key if we added one
                if hasattr(app_settings, "pop"):
                    app_settings.pop("RAG", None)
                else:
                    app_settings["RAG"] = {}
            else:
                app_settings["RAG"] = prev_rag
        except Exception:
            pass


@pytest.fixture(scope="function")
def pgvector_temp_table(pgvector_dsn):
    """Create a temporary collection table for tests; cleanup on teardown."""
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not installed; skipping pgvector tests")
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
