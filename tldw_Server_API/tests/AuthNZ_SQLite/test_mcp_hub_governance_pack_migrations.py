from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_mcp_hub_governance_pack_tables_exist_after_authnz_migrations_sqlite(
    tmp_path,
    monkeypatch,
) -> None:
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

    assert "mcp_governance_packs" in names
    assert "mcp_governance_pack_objects" in names

    governance_pack_columns = await pool.fetchall("PRAGMA table_info(mcp_governance_packs)")
    governance_pack_column_names = {str(row["name"]) for row in governance_pack_columns}
    assert "pack_id" in governance_pack_column_names
    assert "pack_version" in governance_pack_column_names
    assert "bundle_digest" in governance_pack_column_names
    assert "manifest_json" in governance_pack_column_names
    assert "normalized_ir_json" in governance_pack_column_names
    assert "owner_scope_type" in governance_pack_column_names
    assert "owner_scope_id" in governance_pack_column_names

    governance_object_columns = await pool.fetchall("PRAGMA table_info(mcp_governance_pack_objects)")
    governance_object_column_names = {str(row["name"]) for row in governance_object_columns}
    assert "governance_pack_id" in governance_object_column_names
    assert "object_type" in governance_object_column_names
    assert "object_id" in governance_object_column_names
    assert "source_object_id" in governance_object_column_names

    profile_columns = await pool.fetchall("PRAGMA table_info(mcp_permission_profiles)")
    profile_column_names = {str(row["name"]) for row in profile_columns}
    assert "is_immutable" in profile_column_names

    assignment_columns = await pool.fetchall("PRAGMA table_info(mcp_policy_assignments)")
    assignment_column_names = {str(row["name"]) for row in assignment_columns}
    assert "is_immutable" in assignment_column_names

    approval_columns = await pool.fetchall("PRAGMA table_info(mcp_approval_policies)")
    approval_column_names = {str(row["name"]) for row in approval_columns}
    assert "is_immutable" in approval_column_names
