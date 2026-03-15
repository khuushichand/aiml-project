from __future__ import annotations

from pathlib import Path

import pytest


async def _make_repo(tmp_path, monkeypatch):
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
    return repo


@pytest.mark.asyncio
async def test_dry_run_governance_pack_uses_live_capability_mappings(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.MCP_unified.governance_packs import (
        load_governance_pack_fixture,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_service import (
        McpHubGovernancePackService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)
    service = McpHubGovernancePackService(repo=repo)
    pack = load_governance_pack_fixture("minimal_researcher_pack")

    report = await service.dry_run_pack(
        pack=pack,
        owner_scope_type="team",
        owner_scope_id=21,
    )

    assert report.verdict == "blocked"
    assert report.resolved_capabilities == []
    assert sorted(report.unresolved_capabilities) == [
        "filesystem.read",
        "tool.invoke.research",
    ]
    assert report.capability_mapping_summary == []

    await repo.create_capability_adapter_mapping(
        mapping_id="filesystem.read.global",
        owner_scope_type="global",
        owner_scope_id=None,
        capability_name="filesystem.read",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["files.read"]},
        supported_environment_requirements=["workspace_bounded_read"],
        is_active=True,
        actor_id=7,
    )
    await repo.create_capability_adapter_mapping(
        mapping_id="tool.invoke.research.team-21",
        owner_scope_type="team",
        owner_scope_id=21,
        capability_name="tool.invoke.research",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["web.search"]},
        supported_environment_requirements=[],
        is_active=True,
        actor_id=7,
    )

    report = await service.dry_run_pack(
        pack=pack,
        owner_scope_type="team",
        owner_scope_id=21,
    )

    assert report.verdict == "importable"
    assert sorted(report.resolved_capabilities) == [
        "filesystem.read",
        "tool.invoke.research",
    ]
    assert report.unresolved_capabilities == []
    assert sorted(summary["mapping_id"] for summary in report.capability_mapping_summary) == [
        "filesystem.read.global",
        "tool.invoke.research.team-21",
    ]


@pytest.mark.asyncio
async def test_dry_run_governance_pack_warns_when_profile_requirement_not_guaranteed(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.MCP_unified.governance_packs import (
        load_governance_pack_fixture,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_service import (
        McpHubGovernancePackService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)
    service = McpHubGovernancePackService(repo=repo)
    pack = load_governance_pack_fixture("minimal_researcher_pack")
    pack.profiles[0].environment_requirements = ["workspace_bounded_write"]

    await repo.create_capability_adapter_mapping(
        mapping_id="filesystem.read.global",
        owner_scope_type="global",
        owner_scope_id=None,
        capability_name="filesystem.read",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["files.read"]},
        supported_environment_requirements=[],
        is_active=True,
        actor_id=7,
    )
    await repo.create_capability_adapter_mapping(
        mapping_id="tool.invoke.research.global",
        owner_scope_type="global",
        owner_scope_id=None,
        capability_name="tool.invoke.research",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["web.search"]},
        supported_environment_requirements=[],
        is_active=True,
        actor_id=7,
    )

    report = await service.dry_run_pack(
        pack=pack,
        owner_scope_type="global",
        owner_scope_id=None,
    )

    assert report.verdict == "importable"
    assert report.unresolved_capabilities == []
    assert (
        "profile:researcher.profile requires environment requirement 'workspace_bounded_write' "
        "but current capability mappings do not guarantee it"
    ) in report.warnings


@pytest.mark.asyncio
async def test_import_governance_pack_materializes_immutable_base_objects_with_provenance(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.MCP_unified.governance_packs import (
        load_governance_pack_fixture,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_service import (
        McpHubGovernancePackService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)

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
async def test_governance_pack_repo_tracks_active_install_state_and_upgrade_lineage(
    tmp_path,
    monkeypatch,
) -> None:
    repo = await _make_repo(tmp_path, monkeypatch)

    created = await repo.create_governance_pack(
        pack_id="researcher-pack",
        pack_version="1.0.0",
        pack_schema_version=1,
        capability_taxonomy_version=1,
        adapter_contract_version=1,
        title="Researcher Pack",
        description="Initial install",
        owner_scope_type="user",
        owner_scope_id=7,
        bundle_digest="a" * 64,
        manifest={"pack_id": "researcher-pack", "pack_version": "1.0.0"},
        normalized_ir={"profiles": []},
        actor_id=7,
    )

    assert created["is_active_install"] is True
    assert created["superseded_by_governance_pack_id"] is None

    upgraded = await repo.create_governance_pack(
        pack_id="researcher-pack",
        pack_version="1.1.0",
        pack_schema_version=1,
        capability_taxonomy_version=1,
        adapter_contract_version=1,
        title="Researcher Pack",
        description="Upgrade target",
        owner_scope_type="user",
        owner_scope_id=7,
        bundle_digest="b" * 64,
        manifest={"pack_id": "researcher-pack", "pack_version": "1.1.0"},
        normalized_ir={"profiles": []},
        actor_id=7,
        is_active_install=False,
    )

    lineage = await repo.create_governance_pack_upgrade(
        pack_id="researcher-pack",
        owner_scope_type="user",
        owner_scope_id=7,
        from_governance_pack_id=int(created["id"]),
        to_governance_pack_id=int(upgraded["id"]),
        from_pack_version="1.0.0",
        to_pack_version="1.1.0",
        status="planned",
        planned_by=7,
        plan_summary={"changed_objects": 2},
    )

    assert lineage["from_pack_version"] == "1.0.0"
    assert lineage["to_pack_version"] == "1.1.0"
    assert lineage["status"] == "planned"

    history = await repo.list_governance_pack_upgrades(
        pack_id="researcher-pack",
        owner_scope_type="user",
        owner_scope_id=7,
    )

    assert [item["to_pack_version"] for item in history] == ["1.1.0"]


@pytest.mark.asyncio
async def test_import_governance_pack_rejects_duplicate_scope_identity(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.MCP_unified.governance_packs import (
        load_governance_pack_fixture,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_service import (
        GovernancePackAlreadyExistsError,
        McpHubGovernancePackService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)

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


@pytest.mark.asyncio
async def test_imported_governance_pack_denied_capabilities_narrow_runtime_policy(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.MCP_unified.governance_packs import (
        load_governance_pack_fixture,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_service import (
        McpHubGovernancePackService,
    )
    from tldw_Server_API.app.services.mcp_hub_policy_resolver import McpHubPolicyResolver

    repo = await _make_repo(tmp_path, monkeypatch)
    service = McpHubGovernancePackService(repo=repo)
    pack = load_governance_pack_fixture("minimal_researcher_pack")
    pack.profiles[0].capabilities.deny = ["tool.invoke.docs"]

    await repo.create_capability_adapter_mapping(
        mapping_id="filesystem.read.global",
        owner_scope_type="global",
        owner_scope_id=None,
        capability_name="filesystem.read",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["files.read"]},
        supported_environment_requirements=["workspace_bounded_read"],
        is_active=True,
        actor_id=7,
    )
    await repo.create_capability_adapter_mapping(
        mapping_id="tool.invoke.research.global",
        owner_scope_type="global",
        owner_scope_id=None,
        capability_name="tool.invoke.research",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["web.search"]},
        supported_environment_requirements=[],
        is_active=True,
        actor_id=7,
    )
    await repo.create_capability_adapter_mapping(
        mapping_id="tool.invoke.docs.global",
        owner_scope_type="global",
        owner_scope_id=None,
        capability_name="tool.invoke.docs",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["docs.search"]},
        supported_environment_requirements=[],
        is_active=True,
        actor_id=7,
    )

    await service.import_pack(
        pack=pack,
        owner_scope_type="user",
        owner_scope_id=7,
        actor_id=7,
    )

    resolver = McpHubPolicyResolver(repo=repo)
    policy = await resolver.resolve_for_context(
        user_id=7,
        metadata={"mcp_policy_context_enabled": True},
    )

    assert sorted(policy["allowed_tools"]) == ["files.read", "web.search"]
    assert policy["denied_tools"] == ["docs.search"]
    assert any(
        summary["capability_name"] == "tool.invoke.docs" and summary["resolution_intent"] == "deny"
        for summary in policy["capability_mapping_summary"]
    )

    inventory = await repo.list_governance_packs(owner_scope_type="user", owner_scope_id=7)
    assert len(inventory) == 1


@pytest.mark.asyncio
async def test_import_governance_pack_rolls_back_partial_objects_on_failure(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.MCP_unified.governance_packs import (
        load_governance_pack_fixture,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_service import (
        McpHubGovernancePackService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)

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
