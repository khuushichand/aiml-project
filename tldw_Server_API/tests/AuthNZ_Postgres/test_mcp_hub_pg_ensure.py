from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_ensure_mcp_hub_tables_pg_creates_required_tables(test_db_pool) -> None:
    from tldw_Server_API.app.core.AuthNZ.pg_migrations_extra import (
        ensure_mcp_hub_tables_pg,
    )

    assert await ensure_mcp_hub_tables_pg(test_db_pool)

    rows = await test_db_pool.fetch(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN (
            'mcp_acp_profiles',
            'mcp_external_servers',
            'mcp_external_server_secrets'
          )
        """
    )
    names = {str(row["table_name"]) for row in rows}

    assert "mcp_acp_profiles" in names
    assert "mcp_external_servers" in names
    assert "mcp_external_server_secrets" in names

