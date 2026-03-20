from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
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


def _fixture_pack_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "fixtures"
        / "governance_packs"
        / "minimal_researcher_pack"
    )


def _init_git_pack_repo(tmp_path: Path, *, subpath: str = "packs/researcher") -> tuple[str, str]:
    repo_root = tmp_path / "git-pack"
    repo_root.mkdir()
    pack_root = repo_root / subpath
    shutil.copytree(_fixture_pack_path(), pack_root)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "codex@example.com"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Codex"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "Add governance pack fixture"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "tag", "v1.0.0"], cwd=repo_root, check=True, capture_output=True, text=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo_root.as_uri(), commit


class _FakeGitTrustService:
    def __init__(
        self,
        *,
        canonical_repository: str = "github.com/example/researcher-pack",
        verification_required: bool = False,
        trusted_git_key_fingerprints: list[str] | None = None,
    ) -> None:
        self.canonical_repository = canonical_repository
        self.verification_required = verification_required
        self.trusted_git_key_fingerprints = list(trusted_git_key_fingerprints or [])
        self.calls: list[dict[str, str]] = []

    async def evaluate_git_source(self, repo_url: str, *, ref_kind: str) -> dict[str, Any]:
        self.calls.append({"repo_url": repo_url, "ref_kind": ref_kind})
        return {
            "allowed": True,
            "reason": None,
            "canonical_repository": self.canonical_repository,
            "verification_required": self.verification_required,
            "trusted_git_key_fingerprints": list(self.trusted_git_key_fingerprints),
        }


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


@pytest.mark.asyncio
async def test_governance_pack_trust_service_normalizes_structured_signers_and_legacy_fingerprints(
    tmp_path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
        McpHubGovernancePackTrustService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)
    service = McpHubGovernancePackTrustService(repo=repo)

    policy = await service.update_policy(
        {
            "allow_git_sources": True,
            "allowed_git_hosts": ["github.com"],
            "allowed_git_repositories": ["github.com/example/packs"],
            "allowed_git_ref_kinds": ["tag"],
            "require_git_signature_verification": True,
            "trusted_signers": [
                {
                    "fingerprint": "abc123",
                    "display_name": "Release Bot",
                    "repo_bindings": [
                        "github.com/example/packs",
                        "github.com/example/",
                    ],
                    "status": "active",
                },
                {
                    "fingerprint": "def456",
                    "repo_bindings": ["github.com/example"],
                    "status": "inactive",
                },
            ],
            "trusted_git_key_fingerprints": ["legacy789"],
        },
        actor_id=1,
    )

    assert policy["trusted_signers"][0]["fingerprint"] == "ABC123"
    assert policy["trusted_signers"][0]["display_name"] == "Release Bot"
    assert policy["trusted_signers"][0]["repo_bindings"] == [
        "github.com/example/packs",
        "github.com/example/",
    ]
    assert policy["trusted_signers"][0]["status"] == "active"
    assert policy["trusted_signers"][1]["fingerprint"] == "DEF456"
    assert policy["trusted_signers"][1]["repo_bindings"] == ["github.com/example"]
    assert policy["trusted_signers"][1]["status"] == "inactive"
    assert policy["trusted_signers"][2]["fingerprint"] == "LEGACY789"
    assert policy["trusted_signers"][2]["repo_bindings"] == []
    assert policy["trusted_signers"][2]["status"] == "active"
    assert policy["trusted_git_key_fingerprints"] == ["ABC123", "DEF456", "LEGACY789"]


@pytest.mark.asyncio
async def test_distribution_service_resolves_allowed_local_pack_and_digest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
        McpHubGovernancePackTrustService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)
    trust_service = McpHubGovernancePackTrustService(repo=repo)
    allowed_root = tmp_path / "allowed"
    pack_path = allowed_root / "researcher-pack"
    allowed_root.mkdir()
    shutil.copytree(_fixture_pack_path(), pack_path)
    await trust_service.update_policy(
        {
            "allow_local_path_sources": True,
            "allowed_local_roots": [str(allowed_root)],
        },
        actor_id=5,
    )

    service = McpHubGovernancePackDistributionService(trust_service=trust_service)
    resolved = await service.resolve_local_path(str(pack_path))

    assert resolved.manifest.pack_id == "researcher-pack"
    assert resolved.source_type == "local_path"
    assert resolved.source_location == str(pack_path.resolve())
    assert resolved.pack_content_digest


@pytest.mark.asyncio
async def test_distribution_service_resolve_local_path_uses_thread_offload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services import mcp_hub_governance_pack_distribution_service as distribution_module
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
        McpHubGovernancePackTrustService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)
    trust_service = McpHubGovernancePackTrustService(repo=repo)
    allowed_root = tmp_path / "allowed"
    pack_path = allowed_root / "researcher-pack"
    allowed_root.mkdir()
    shutil.copytree(_fixture_pack_path(), pack_path)
    await trust_service.update_policy(
        {
            "allow_local_path_sources": True,
            "allowed_local_roots": [str(allowed_root)],
        },
        actor_id=5,
    )

    service = McpHubGovernancePackDistributionService(trust_service=trust_service)
    calls: list[str] = []

    async def _fake_to_thread(func: Any, /, *args: Any, **kwargs: Any) -> Any:
        calls.append(getattr(func, "__name__", "<anonymous>"))
        return func(*args, **kwargs)

    monkeypatch.setattr(distribution_module.asyncio, "to_thread", _fake_to_thread)

    resolved = await service.resolve_local_path(str(pack_path))

    assert resolved.manifest.pack_id == "researcher-pack"
    assert calls == ["_load_local_pack_sync"]


@pytest.mark.asyncio
async def test_distribution_service_rejects_local_pack_outside_allowlist(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
        McpHubGovernancePackTrustService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)
    trust_service = McpHubGovernancePackTrustService(repo=repo)
    allowed_root = tmp_path / "allowed"
    outside_root = tmp_path / "outside"
    allowed_root.mkdir()
    outside_root.mkdir()
    pack_path = outside_root / "researcher-pack"
    shutil.copytree(_fixture_pack_path(), pack_path)
    await trust_service.update_policy(
        {
            "allow_local_path_sources": True,
            "allowed_local_roots": [str(allowed_root)],
        },
        actor_id=5,
    )

    service = McpHubGovernancePackDistributionService(trust_service=trust_service)
    with pytest.raises(ValueError, match="path_not_allowed"):
        await service.resolve_local_path(str(pack_path))


@pytest.mark.asyncio
async def test_distribution_service_resolves_git_source_to_exact_commit_and_digest(
    tmp_path: Path,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )

    repo_url, commit = _init_git_pack_repo(tmp_path)
    trust_service = _FakeGitTrustService()
    service = McpHubGovernancePackDistributionService(trust_service=trust_service)

    resolved = await service.resolve_git_source(
        repo_url,
        ref="v1.0.0",
        ref_kind="tag",
        subpath="packs/researcher",
    )

    assert resolved.manifest.pack_id == "researcher-pack"
    assert resolved.source_type == "git"
    assert resolved.source_location == repo_url
    assert resolved.source_ref_requested == "v1.0.0"
    assert resolved.source_ref_kind == "tag"
    assert resolved.source_subpath == "packs/researcher"
    assert resolved.source_commit_resolved == commit
    assert resolved.source_path is None
    assert resolved.pack_content_digest


@pytest.mark.asyncio
async def test_distribution_service_checkout_git_source_uses_thread_offload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services import mcp_hub_governance_pack_distribution_service as distribution_module
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )

    service = McpHubGovernancePackDistributionService(trust_service=_FakeGitTrustService())
    calls: list[str] = []

    async def _fake_to_thread(func: Any, /, *args: Any, **kwargs: Any) -> Any:
        calls.append(getattr(func, "__name__", "<anonymous>"))
        return func(*args, **kwargs)

    def _fake_checkout_sync(
        *,
        repo_url: str,
        ref: str | None,
        ref_kind: str,
        checkout_root: Path,
    ) -> str:
        assert repo_url == "https://example.com/researcher-pack.git"
        assert ref == "main"
        assert ref_kind == "branch"
        assert checkout_root == tmp_path / "checkout"
        return "abc123"

    monkeypatch.setattr(distribution_module.asyncio, "to_thread", _fake_to_thread)
    monkeypatch.setattr(service, "_checkout_git_source_sync", _fake_checkout_sync)

    commit = await service._checkout_git_source(
        repo_url="https://example.com/researcher-pack.git",
        ref="main",
        ref_kind="branch",
        checkout_root=tmp_path / "checkout",
    )

    assert commit == "abc123"
    assert calls == ["_fake_checkout_sync"]


@pytest.mark.asyncio
async def test_distribution_service_verify_git_revision_uses_thread_offload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services import mcp_hub_governance_pack_distribution_service as distribution_module
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )

    service = McpHubGovernancePackDistributionService(trust_service=_FakeGitTrustService())
    calls: list[str] = []

    async def _fake_to_thread(func: Any, /, *args: Any, **kwargs: Any) -> Any:
        calls.append(getattr(func, "__name__", "<anonymous>"))
        return func(*args, **kwargs)

    def _fake_verify_sync(
        *,
        checkout_root: Path,
        ref: str | None,
        ref_kind: str,
        commit: str,
        trusted_git_key_fingerprints: list[str] | None = None,
    ) -> bool:
        assert checkout_root == tmp_path / "checkout"
        assert ref == "v1.0.0"
        assert ref_kind == "tag"
        assert commit == "abc123"
        assert trusted_git_key_fingerprints == ["ABCD1234"]
        return True

    monkeypatch.setattr(distribution_module.asyncio, "to_thread", _fake_to_thread)
    monkeypatch.setattr(service, "_verify_git_revision_sync", _fake_verify_sync)

    verified = await service._verify_git_revision(
        checkout_root=tmp_path / "checkout",
        ref="v1.0.0",
        ref_kind="tag",
        commit="abc123",
        trusted_git_key_fingerprints=["ABCD1234"],
    )

    assert verified is True
    assert calls == ["_fake_verify_sync"]


@pytest.mark.asyncio
async def test_distribution_service_uses_canonicalized_repo_for_trust_matching(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )
    from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
        McpHubGovernancePackTrustService,
    )

    repo = await _make_repo(tmp_path, monkeypatch)
    trust_service = McpHubGovernancePackTrustService(repo=repo)
    await trust_service.update_policy(
        {
            "allow_git_sources": True,
            "allowed_git_hosts": ["github.com"],
            "allowed_git_repositories": ["github.com/example/researcher-pack"],
            "allowed_git_ref_kinds": ["tag"],
        },
        actor_id=7,
    )

    checkout_root = tmp_path / "checkout"
    shutil.copytree(_fixture_pack_path(), checkout_root)
    service = McpHubGovernancePackDistributionService(trust_service=trust_service)

    async def _fake_checkout(*args: Any, **kwargs: Any) -> str:
        requested_checkout_root = Path(kwargs["checkout_root"])
        shutil.copytree(checkout_root, requested_checkout_root)
        return "abc123"

    monkeypatch.setattr(service, "_checkout_git_source", _fake_checkout)

    resolved = await service.resolve_git_source(
        "git@github.com:example/researcher-pack.git",
        ref="v1.0.0",
        ref_kind="tag",
        subpath=None,
    )

    assert resolved.source_location == "git@github.com:example/researcher-pack.git"
    assert resolved.source_ref_kind == "tag"
    assert resolved.source_commit_resolved == "abc123"


@pytest.mark.asyncio
async def test_distribution_service_rejects_git_subpath_escape(
    tmp_path: Path,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )

    repo_url, _commit = _init_git_pack_repo(tmp_path)
    service = McpHubGovernancePackDistributionService(trust_service=_FakeGitTrustService())

    with pytest.raises(ValueError, match="subpath"):
        await service.resolve_git_source(
            repo_url,
            ref="v1.0.0",
            ref_kind="tag",
            subpath="../escape",
        )


@pytest.mark.asyncio
async def test_distribution_service_rejects_git_symlink_subpath_escape(
    tmp_path: Path,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )

    repo_url, _commit = _init_git_pack_repo(tmp_path)
    repo_root = Path(repo_url.removeprefix("file://"))
    link_parent = repo_root / "packs"
    link_parent.mkdir(exist_ok=True)
    (link_parent / "escape").symlink_to("../../outside-pack")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "Add symlink escape"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    service = McpHubGovernancePackDistributionService(trust_service=_FakeGitTrustService())
    with pytest.raises(ValueError, match="repository root"):
        await service.resolve_git_source(
            repo_url,
            ref=None,
            ref_kind="branch",
            subpath="packs/escape",
        )


@pytest.mark.asyncio
async def test_distribution_service_rejects_git_urls_with_embedded_credentials() -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )

    service = McpHubGovernancePackDistributionService(trust_service=_FakeGitTrustService())

    with pytest.raises(ValueError, match="credentials"):
        await service.resolve_git_source(
            "https://token@example@example.com/researcher-pack.git",
            ref="main",
            ref_kind="branch",
            subpath=None,
        )


@pytest.mark.asyncio
async def test_distribution_service_requires_git_signature_verification_when_configured(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )

    repo_url, _commit = _init_git_pack_repo(tmp_path)
    trust_service = _FakeGitTrustService(verification_required=True)
    service = McpHubGovernancePackDistributionService(trust_service=trust_service)

    async def _fake_verify(*args: Any, **kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(service, "_verify_git_revision", _fake_verify)

    with pytest.raises(ValueError, match="verification"):
        await service.resolve_git_source(
            repo_url,
            ref="v1.0.0",
            ref_kind="tag",
            subpath="packs/researcher",
        )


@pytest.mark.asyncio
async def test_distribution_service_passes_trusted_key_fingerprints_to_verifier(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )

    repo_url, commit = _init_git_pack_repo(tmp_path)
    trust_service = _FakeGitTrustService(
        verification_required=True,
        trusted_git_key_fingerprints=["ABCD1234"],
    )
    service = McpHubGovernancePackDistributionService(trust_service=trust_service)

    async def _fake_verify(*args: Any, **kwargs: Any) -> bool:
        assert kwargs["trusted_git_key_fingerprints"] == ["ABCD1234"]
        return True

    monkeypatch.setattr(service, "_verify_git_revision", _fake_verify)

    resolved = await service.resolve_git_source(
        repo_url,
        ref="v1.0.0",
        ref_kind="tag",
        subpath="packs/researcher",
    )

    assert resolved.source_commit_resolved == commit


@pytest.mark.asyncio
async def test_distribution_service_rejects_option_like_git_refs(
    tmp_path: Path,
) -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_distribution_service import (
        McpHubGovernancePackDistributionService,
    )

    repo_url, _commit = _init_git_pack_repo(tmp_path)
    service = McpHubGovernancePackDistributionService(trust_service=_FakeGitTrustService())

    with pytest.raises(ValueError, match="must not start"):
        await service.resolve_git_source(
            repo_url,
            ref="--help",
            ref_kind="tag",
            subpath="packs/researcher",
        )
