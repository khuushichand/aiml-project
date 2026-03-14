from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_import_governance_pack_materializes_immutable_base_objects_with_provenance(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.MCP_unified.governance_packs import (
        load_governance_pack_fixture,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_service import (
        McpHubGovernancePackService,
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

    pack = load_governance_pack_fixture("minimal_researcher_pack")
    service = McpHubGovernancePackService(repo=repo)

    result = await service.import_pack(
        pack=pack,
        owner_scope_type="user",
        owner_scope_id=7,
        actor_id=7,
    )

    assert result.blocked_objects == []
    assert result.imported_object_counts["approval_policies"] == 1
    assert result.imported_object_counts["permission_profiles"] == 1
    assert result.imported_object_counts["policy_assignments"] == 1

    governance_pack = await repo.get_governance_pack(result.governance_pack_id)
    assert governance_pack is not None
    assert governance_pack["pack_id"] == "researcher-pack"
    assert governance_pack["pack_version"] == "1.0.0"
    assert len(str(governance_pack["bundle_digest"])) == 64

    approval_policy = await repo.get_approval_policy(result.imported_object_ids["approval_policies"][0])
    assert approval_policy is not None
    assert approval_policy["is_immutable"] is True
    assert approval_policy["mode"] == "ask_every_time"

    permission_profile = await repo.get_permission_profile(
        result.imported_object_ids["permission_profiles"][0]
    )
    assert permission_profile is not None
    assert permission_profile["is_immutable"] is True
    assert permission_profile["mode"] == "preset"
    assert permission_profile["policy_document"]["capabilities"] == [
        "filesystem.read",
        "tool.invoke.research",
    ]
    assert permission_profile["policy_document"]["environment_requirements"] == [
        "workspace_bounded_read",
    ]

    profile_link = await repo.get_governance_pack_object(
        object_type="permission_profile",
        object_id=permission_profile["id"],
    )
    assert profile_link is not None
    assert profile_link["source_object_id"] == "researcher.profile"

    assignment = await repo.get_policy_assignment(result.imported_object_ids["policy_assignments"][0])
    assert assignment is not None
    assert assignment["is_immutable"] is True
    assert assignment["target_type"] == "default"
    assert int(assignment["profile_id"]) == int(permission_profile["id"])
    assert int(assignment["approval_policy_id"]) == int(approval_policy["id"])

    override = await repo.upsert_policy_override(
        int(assignment["id"]),
        override_policy_document={"allowed_tools": ["Read"]},
        broadens_access=False,
        grant_authority_snapshot={"source": "local-overlay"},
        actor_id=8,
        is_active=True,
    )
    assert override is not None
    assert override["override_policy_document"]["allowed_tools"] == ["Read"]


@pytest.mark.asyncio
async def test_import_governance_pack_rejects_duplicate_scope_identity(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.MCP_unified.governance_packs import (
        load_governance_pack_fixture,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_service import (
        GovernancePackAlreadyExistsError,
        McpHubGovernancePackService,
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

    pack = load_governance_pack_fixture("minimal_researcher_pack")
    service = McpHubGovernancePackService(repo=repo)

    await service.import_pack(
        pack=pack,
        owner_scope_type="user",
        owner_scope_id=7,
        actor_id=7,
    )

    with pytest.raises(GovernancePackAlreadyExistsError):
        await service.import_pack(
            pack=pack,
            owner_scope_type="user",
            owner_scope_id=7,
            actor_id=7,
        )

    inventory = await repo.list_governance_packs(owner_scope_type="user", owner_scope_id=7)
    assert len(inventory) == 1


@pytest.mark.asyncio
async def test_import_governance_pack_rolls_back_partial_objects_on_failure(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.MCP_unified.governance_packs import (
        load_governance_pack_fixture,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_service import (
        McpHubGovernancePackService,
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

    original_create_policy_assignment = repo.create_policy_assignment

    async def _boom_create_policy_assignment(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("assignment insert failed")

    repo.create_policy_assignment = _boom_create_policy_assignment  # type: ignore[method-assign]

    pack = load_governance_pack_fixture("minimal_researcher_pack")
    service = McpHubGovernancePackService(repo=repo)

    with pytest.raises(RuntimeError, match="assignment insert failed"):
        await service.import_pack(
            pack=pack,
            owner_scope_type="user",
            owner_scope_id=7,
            actor_id=7,
        )

    repo.create_policy_assignment = original_create_policy_assignment  # type: ignore[method-assign]

    assert await repo.list_governance_packs(owner_scope_type="user", owner_scope_id=7) == []
    assert await repo.list_permission_profiles(owner_scope_type="user", owner_scope_id=7) == []
    assert await repo.list_approval_policies(owner_scope_type="user", owner_scope_id=7) == []
    assert await repo.list_policy_assignments(owner_scope_type="user", owner_scope_id=7) == []
