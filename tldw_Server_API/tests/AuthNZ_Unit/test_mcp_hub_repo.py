from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

pytest_plugins = ("tldw_Server_API.tests.AuthNZ.conftest",)


@pytest.mark.asyncio
async def test_repo_can_crud_acp_profile(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(str(db_path)))

    repo = McpHubRepo(pool)
    await repo.ensure_tables()

    created = await repo.create_acp_profile(
        name="default-dev",
        owner_scope_type="org",
        owner_scope_id=42,
        profile_json='{"sandbox":"strict"}',
        actor_id=1,
    )
    assert created["name"] == "default-dev"

    fetched = await repo.get_acp_profile(int(created["id"]))
    assert fetched is not None
    assert fetched["name"] == "default-dev"
    assert fetched["owner_scope_type"] == "org"
    assert int(fetched["owner_scope_id"]) == 42

    listed = await repo.list_acp_profiles(owner_scope_type="org", owner_scope_id=42)
    assert len(listed) == 1
    assert listed[0]["name"] == "default-dev"

    updated = await repo.update_acp_profile(
        int(created["id"]),
        name="default-prod",
        profile_json='{"sandbox":"relaxed"}',
        is_active=False,
        actor_id=2,
    )
    assert updated is not None
    assert updated["name"] == "default-prod"
    assert updated["is_active"] is False

    deleted = await repo.delete_acp_profile(int(created["id"]))
    assert deleted is True
    missing = await repo.get_acp_profile(int(created["id"]))
    assert missing is None


@pytest.mark.asyncio
async def test_repo_external_server_secret_is_stored_separately(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(str(db_path)))

    repo = McpHubRepo(pool)
    await repo.ensure_tables()

    await repo.upsert_external_server(
        server_id="docs",
        name="Docs",
        transport="stdio",
        config_json='{"cmd":"npx"}',
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        actor_id=1,
    )
    await repo.upsert_external_secret(
        server_id="docs",
        encrypted_blob='{"ciphertext":"abc"}',
        key_hint="cdef",
        actor_id=1,
    )

    row = await repo.get_external_server("docs")
    assert row is not None
    assert row["id"] == "docs"
    assert row["secret_configured"] is True
    assert "encrypted_blob" not in row

    secret = await repo.get_external_secret("docs")
    assert secret is not None
    assert secret["server_id"] == "docs"
    assert secret["encrypted_blob"] == '{"ciphertext":"abc"}'


@pytest.mark.asyncio
async def test_repo_can_crud_permission_profile_and_policy_assignment(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

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
        name="Read Current Folder",
        owner_scope_type="user",
        owner_scope_id=7,
        mode="custom",
        policy_document={
            "capabilities": ["filesystem.read"],
            "path_scope": "cwd_descendants",
        },
        actor_id=7,
        description="Read-only profile for the current workspace",
        is_active=True,
    )
    assert profile["name"] == "Read Current Folder"
    assert profile["owner_scope_type"] == "user"
    assert int(profile["owner_scope_id"]) == 7
    assert profile["policy_document"]["capabilities"] == ["filesystem.read"]

    assignment = await repo.create_policy_assignment(
        target_type="persona",
        target_id="researcher",
        owner_scope_type="user",
        owner_scope_id=7,
        profile_id=int(profile["id"]),
        inline_policy_document={"approval_mode": "ask_outside_profile"},
        approval_policy_id=None,
        actor_id=7,
        is_active=True,
    )
    assert assignment["target_type"] == "persona"
    assert assignment["target_id"] == "researcher"
    assert int(assignment["profile_id"]) == int(profile["id"])
    assert assignment["inline_policy_document"]["approval_mode"] == "ask_outside_profile"

    fetched = await repo.get_policy_assignment(int(assignment["id"]))
    assert fetched is not None
    assert fetched["target_type"] == "persona"
    assert fetched["target_id"] == "researcher"

    listed = await repo.list_policy_assignments(owner_scope_type="user", owner_scope_id=7)
    assert len(listed) == 1
    assert listed[0]["target_type"] == "persona"
    assert listed[0]["inline_policy_document"]["approval_mode"] == "ask_outside_profile"

    updated = await repo.update_policy_assignment(
        int(assignment["id"]),
        inline_policy_document={"approval_mode": "ask_every_time"},
        actor_id=8,
    )
    assert updated is not None
    assert updated["inline_policy_document"]["approval_mode"] == "ask_every_time"

    deleted = await repo.delete_policy_assignment(int(assignment["id"]))
    assert deleted is True
    missing = await repo.get_policy_assignment(int(assignment["id"]))
    assert missing is None


@pytest.mark.asyncio
async def test_repo_update_policy_assignment_can_clear_nullable_fields(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

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
        name="Runtime Profile",
        owner_scope_type="user",
        owner_scope_id=7,
        mode="custom",
        policy_document={"capabilities": ["filesystem.read"]},
        actor_id=7,
    )
    assignment = await repo.create_policy_assignment(
        target_type="persona",
        target_id="researcher",
        owner_scope_type="user",
        owner_scope_id=7,
        profile_id=int(profile["id"]),
        inline_policy_document={"approval_mode": "ask_outside_profile"},
        approval_policy_id=9,
        actor_id=7,
        is_active=True,
    )

    updated = await repo.update_policy_assignment(
        int(assignment["id"]),
        profile_id=None,
        approval_policy_id=None,
        actor_id=8,
    )

    assert updated is not None
    assert updated["profile_id"] is None
    assert updated["approval_policy_id"] is None


@pytest.mark.asyncio
async def test_repo_can_crud_approval_policy_and_match_active_decision(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(str(db_path)))

    repo = McpHubRepo(pool)
    await repo.ensure_tables()

    policy = await repo.create_approval_policy(
        name="Outside Profile",
        description="Require approval for tools outside the active profile",
        owner_scope_type="user",
        owner_scope_id=7,
        mode="ask_outside_profile",
        rules={"duration_options": ["once", "session"]},
        actor_id=7,
        is_active=True,
    )
    assert policy["name"] == "Outside Profile"
    assert policy["mode"] == "ask_outside_profile"
    assert policy["rules"]["duration_options"] == ["once", "session"]

    listed = await repo.list_approval_policies(owner_scope_type="user", owner_scope_id=7)
    assert len(listed) == 1
    assert listed[0]["name"] == "Outside Profile"

    updated = await repo.update_approval_policy(
        int(policy["id"]),
        mode="temporary_elevation_allowed",
        rules={"duration_options": ["session"]},
        actor_id=8,
    )
    assert updated is not None
    assert updated["mode"] == "temporary_elevation_allowed"
    assert updated["rules"]["duration_options"] == ["session"]

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    decision = await repo.create_approval_decision(
        approval_policy_id=int(policy["id"]),
        context_key="user:7|persona:researcher",
        conversation_id="sess-1",
        tool_name="Bash",
        scope_key="tool:Bash|command:git-status",
        decision="approved",
        expires_at=expires_at,
        consume_on_match=False,
        actor_id=7,
    )
    assert decision["decision"] == "approved"
    assert decision["consume_on_match"] is False

    matched = await repo.find_active_approval_decision(
        approval_policy_id=int(policy["id"]),
        context_key="user:7|persona:researcher",
        conversation_id="sess-1",
        tool_name="Bash",
        scope_key="tool:Bash|command:git-status",
        decision="approved",
        now=datetime.now(timezone.utc),
    )
    assert matched is not None
    assert matched["decision"] == "approved"
    assert matched["tool_name"] == "Bash"

    expired = await repo.expire_approval_decision(
        int(decision["id"]),
        expires_at=datetime.now(timezone.utc),
    )
    assert expired is not None

    after_consume = await repo.find_active_approval_decision(
        approval_policy_id=int(policy["id"]),
        context_key="user:7|persona:researcher",
        conversation_id="sess-1",
        tool_name="Bash",
        scope_key="tool:Bash|command:git-status",
        decision="approved",
        now=datetime.now(timezone.utc),
    )
    assert after_consume is None

    single_use = await repo.create_approval_decision(
        approval_policy_id=int(policy["id"]),
        context_key="user:7|persona:researcher",
        conversation_id="sess-1",
        tool_name="Bash",
        scope_key="tool:Bash|command:git-status",
        decision="approved",
        expires_at=None,
        consume_on_match=True,
        actor_id=7,
    )
    assert single_use["consume_on_match"] is True

    consumed = await repo.consume_active_approval_decision(
        approval_policy_id=int(policy["id"]),
        context_key="user:7|persona:researcher",
        conversation_id="sess-1",
        tool_name="Bash",
        scope_key="tool:Bash|command:git-status",
        now=datetime.now(timezone.utc),
    )
    assert consumed is not None
    assert consumed["id"] == single_use["id"]
    assert consumed["consumed_at"] is not None

    consumed_again = await repo.consume_active_approval_decision(
        approval_policy_id=int(policy["id"]),
        context_key="user:7|persona:researcher",
        conversation_id="sess-1",
        tool_name="Bash",
        scope_key="tool:Bash|command:git-status",
        now=datetime.now(timezone.utc),
    )
    assert consumed_again is None

    deleted = await repo.delete_approval_policy(int(policy["id"]))
    assert deleted is True
