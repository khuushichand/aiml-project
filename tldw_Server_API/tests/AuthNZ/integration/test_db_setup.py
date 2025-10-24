"""
Integration test to ensure the PostgreSQL schema initialized by fixtures is available.
"""

from __future__ import annotations

import asyncpg
import os
import pytest

pytestmark = pytest.mark.integration

_TEST_DSN = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or ""
_TEST_DSN = _TEST_DSN.strip()

def _parse_pg_dsn(dsn: str):
    try:
        from urllib.parse import urlparse
        parsed = urlparse(dsn)
        if not parsed.scheme.startswith("postgres"):
            return None
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 5432)
        user = parsed.username or "tldw_user"
        password = parsed.password or "TestPassword123!"
        return host, port, user, password
    except Exception:
        return None

_parsed = _parse_pg_dsn(_TEST_DSN) if _TEST_DSN else None
TEST_DB_HOST = (_parsed[0] if _parsed else os.getenv("TEST_DB_HOST", "localhost"))
TEST_DB_PORT = int(_parsed[1] if _parsed else int(os.getenv("TEST_DB_PORT", "5432")))
TEST_DB_USER = (_parsed[2] if _parsed else os.getenv("TEST_DB_USER", "tldw_user"))
TEST_DB_PASSWORD = (_parsed[3] if _parsed else os.getenv("TEST_DB_PASSWORD", "TestPassword123!"))


@pytest.mark.asyncio
async def test_postgres_schema_is_initialized(isolated_test_environment):
    client, db_name = isolated_test_environment

    conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=db_name,
    )

    try:
        tables = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
        )
        table_names = {row["table_name"] for row in tables}

        assert "users" in table_names
        assert "sessions" in table_names
        assert "password_history" in table_names
    finally:
        await conn.close()

    assert client is not None
