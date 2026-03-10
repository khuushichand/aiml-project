from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_mcp_hub_tables_exist_after_authnz_migrations_sqlite(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    rows = await pool.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    names = {str(row["name"]) for row in rows}

    assert "mcp_acp_profiles" in names
    assert "mcp_external_servers" in names
    assert "mcp_external_server_secrets" in names
    assert "mcp_permission_profiles" in names
    assert "mcp_policy_assignments" in names
    assert "mcp_policy_overrides" in names
    assert "mcp_approval_policies" in names
    assert "mcp_approval_decisions" in names
    assert "mcp_credential_bindings" in names
    assert "mcp_policy_audit_history" in names

    columns = await pool.fetchall("PRAGMA table_info(mcp_approval_decisions)")
    column_names = {str(row["name"]) for row in columns}
    assert "consume_on_match" in column_names
    assert "consumed_at" in column_names

    override_columns = await pool.fetchall("PRAGMA table_info(mcp_policy_overrides)")
    override_column_names = {str(row["name"]) for row in override_columns}
    assert "is_active" in override_column_names

    external_columns = await pool.fetchall("PRAGMA table_info(mcp_external_servers)")
    external_column_names = {str(row["name"]) for row in external_columns}
    assert "server_source" in external_column_names
    assert "legacy_source_ref" in external_column_names
    assert "superseded_by_server_id" in external_column_names

    binding_columns = await pool.fetchall("PRAGMA table_info(mcp_credential_bindings)")
    binding_column_names = {str(row["name"]) for row in binding_columns}
    assert "binding_mode" in binding_column_names

    binding_indexes = await pool.fetchall("PRAGMA index_list(mcp_credential_bindings)")
    unique_binding_indexes = {
        str(row["name"])
        for row in binding_indexes
        if int(row["unique"]) == 1
    }
    assert "uq_mcp_credential_bindings_target_server" in unique_binding_indexes
