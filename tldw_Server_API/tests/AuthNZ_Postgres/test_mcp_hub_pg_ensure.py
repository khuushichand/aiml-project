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
            'mcp_external_server_credential_slots',
            'mcp_external_server_secrets',
            'mcp_external_server_slot_secrets',
            'mcp_permission_profiles',
            'mcp_policy_assignments',
            'mcp_policy_audit_history',
            'mcp_policy_overrides',
            'mcp_workspace_set_objects',
            'mcp_workspace_set_object_members'
          )
        """
    )
    names = {str(row["table_name"]) for row in rows}

    assert "mcp_acp_profiles" in names
    assert "mcp_approval_decisions" in names
    assert "mcp_approval_policies" in names
    assert "mcp_credential_bindings" in names
    assert "mcp_external_servers" in names
    assert "mcp_external_server_credential_slots" in names
    assert "mcp_external_server_secrets" in names
    assert "mcp_external_server_slot_secrets" in names
    assert "mcp_permission_profiles" in names
    assert "mcp_policy_assignments" in names
    assert "mcp_policy_audit_history" in names
    assert "mcp_policy_overrides" in names
    assert "mcp_workspace_set_objects" in names
    assert "mcp_workspace_set_object_members" in names

    column_rows = await test_db_pool.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_approval_decisions'
          AND column_name IN ('consume_on_match', 'consumed_at')
        """
    )
    column_names = {str(row["column_name"]) for row in column_rows}
    assert "consume_on_match" in column_names
    assert "consumed_at" in column_names

    override_column_rows = await test_db_pool.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_policy_overrides'
          AND column_name IN ('is_active')
        """
    )
    override_column_names = {str(row["column_name"]) for row in override_column_rows}
    assert "is_active" in override_column_names

    assignment_column_rows = await test_db_pool.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_policy_assignments'
          AND column_name IN ('workspace_source_mode', 'workspace_set_object_id')
        """
    )
    assignment_column_names = {str(row["column_name"]) for row in assignment_column_rows}
    assert "workspace_source_mode" in assignment_column_names
    assert "workspace_set_object_id" in assignment_column_names

    workspace_set_column_rows = await test_db_pool.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_workspace_set_objects'
          AND column_name IN ('name', 'owner_scope_type', 'owner_scope_id')
        """
    )
    workspace_set_column_names = {str(row["column_name"]) for row in workspace_set_column_rows}
    assert "name" in workspace_set_column_names
    assert "owner_scope_type" in workspace_set_column_names
    assert "owner_scope_id" in workspace_set_column_names

    workspace_member_column_rows = await test_db_pool.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_workspace_set_object_members'
          AND column_name IN ('workspace_set_object_id', 'workspace_id')
        """
    )
    workspace_member_column_names = {str(row["column_name"]) for row in workspace_member_column_rows}
    assert "workspace_set_object_id" in workspace_member_column_names
    assert "workspace_id" in workspace_member_column_names

    external_column_rows = await test_db_pool.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_external_servers'
          AND column_name IN ('server_source', 'legacy_source_ref', 'superseded_by_server_id')
        """
    )
    external_column_names = {str(row["column_name"]) for row in external_column_rows}
    assert "server_source" in external_column_names
    assert "legacy_source_ref" in external_column_names
    assert "superseded_by_server_id" in external_column_names

    binding_column_rows = await test_db_pool.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_credential_bindings'
          AND column_name IN ('binding_mode', 'slot_name')
        """
    )
    binding_column_names = {str(row["column_name"]) for row in binding_column_rows}
    assert "binding_mode" in binding_column_names
    assert "slot_name" in binding_column_names

    slot_column_rows = await test_db_pool.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_external_server_credential_slots'
          AND column_name IN ('slot_name', 'display_name', 'secret_kind', 'privilege_class', 'is_required')
        """
    )
    slot_column_names = {str(row["column_name"]) for row in slot_column_rows}
    assert "slot_name" in slot_column_names
    assert "display_name" in slot_column_names
    assert "secret_kind" in slot_column_names
    assert "privilege_class" in slot_column_names
    assert "is_required" in slot_column_names

    slot_secret_column_rows = await test_db_pool.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_external_server_slot_secrets'
          AND column_name IN ('slot_id', 'encrypted_blob', 'key_hint')
        """
    )
    slot_secret_column_names = {str(row["column_name"]) for row in slot_secret_column_rows}
    assert "slot_id" in slot_secret_column_names
    assert "encrypted_blob" in slot_secret_column_names
    assert "key_hint" in slot_secret_column_names

    binding_index_rows = await test_db_pool.fetch(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'mcp_credential_bindings'
          AND indexname = 'uq_mcp_credential_bindings_target_server_slot'
        """
    )
    binding_index_names = {str(row["indexname"]) for row in binding_index_rows}
    assert "uq_mcp_credential_bindings_target_server_slot" in binding_index_names

    slot_index_rows = await test_db_pool.fetch(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'mcp_external_server_credential_slots'
          AND indexname = 'uq_mcp_external_server_slots_server_slot'
        """
    )
    slot_index_names = {str(row["indexname"]) for row in slot_index_rows}
    assert "uq_mcp_external_server_slots_server_slot" in slot_index_names

    workspace_member_index_rows = await test_db_pool.fetch(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'mcp_workspace_set_object_members'
          AND indexname = 'uq_mcp_workspace_set_members_object_workspace'
        """
    )
    workspace_member_index_names = {str(row["indexname"]) for row in workspace_member_index_rows}
    assert "uq_mcp_workspace_set_members_object_workspace" in workspace_member_index_names
