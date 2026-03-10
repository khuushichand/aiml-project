from __future__ import annotations

import json
from pathlib import Path

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo

pytest_plugins = ("tldw_Server_API.tests.AuthNZ.conftest",)


@pytest.mark.asyncio
async def test_external_access_resolver_is_slot_aware(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.services.mcp_hub_external_access_resolver import (
        McpHubExternalAccessResolver,
    )

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()
    pool = await get_db_pool()
    ensure_authnz_tables(Path(str(db_path)))

    repo = McpHubRepo(pool)
    await repo.ensure_tables()

    profile = await repo.create_permission_profile(
        name="External Docs",
        owner_scope_type="user",
        owner_scope_id=1,
        mode="custom",
        policy_document={"capabilities": ["network.external"]},
        actor_id=1,
    )
    assignment = await repo.create_policy_assignment(
        target_type="persona",
        target_id="researcher",
        owner_scope_type="user",
        owner_scope_id=1,
        profile_id=int(profile["id"]),
        inline_policy_document={"capabilities": ["network.external"]},
        approval_policy_id=None,
        actor_id=1,
        is_active=True,
    )
    await repo.upsert_external_server(
        server_id="docs",
        name="Docs",
        transport="websocket",
        config_json=json.dumps({"websocket": {"url": "wss://docs.example/ws"}}),
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        actor_id=1,
    )
    await repo.create_external_server_credential_slot(
        server_id="docs",
        slot_name="token_readonly",
        display_name="Read-only token",
        secret_kind="bearer_token",
        privilege_class="read",
        is_required=True,
        actor_id=1,
    )
    await repo.create_external_server_credential_slot(
        server_id="docs",
        slot_name="token_write",
        display_name="Write token",
        secret_kind="api_key",
        privilege_class="write",
        is_required=False,
        actor_id=1,
    )
    await repo.upsert_external_server_slot_secret(
        server_id="docs",
        slot_name="token_readonly",
        encrypted_blob='{"ciphertext":"abc"}',
        key_hint="cdef",
        actor_id=1,
    )
    await repo.create_credential_binding(
        binding_target_type="profile",
        binding_target_id=str(profile["id"]),
        external_server_id="docs",
        slot_name="token_readonly",
        credential_ref="slot",
        binding_mode="grant",
        usage_rules={},
        actor_id=1,
    )
    await repo.create_credential_binding(
        binding_target_type="assignment",
        binding_target_id=str(assignment["id"]),
        external_server_id="docs",
        slot_name="token_write",
        credential_ref="slot",
        binding_mode="grant",
        usage_rules={},
        actor_id=1,
    )
    await repo.create_credential_binding(
        binding_target_type="assignment",
        binding_target_id=str(assignment["id"]),
        external_server_id="docs",
        slot_name="token_readonly",
        credential_ref="slot",
        binding_mode="disable",
        usage_rules={},
        actor_id=1,
    )

    resolver = McpHubExternalAccessResolver(repo=repo)
    summary = await resolver.resolve(
        assignment_id=int(assignment["id"]),
        effective_policy={"capabilities": ["network.external"]},
    )

    assert summary["servers"][0]["server_id"] == "docs"
    assert summary["servers"][0]["slots"][0]["slot_name"] == "token_readonly"
    assert summary["servers"][0]["slots"][0]["blocked_reason"] == "disabled_by_assignment"
    assert summary["servers"][0]["slots"][1]["slot_name"] == "token_write"
    assert summary["servers"][0]["slots"][1]["granted_by"] == "assignment"


@pytest.mark.asyncio
async def test_external_access_resolver_marks_missing_slot_secret(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.services.mcp_hub_external_access_resolver import (
        McpHubExternalAccessResolver,
    )

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()
    pool = await get_db_pool()
    ensure_authnz_tables(Path(str(db_path)))

    repo = McpHubRepo(pool)
    await repo.ensure_tables()

    profile = await repo.create_permission_profile(
        name="External Docs",
        owner_scope_type="user",
        owner_scope_id=1,
        mode="custom",
        policy_document={"capabilities": ["network.external"]},
        actor_id=1,
    )
    assignment = await repo.create_policy_assignment(
        target_type="persona",
        target_id="researcher",
        owner_scope_type="user",
        owner_scope_id=1,
        profile_id=int(profile["id"]),
        inline_policy_document={"capabilities": ["network.external"]},
        approval_policy_id=None,
        actor_id=1,
        is_active=True,
    )
    await repo.upsert_external_server(
        server_id="docs",
        name="Docs",
        transport="websocket",
        config_json=json.dumps({"websocket": {"url": "wss://docs.example/ws"}}),
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        actor_id=1,
    )
    await repo.create_external_server_credential_slot(
        server_id="docs",
        slot_name="token_readonly",
        display_name="Read-only token",
        secret_kind="bearer_token",
        privilege_class="read",
        is_required=True,
        actor_id=1,
    )
    await repo.create_credential_binding(
        binding_target_type="profile",
        binding_target_id=str(profile["id"]),
        external_server_id="docs",
        slot_name="token_readonly",
        credential_ref="slot",
        binding_mode="grant",
        usage_rules={},
        actor_id=1,
    )

    resolver = McpHubExternalAccessResolver(repo=repo)
    summary = await resolver.resolve(
        assignment_id=int(assignment["id"]),
        effective_policy={"capabilities": ["network.external"]},
    )

    assert summary["servers"][0]["slots"][0]["slot_name"] == "token_readonly"
    assert summary["servers"][0]["slots"][0]["blocked_reason"] == "missing_secret"
