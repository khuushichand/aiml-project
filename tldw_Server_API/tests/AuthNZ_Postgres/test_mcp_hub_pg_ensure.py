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
            'mcp_approval_decisions',
            'mcp_approval_policies',
            'mcp_credential_bindings',
            'mcp_external_servers',
            'mcp_external_server_secrets',
            'mcp_permission_profiles',
            'mcp_policy_assignments',
            'mcp_policy_audit_history',
            'mcp_policy_overrides'
          )
        """
    )
    names = {str(row["table_name"]) for row in rows}

    assert "mcp_acp_profiles" in names
    assert "mcp_approval_decisions" in names
    assert "mcp_approval_policies" in names
    assert "mcp_credential_bindings" in names
    assert "mcp_external_servers" in names
    assert "mcp_external_server_secrets" in names
    assert "mcp_permission_profiles" in names
    assert "mcp_policy_assignments" in names
    assert "mcp_policy_audit_history" in names
    assert "mcp_policy_overrides" in names
