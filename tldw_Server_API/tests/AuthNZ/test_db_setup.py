"""
Integration test to ensure the PostgreSQL schema initialized by fixtures is available.
"""

from __future__ import annotations

import asyncpg
import os
import pytest

pytestmark = pytest.mark.integration

TEST_DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
TEST_DB_PORT = int(os.getenv("TEST_DB_PORT", "5432"))
TEST_DB_USER = os.getenv("TEST_DB_USER", "tldw_user")
TEST_DB_PASSWORD = os.getenv("TEST_DB_PASSWORD", "TestPassword123!")


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
