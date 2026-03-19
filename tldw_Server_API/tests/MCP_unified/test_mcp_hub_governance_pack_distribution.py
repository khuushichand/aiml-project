from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


async def _make_repo(tmp_path: Path, monkeypatch: Any):
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
async def test_governance_pack_trust_service_enforces_local_root_allowlist(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
        McpHubGovernancePackTrustService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)
    service = McpHubGovernancePackTrustService(repo=repo)
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    inside = allowed_root / "packs" / "researcher"
    inside.mkdir(parents=True)
    outside = tmp_path / "outside" / "researcher"
    outside.mkdir(parents=True)

    await service.update_policy(
        {
            "allow_local_path_sources": True,
            "allowed_local_roots": [str(allowed_root)],
        },
        actor_id=7,
    )

    allowed = await service.evaluate_local_path(str(inside))
    assert allowed["allowed"] is True
    assert allowed["resolved_path"] == str(inside.resolve())

    denied = await service.evaluate_local_path(str(outside))
    assert denied["allowed"] is False
    assert denied["reason"] == "path_not_allowed"


@pytest.mark.asyncio
async def test_governance_pack_trust_service_enforces_git_repo_and_ref_policy(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
        McpHubGovernancePackTrustService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)
    service = McpHubGovernancePackTrustService(repo=repo)

    await service.update_policy(
        {
            "allow_git_sources": True,
            "allowed_git_hosts": ["github.com"],
            "allowed_git_repositories": ["github.com/example/researcher-pack"],
            "allowed_git_ref_kinds": ["tag"],
            "require_git_signature_verification": True,
        },
        actor_id=7,
    )

    allowed = await service.evaluate_git_source(
        "https://github.com/example/researcher-pack.git",
        ref_kind="tag",
    )
    assert allowed["allowed"] is True
    assert allowed["verification_required"] is True
    assert allowed["canonical_repository"] == "github.com/example/researcher-pack"

    denied_repo = await service.evaluate_git_source(
        "https://github.com/example/other-pack.git",
        ref_kind="tag",
    )
    assert denied_repo["allowed"] is False
    assert denied_repo["reason"] == "repository_not_allowed"

    denied_ref = await service.evaluate_git_source(
        "https://github.com/example/researcher-pack.git",
        ref_kind="branch",
    )
    assert denied_ref["allowed"] is False
    assert denied_ref["reason"] == "ref_kind_not_allowed"


@pytest.mark.asyncio
async def test_governance_pack_trust_policy_persists_as_deployment_wide_config(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
        McpHubGovernancePackTrustService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)
    service = McpHubGovernancePackTrustService(repo=repo)

    updated = await service.update_policy(
        {
            "allow_local_path_sources": True,
            "allowed_local_roots": ["/srv/packs"],
            "allow_git_sources": True,
            "allowed_git_hosts": ["github.com"],
            "allowed_git_repositories": ["github.com/example/researcher-pack"],
            "allowed_git_ref_kinds": ["commit", "tag"],
            "require_git_signature_verification": True,
        },
        actor_id=11,
    )

    assert updated["allowed_local_roots"] == ["/srv/packs"]
    assert updated["allowed_git_ref_kinds"] == ["commit", "tag"]
    assert updated["require_git_signature_verification"] is True

    stored = await repo.get_governance_pack_trust_policy()
    assert stored["policy_document"]["allowed_local_roots"] == ["/srv/packs"]
    assert stored["updated_by"] == 11
