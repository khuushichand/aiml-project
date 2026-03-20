from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import mcp_hub_management
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services.mcp_hub_governance_pack_service import (
    GovernancePackAlreadyExistsError,
    GovernancePackUpgradeConflictError,
    GovernancePackUpgradeStaleError,
)


def _make_principal(
    *,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=7,
        api_key_id=None,
        subject="7",
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=permissions or [],
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )


class _FakePolicyService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.permission_profiles = [
            {
                "id": 5,
                "name": "Imported Researcher",
                "description": None,
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "mode": "preset",
                "path_scope_object_id": None,
                "policy_document": {"capabilities": ["filesystem.read"]},
                "is_active": True,
                "is_immutable": False,
                "created_by": 7,
                "updated_by": 7,
                "created_at": now,
                "updated_at": now,
            }
        ]

    async def get_permission_profile(self, profile_id: int):
        for profile in self.permission_profiles:
            if int(profile["id"]) == int(profile_id):
                return dict(profile)
        return None

    async def update_permission_profile(self, profile_id: int, **kwargs):
        profile = await self.get_permission_profile(profile_id)
        if profile is None:
            return None
        profile.update(kwargs)
        self.permission_profiles = [profile]
        return profile


class _FakeGovernancePackService:
    def __init__(self) -> None:
        self.dry_run_calls: list[dict] = []
        self.import_calls: list[dict] = []
        self.upgrade_dry_run_calls: list[dict] = []
        self.upgrade_execute_calls: list[dict] = []
        self.report = {
            "manifest": {
                "pack_id": "researcher-pack",
                "pack_version": "1.0.0",
                "title": "Researcher Pack",
                "description": "Portable research governance pack",
            },
            "digest": "a" * 64,
            "resolved_capabilities": ["filesystem.read", "tool.invoke.research"],
            "unresolved_capabilities": [],
            "capability_mapping_summary": [
                {
                    "capability_name": "tool.invoke.research",
                    "mapping_id": "research.global",
                    "mapping_scope_type": "global",
                    "mapping_scope_id": None,
                    "resolved_effects": {"allowed_tools": ["web.search"]},
                    "supported_environment_requirements": ["workspace_bounded_read"],
                    "unsupported_environment_requirements": [],
                }
            ],
            "supported_environment_requirements": ["workspace_bounded_read"],
            "unsupported_environment_requirements": [],
            "warnings": [],
            "blocked_objects": [],
            "verdict": "importable",
        }
        self.inventory = [
            {
                "id": 81,
                "pack_id": "researcher-pack",
                "pack_version": "1.0.0",
                "title": "Researcher Pack",
                "description": "Portable research governance pack",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "bundle_digest": "a" * 64,
                "source_type": "git",
                "source_location": "https://github.com/example/researcher-pack.git",
                "source_ref_requested": "main",
                "source_subpath": "packs/researcher",
                "source_commit_resolved": "abc123",
                "pack_content_digest": "b" * 64,
                "source_verified": True,
                "source_verification_mode": "git-commit",
                "source_fetched_at": datetime.now(timezone.utc).isoformat(),
                "fetched_by": 7,
                "manifest": {
                    "pack_id": "researcher-pack",
                    "pack_version": "1.0.0",
                    "title": "Researcher Pack",
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
        self.detail = {
            **self.inventory[0],
            "normalized_ir": {
                "manifest": self.inventory[0]["manifest"],
                "data": {
                    "profiles": [{"profile_id": "researcher.profile"}],
                    "approvals": [{"approval_template_id": "researcher.ask"}],
                    "personas": [{"persona_template_id": "researcher.persona"}],
                    "assignments": [{"assignment_template_id": "researcher.default"}],
                },
            },
            "imported_objects": [
                {
                    "object_type": "permission_profile",
                    "object_id": "5",
                    "source_object_id": "researcher.profile",
                },
                {
                    "object_type": "policy_assignment",
                    "object_id": "11",
                    "source_object_id": "researcher.default",
                },
            ],
        }
        self.upgrade_plan = {
            "source_governance_pack_id": 81,
            "source_manifest": self.inventory[0]["manifest"],
            "target_manifest": {
                "pack_id": "researcher-pack",
                "pack_version": "1.1.0",
                "title": "Researcher Pack",
            },
            "object_diff": [
                {
                    "object_type": "permission_profile",
                    "source_object_id": "researcher.profile",
                    "change_type": "modified",
                    "previous_digest": "1" * 64,
                    "next_digest": "2" * 64,
                }
            ],
            "dependency_impact": [
                {
                    "object_type": "permission_profile",
                    "source_object_id": "researcher.profile",
                    "change_type": "modified",
                    "impact": "behavioral_conflict",
                    "dependent_type": "policy_assignment",
                    "dependent_id": 91,
                    "reference_field": "profile_id",
                    "target_type": "permission_profile",
                    "target_id": "researcher.profile",
                }
            ],
            "structural_conflicts": [],
            "behavioral_conflicts": [],
            "warnings": [],
            "planner_inputs_fingerprint": "plan-fingerprint",
            "adapter_state_fingerprint": "adapter-fingerprint",
            "upgradeable": True,
        }
        self.upgrade_result = {
            "upgrade_id": 12,
            "source_governance_pack_id": 81,
            "target_governance_pack_id": 82,
            "from_pack_version": "1.0.0",
            "to_pack_version": "1.1.0",
            "planner_inputs_fingerprint": "plan-fingerprint",
            "adapter_state_fingerprint": "adapter-fingerprint",
            "imported_object_ids": {
                "approval_policies": [31],
                "permission_profiles": [41],
                "policy_assignments": [51],
            },
            "imported_object_counts": {
                "approval_policies": 1,
                "permission_profiles": 1,
                "policy_assignments": 1,
            },
        }
        self.upgrade_history = [
            {
                "id": 12,
                "pack_id": "researcher-pack",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "from_governance_pack_id": 81,
                "to_governance_pack_id": 82,
                "from_pack_version": "1.0.0",
                "to_pack_version": "1.1.0",
                "status": "executed",
                "planned_by": 7,
                "executed_by": 7,
                "planner_inputs_fingerprint": "plan-fingerprint",
                "adapter_state_fingerprint": "adapter-fingerprint",
                "plan_summary": {
                    "object_diff_count": 1,
                    "dependency_impact_count": 1,
                },
                "accepted_resolutions": {},
                "failure_summary": None,
                "planned_at": datetime.now(timezone.utc).isoformat(),
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

    async def dry_run_pack_document(
        self,
        *,
        document: dict[str, object],
        owner_scope_type: str,
        owner_scope_id: int | None,
    ) -> dict[str, object]:
        self.dry_run_calls.append(
            {
                "document": dict(document),
                "owner_scope_type": owner_scope_type,
                "owner_scope_id": owner_scope_id,
            }
        )
        return dict(self.report)

    async def import_pack_document(
        self,
        *,
        document: dict[str, object],
        owner_scope_type: str,
        owner_scope_id: int | None,
        actor_id: int | None,
        source_metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.import_calls.append(
            {
                "document": dict(document),
                "owner_scope_type": owner_scope_type,
                "owner_scope_id": owner_scope_id,
                "actor_id": actor_id,
                "source_metadata": dict(source_metadata or {}),
            }
        )
        return {
            "governance_pack_id": 81,
            "imported_object_counts": {
                "approval_policies": 1,
                "permission_profiles": 1,
                "policy_assignments": 1,
            },
            "blocked_objects": [],
            "report": dict(self.report),
        }

    async def list_governance_packs(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, object]]:
        del owner_scope_type, owner_scope_id
        return list(self.inventory)

    async def get_governance_pack_detail(self, governance_pack_id: int) -> dict[str, object] | None:
        if int(governance_pack_id) == 81:
            return dict(self.detail)
        return None

    async def dry_run_upgrade_document(
        self,
        *,
        source_governance_pack_id: int,
        document: dict[str, object],
        owner_scope_type: str,
        owner_scope_id: int | None,
    ) -> dict[str, object]:
        self.upgrade_dry_run_calls.append(
            {
                "source_governance_pack_id": source_governance_pack_id,
                "document": dict(document),
                "owner_scope_type": owner_scope_type,
                "owner_scope_id": owner_scope_id,
            }
        )
        return dict(self.upgrade_plan)

    async def execute_upgrade_document(
        self,
        *,
        source_governance_pack_id: int,
        document: dict[str, object],
        owner_scope_type: str,
        owner_scope_id: int | None,
        actor_id: int | None,
        planner_inputs_fingerprint: str,
        adapter_state_fingerprint: str,
    ) -> dict[str, object]:
        self.upgrade_execute_calls.append(
            {
                "source_governance_pack_id": source_governance_pack_id,
                "document": dict(document),
                "owner_scope_type": owner_scope_type,
                "owner_scope_id": owner_scope_id,
                "actor_id": actor_id,
                "planner_inputs_fingerprint": planner_inputs_fingerprint,
                "adapter_state_fingerprint": adapter_state_fingerprint,
            }
        )
        return dict(self.upgrade_result)

    async def list_governance_pack_upgrade_history(
        self,
        governance_pack_id: int,
    ) -> list[dict[str, object]]:
        assert governance_pack_id == 81
        return list(self.upgrade_history)


class _FakeGovernancePackTrustService:
    def __init__(self) -> None:
        self.policy = {
            "allow_local_path_sources": True,
            "allowed_local_roots": ["/srv/packs"],
            "allow_git_sources": True,
            "allowed_git_hosts": ["github.com"],
            "allowed_git_repositories": ["github.com/example/researcher-pack"],
            "allowed_git_ref_kinds": ["commit", "tag"],
            "require_git_signature_verification": True,
            "trusted_signers": [
                {
                    "fingerprint": "ABCD1234",
                    "display_name": "Release Bot",
                    "repo_bindings": ["github.com/example/researcher-pack"],
                    "status": "active",
                }
            ],
        }
        self.update_calls: list[dict[str, object]] = []

    async def get_policy(self) -> dict[str, object]:
        from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
            _stable_policy_fingerprint,
        )

        payload = dict(self.policy)
        payload["policy_fingerprint"] = _stable_policy_fingerprint(payload)
        return payload

    async def update_policy(self, policy: dict[str, object], *, actor_id: int | None) -> dict[str, object]:
        from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
            GovernancePackTrustPolicyStaleError,
            _normalize_repo_binding,
            _stable_policy_fingerprint,
        )

        requested_fingerprint = str(policy.get("policy_fingerprint") or "").strip()
        current_fingerprint = _stable_policy_fingerprint(self.policy)
        if not requested_fingerprint:
            raise GovernancePackTrustPolicyStaleError("policy_fingerprint is required for trust policy updates")
        if requested_fingerprint != current_fingerprint:
            raise GovernancePackTrustPolicyStaleError("stale governance pack trust policy write")
        self.update_calls.append({"policy": dict(policy), "actor_id": actor_id})
        self.policy = {
            **self.policy,
            **dict(policy),
        }
        self.policy.pop("policy_fingerprint", None)
        allowed_repositories = [
            str(entry).strip()
            for entry in self.policy.get("allowed_git_repositories", [])
            if str(entry).strip()
        ]
        normalized_signers: list[dict[str, object]] = []
        seen_fingerprints: set[str] = set()
        for signer in self.policy.get("trusted_signers", []):
            fingerprint = str(signer.get("fingerprint") or "").strip().upper()
            if not fingerprint:
                continue
            repo_bindings: list[str] = []
            seen_bindings: set[str] = set()
            for binding in signer.get("repo_bindings", []):
                cleaned = str(binding or "").strip()
                if not cleaned:
                    continue
                normalized_binding = _normalize_repo_binding(cleaned)
                if normalized_binding in seen_bindings:
                    continue
                seen_bindings.add(normalized_binding)
                repo_bindings.append(normalized_binding)
            normalized_signers.append(
                {
                    "fingerprint": fingerprint,
                    "display_name": signer.get("display_name"),
                    "repo_bindings": repo_bindings,
                    "status": str(signer.get("status") or "active").strip().lower(),
                }
            )
            seen_fingerprints.add(fingerprint)
        for fingerprint in policy.get("trusted_git_key_fingerprints", []):
            cleaned = str(fingerprint or "").strip().upper()
            if not cleaned or cleaned in seen_fingerprints:
                continue
            normalized_signers.append(
                {
                    "fingerprint": cleaned,
                    "display_name": None,
                    "repo_bindings": list(allowed_repositories),
                    "status": "active",
                }
            )
            seen_fingerprints.add(cleaned)
        self.policy["trusted_signers"] = normalized_signers
        self.policy.pop("trusted_git_key_fingerprints", None)
        payload = dict(self.policy)
        payload["policy_fingerprint"] = _stable_policy_fingerprint(payload)
        return payload


class _FakeGovernancePackDistributionService:
    def __init__(self) -> None:
        self.prepare_calls: list[dict[str, object]] = []
        self.update_check_calls: list[int] = []
        self.prepare_upgrade_calls: list[dict[str, object]] = []
        self.validate_upgrade_calls: list[dict[str, object]] = []
        self.load_calls: list[dict[str, object]] = []
        self.candidate = {
            "id": 501,
            "source_type": "local_path",
            "source_location": "/srv/packs/researcher-pack",
            "source_ref_requested": None,
            "source_ref_kind": None,
            "source_subpath": None,
            "source_commit_resolved": None,
            "pack_content_digest": "c" * 64,
            "source_verified": None,
            "source_verification_mode": None,
            "source_fetched_at": datetime.now(timezone.utc).isoformat(),
            "fetched_by": 7,
        }
        self.upgrade_candidate = {
            "id": 502,
            "source_type": "git",
            "source_location": "https://github.com/example/researcher-pack.git",
            "source_ref_requested": "main",
            "source_ref_kind": "branch",
            "source_subpath": "packs/researcher",
            "source_commit_resolved": "def456",
            "pack_content_digest": "d" * 64,
            "source_verified": True,
            "source_verification_mode": "git_signature",
            "source_fetched_at": datetime.now(timezone.utc).isoformat(),
            "fetched_by": 7
        }
        self.update_check = {
            "governance_pack_id": 81,
            "status": "newer_version_available",
            "installed_manifest": {
                "pack_id": "researcher-pack",
                "pack_version": "1.0.0",
                "title": "Researcher Pack"
            },
            "candidate_manifest": {
                "pack_id": "researcher-pack",
                "pack_version": "1.1.0",
                "title": "Researcher Pack"
            },
            "source_commit_resolved": "def456",
            "pack_content_digest": "d" * 64
        }

    async def prepare_source_candidate(
        self,
        *,
        source: dict[str, object],
        actor_id: int | None,
    ) -> dict[str, object]:
        self.prepare_calls.append({"source": dict(source), "actor_id": actor_id})
        return {
            "candidate": dict(self.candidate),
            "manifest": dict(_minimal_pack_document()["manifest"]),
        }

    async def load_prepared_candidate(
        self,
        candidate_id: int,
        *,
        actor_id: int | None = None,
        revalidate_trust: bool = False,
    ) -> dict[str, object]:
        self.load_calls.append(
            {
                "candidate_id": int(candidate_id),
                "actor_id": actor_id,
                "revalidate_trust": revalidate_trust,
            }
        )
        if int(candidate_id) == 501:
            return {
                "candidate": dict(self.candidate),
                "pack_document": _minimal_pack_document()
            }
        assert int(candidate_id) == 502
        upgraded_pack_document = _minimal_pack_document()
        upgraded_pack_document["manifest"]["pack_version"] = "1.1.0"
        return {
            "candidate": dict(self.upgrade_candidate),
            "pack_document": upgraded_pack_document,
        }

    async def check_for_updates(self, governance_pack_id: int) -> dict[str, object]:
        self.update_check_calls.append(int(governance_pack_id))
        return dict(self.update_check)

    async def prepare_upgrade_candidate(
        self,
        *,
        governance_pack_id: int,
        actor_id: int | None,
    ) -> dict[str, object]:
        self.prepare_upgrade_calls.append(
            {"governance_pack_id": int(governance_pack_id), "actor_id": actor_id}
        )
        return {
            "status": "newer_version_available",
            "installed_manifest": dict(self.update_check["installed_manifest"]),
            "candidate_manifest": dict(self.update_check["candidate_manifest"]),
            "candidate": dict(self.upgrade_candidate),
            "manifest": dict(self.update_check["candidate_manifest"]),
        }

    async def validate_prepared_upgrade_candidate(
        self,
        *,
        governance_pack_id: int,
        candidate_id: int,
        actor_id: int | None = None,
    ) -> dict[str, object]:
        self.validate_upgrade_calls.append(
            {
                "governance_pack_id": int(governance_pack_id),
                "candidate_id": int(candidate_id),
                "actor_id": actor_id,
            }
        )
        return await self.load_prepared_candidate(
            candidate_id,
            actor_id=actor_id,
            revalidate_trust=True,
        )


def _build_app(
    principal: AuthPrincipal,
    *,
    policy_service: _FakePolicyService | None = None,
    governance_service: _FakeGovernancePackService | None = None,
    trust_service: _FakeGovernancePackTrustService | None = None,
    distribution_service: _FakeGovernancePackDistributionService | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(mcp_hub_management.router, prefix="/api/v1")

    async def _fake_get_auth_principal(_request: Request) -> AuthPrincipal:  # type: ignore[override]
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_service] = (
        lambda: policy_service or _FakePolicyService()
    )
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_governance_pack_service] = (
        lambda: governance_service or _FakeGovernancePackService()
    )
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_governance_pack_trust_service] = (
        lambda: trust_service or _FakeGovernancePackTrustService()
    )
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_governance_pack_distribution_service] = (
        lambda: distribution_service or _FakeGovernancePackDistributionService()
    )
    return app


def _minimal_pack_document() -> dict:
    return {
        "manifest": {
            "pack_id": "researcher-pack",
            "pack_version": "1.0.0",
            "pack_schema_version": 1,
            "capability_taxonomy_version": 1,
            "adapter_contract_version": 1,
            "title": "Researcher Pack",
            "description": "Portable research governance pack",
            "authors": ["codex"],
            "compatible_runtime_targets": ["tldw"],
        },
        "profiles": [
            {
                "profile_id": "researcher.profile",
                "name": "Researcher",
                "capabilities": {"allow": ["filesystem.read", "tool.invoke.research"]},
                "approval_intent": "ask",
                "environment_requirements": ["workspace_bounded_read"],
            }
        ],
        "approvals": [
            {
                "approval_template_id": "researcher.ask",
                "name": "Ask Before Use",
                "mode": "ask",
            }
        ],
        "personas": [
            {
                "persona_template_id": "researcher.persona",
                "name": "Research Companion",
                "capability_profile_id": "researcher.profile",
                "approval_template_id": "researcher.ask",
            }
        ],
        "assignments": [
            {
                "assignment_template_id": "researcher.default",
                "target_type": "default",
                "capability_profile_id": "researcher.profile",
                "approval_template_id": "researcher.ask",
            }
        ],
    }


def test_governance_pack_dry_run_returns_compatibility_report() -> None:
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"])
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/dry-run",
            json={
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "pack": _minimal_pack_document(),
            },
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["report"]["resolved_capabilities"] == [
        "filesystem.read",
        "tool.invoke.research",
    ]
    assert payload["report"]["unresolved_capabilities"] == []
    assert payload["report"]["capability_mapping_summary"][0]["mapping_id"] == "research.global"
    assert payload["report"]["verdict"] == "importable"


def test_governance_pack_import_returns_import_result() -> None:
    governance_service = _FakeGovernancePackService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=governance_service,
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/import",
            json={
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "pack": _minimal_pack_document(),
            },
        )

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["governance_pack_id"] == 81
    assert payload["imported_object_counts"]["permission_profiles"] == 1
    assert governance_service.import_calls


def test_governance_pack_source_prepare_dry_run_and_import_round_trip() -> None:
    governance_service = _FakeGovernancePackService()
    distribution_service = _FakeGovernancePackDistributionService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=governance_service,
        distribution_service=distribution_service,
    )

    with TestClient(app) as client:
        prepare_resp = client.post(
            "/api/v1/mcp/hub/governance-packs/source/prepare",
            json={
                "source": {
                    "source_type": "local_path",
                    "local_path": "/srv/packs/researcher-pack",
                }
            },
        )
        dry_run_resp = client.post(
            "/api/v1/mcp/hub/governance-packs/source/dry-run",
            json={
                "owner_scope_type": "user",
                "candidate_id": 501,
            },
        )
        import_resp = client.post(
            "/api/v1/mcp/hub/governance-packs/source/import",
            json={
                "owner_scope_type": "user",
                "candidate_id": 501,
            },
        )

    assert prepare_resp.status_code == 201
    assert prepare_resp.json()["candidate"]["source_location"] == "/srv/packs/researcher-pack"

    assert dry_run_resp.status_code == 200
    assert dry_run_resp.json()["report"]["manifest"]["pack_id"] == "researcher-pack"

    assert import_resp.status_code == 201
    assert import_resp.json()["governance_pack_id"] == 81
    assert distribution_service.prepare_calls[0]["actor_id"] == 7
    assert distribution_service.load_calls == [
        {"candidate_id": 501, "actor_id": 7, "revalidate_trust": True},
        {"candidate_id": 501, "actor_id": 7, "revalidate_trust": True},
    ]
    assert governance_service.import_calls[0]["source_metadata"]["source_location"] == "/srv/packs/researcher-pack"


def test_governance_pack_git_update_check_and_candidate_upgrade_round_trip() -> None:
    governance_service = _FakeGovernancePackService()
    distribution_service = _FakeGovernancePackDistributionService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=governance_service,
        distribution_service=distribution_service,
    )

    with TestClient(app) as client:
        check_resp = client.post("/api/v1/mcp/hub/governance-packs/81/check-updates")
        prepare_resp = client.post("/api/v1/mcp/hub/governance-packs/81/prepare-upgrade-candidate")
        dry_run_resp = client.post(
            "/api/v1/mcp/hub/governance-packs/source/dry-run-upgrade",
            json={
                "source_governance_pack_id": 81,
                "owner_scope_type": "user",
                "candidate_id": 502,
            },
        )
        execute_resp = client.post(
            "/api/v1/mcp/hub/governance-packs/source/execute-upgrade",
            json={
                "source_governance_pack_id": 81,
                "owner_scope_type": "user",
                "candidate_id": 502,
                "planner_inputs_fingerprint": "plan-fingerprint",
                "adapter_state_fingerprint": "adapter-fingerprint",
            },
        )

    assert check_resp.status_code == 200
    assert check_resp.json()["status"] == "newer_version_available"
    assert prepare_resp.status_code == 201
    assert prepare_resp.json()["candidate"]["source_commit_resolved"] == "def456"

    assert dry_run_resp.status_code == 200
    assert dry_run_resp.json()["plan"]["target_manifest"]["pack_version"] == "1.1.0"
    assert execute_resp.status_code == 200
    assert execute_resp.json()["target_governance_pack_id"] == 82

    assert distribution_service.update_check_calls == [81]
    assert distribution_service.prepare_upgrade_calls == [{"governance_pack_id": 81, "actor_id": 7}]
    assert distribution_service.validate_upgrade_calls == [
        {"governance_pack_id": 81, "candidate_id": 502, "actor_id": 7}
    ]
    assert governance_service.upgrade_dry_run_calls[0]["source_governance_pack_id"] == 81
    assert governance_service.upgrade_execute_calls[0]["source_governance_pack_id"] == 81


def test_governance_pack_source_execute_upgrade_rejects_stale_candidate() -> None:
    class _StaleCandidateDistributionService(_FakeGovernancePackDistributionService):
        async def validate_prepared_upgrade_candidate(
            self,
            *,
            governance_pack_id: int,
            candidate_id: int,
            actor_id: int | None = None,
        ) -> dict[str, object]:
            del governance_pack_id, candidate_id, actor_id
            raise ValueError("Prepared governance-pack upgrade candidate is stale")

    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=_FakeGovernancePackService(),
        distribution_service=_StaleCandidateDistributionService(),
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/source/execute-upgrade",
            json={
                "source_governance_pack_id": 81,
                "owner_scope_type": "user",
                "candidate_id": 502,
                "planner_inputs_fingerprint": "plan-fingerprint",
                "adapter_state_fingerprint": "adapter-fingerprint",
            },
        )

    assert resp.status_code == 400
    assert "stale" in resp.json()["detail"].lower()


def test_governance_pack_upgrade_dry_run_returns_plan() -> None:
    governance_service = _FakeGovernancePackService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=governance_service,
    )

    upgraded_pack = _minimal_pack_document()
    upgraded_pack["manifest"]["pack_version"] = "1.1.0"

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/dry-run-upgrade",
            json={
                "source_governance_pack_id": 81,
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "pack": upgraded_pack,
            },
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["plan"]["source_governance_pack_id"] == 81
    assert payload["plan"]["upgradeable"] is True
    assert governance_service.upgrade_dry_run_calls[0]["owner_scope_id"] == 7


def test_governance_pack_execute_upgrade_returns_result() -> None:
    governance_service = _FakeGovernancePackService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=governance_service,
    )

    upgraded_pack = _minimal_pack_document()
    upgraded_pack["manifest"]["pack_version"] = "1.1.0"

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/execute-upgrade",
            json={
                "source_governance_pack_id": 81,
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "planner_inputs_fingerprint": "plan-fingerprint",
                "adapter_state_fingerprint": "adapter-fingerprint",
                "pack": upgraded_pack,
            },
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["upgrade_id"] == 12
    assert payload["target_governance_pack_id"] == 82
    assert governance_service.upgrade_execute_calls[0]["actor_id"] == 7


def test_governance_pack_execute_upgrade_requires_grant_authority() -> None:
    governance_service = _FakeGovernancePackService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read"]),
        governance_service=governance_service,
    )

    upgraded_pack = _minimal_pack_document()
    upgraded_pack["manifest"]["pack_version"] = "1.1.0"

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/execute-upgrade",
            json={
                "source_governance_pack_id": 81,
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "planner_inputs_fingerprint": "plan-fingerprint",
                "adapter_state_fingerprint": "adapter-fingerprint",
                "pack": upgraded_pack,
            },
        )

    assert resp.status_code == 403
    assert "grant.tool.invoke" in resp.json()["detail"]
    assert governance_service.upgrade_execute_calls == []


def test_governance_pack_execute_upgrade_returns_conflict_for_blocking_plan() -> None:
    class _ConflictGovernancePackService(_FakeGovernancePackService):
        async def execute_upgrade_document(
            self,
            *,
            source_governance_pack_id: int,
            document: dict[str, object],
            owner_scope_type: str,
            owner_scope_id: int | None,
            actor_id: int | None,
            planner_inputs_fingerprint: str,
            adapter_state_fingerprint: str,
        ) -> dict[str, object]:
            del (
                source_governance_pack_id,
                document,
                owner_scope_type,
                owner_scope_id,
                actor_id,
                planner_inputs_fingerprint,
                adapter_state_fingerprint,
            )
            raise GovernancePackUpgradeConflictError("blocking conflicts")

    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=_ConflictGovernancePackService(),
    )

    upgraded_pack = _minimal_pack_document()
    upgraded_pack["manifest"]["pack_version"] = "1.1.0"

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/execute-upgrade",
            json={
                "source_governance_pack_id": 81,
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "planner_inputs_fingerprint": "plan-fingerprint",
                "adapter_state_fingerprint": "adapter-fingerprint",
                "pack": upgraded_pack,
            },
        )

    assert resp.status_code == 409
    assert "blocking conflicts" in resp.json()["detail"]


def test_governance_pack_execute_upgrade_returns_conflict_for_stale_plan() -> None:
    class _StaleGovernancePackService(_FakeGovernancePackService):
        async def execute_upgrade_document(
            self,
            *,
            source_governance_pack_id: int,
            document: dict[str, object],
            owner_scope_type: str,
            owner_scope_id: int | None,
            actor_id: int | None,
            planner_inputs_fingerprint: str,
            adapter_state_fingerprint: str,
        ) -> dict[str, object]:
            del (
                source_governance_pack_id,
                document,
                owner_scope_type,
                owner_scope_id,
                actor_id,
                planner_inputs_fingerprint,
                adapter_state_fingerprint,
            )
            raise GovernancePackUpgradeStaleError("stale plan")

    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=_StaleGovernancePackService(),
    )

    upgraded_pack = _minimal_pack_document()
    upgraded_pack["manifest"]["pack_version"] = "1.1.0"

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/execute-upgrade",
            json={
                "source_governance_pack_id": 81,
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "planner_inputs_fingerprint": "plan-fingerprint",
                "adapter_state_fingerprint": "adapter-fingerprint",
                "pack": upgraded_pack,
            },
        )

    assert resp.status_code == 409
    assert "stale plan" in resp.json()["detail"]


def test_governance_pack_upgrade_history_returns_lineage() -> None:
    governance_service = _FakeGovernancePackService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=governance_service,
    )

    with TestClient(app) as client:
        resp = client.get("/api/v1/mcp/hub/governance-packs/81/upgrade-history")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload[0]["from_pack_version"] == "1.0.0"
    assert payload[0]["to_pack_version"] == "1.1.0"


def test_governance_pack_dry_run_defaults_user_scope_id_from_principal() -> None:
    governance_service = _FakeGovernancePackService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=governance_service,
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/dry-run",
            json={
                "owner_scope_type": "user",
                "pack": _minimal_pack_document(),
            },
        )

    assert resp.status_code == 200
    assert governance_service.dry_run_calls[0]["owner_scope_id"] == 7


def test_governance_pack_import_requires_grant_authority_for_portable_tool_capability() -> None:
    governance_service = _FakeGovernancePackService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read"]),
        governance_service=governance_service,
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/import",
            json={
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "pack": _minimal_pack_document(),
            },
        )

    assert resp.status_code == 403
    assert "grant.tool.invoke" in resp.json()["detail"]
    assert governance_service.import_calls == []


def test_governance_pack_import_defaults_user_scope_id_from_principal() -> None:
    governance_service = _FakeGovernancePackService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=governance_service,
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/import",
            json={
                "owner_scope_type": "user",
                "pack": _minimal_pack_document(),
            },
        )

    assert resp.status_code == 201
    assert governance_service.import_calls[0]["owner_scope_id"] == 7


def test_governance_pack_import_returns_conflict_for_duplicate_pack() -> None:
    class _DuplicateGovernancePackService(_FakeGovernancePackService):
        async def import_pack_document(
            self,
            *,
            document: dict[str, object],
            owner_scope_type: str,
            owner_scope_id: int | None,
            actor_id: int | None,
        ) -> dict[str, object]:
            del document, owner_scope_type, owner_scope_id, actor_id
            raise GovernancePackAlreadyExistsError("researcher-pack", "1.0.0", "user", 7)

    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"]),
        governance_service=_DuplicateGovernancePackService(),
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/governance-packs/import",
            json={
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "pack": _minimal_pack_document(),
            },
        )

    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


def test_update_permission_profile_rejects_immutable_pack_managed_base_object() -> None:
    policy_service = _FakePolicyService()
    policy_service.permission_profiles[0]["is_immutable"] = True
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read"]),
        policy_service=policy_service,
    )

    with TestClient(app) as client:
        resp = client.put(
            "/api/v1/mcp/hub/permission-profiles/5",
            json={"description": "locally edited"},
        )

    assert resp.status_code == 400
    assert "immutable" in resp.json()["detail"].lower()


def test_governance_pack_list_and_detail_include_provenance() -> None:
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.filesystem.read", "grant.tool.invoke"])
    )

    with TestClient(app) as client:
        list_resp = client.get("/api/v1/mcp/hub/governance-packs")
        detail_resp = client.get("/api/v1/mcp/hub/governance-packs/81")

    assert list_resp.status_code == 200
    assert list_resp.json()[0]["pack_id"] == "researcher-pack"
    assert list_resp.json()[0]["source_type"] == "git"
    assert list_resp.json()[0]["source_location"] == "https://github.com/example/researcher-pack.git"
    assert list_resp.json()[0]["source_commit_resolved"] == "abc123"
    assert list_resp.json()[0]["pack_content_digest"] == "b" * 64

    assert detail_resp.status_code == 200
    detail_payload = detail_resp.json()
    assert detail_payload["source_type"] == "git"
    assert detail_payload["source_location"] == "https://github.com/example/researcher-pack.git"
    assert detail_payload["source_ref_requested"] == "main"
    assert detail_payload["source_subpath"] == "packs/researcher"
    assert detail_payload["source_commit_resolved"] == "abc123"
    assert detail_payload["pack_content_digest"] == "b" * 64
    assert detail_payload["imported_objects"][0]["source_object_id"] == "researcher.profile"
    assert detail_payload["imported_objects"][1]["object_type"] == "policy_assignment"


def test_governance_pack_trust_policy_round_trip() -> None:
    trust_service = _FakeGovernancePackTrustService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE]),
        trust_service=trust_service,
    )

    with TestClient(app) as client:
        get_resp = client.get("/api/v1/mcp/hub/governance-packs/trust-policy")
        policy_fingerprint = get_resp.json()["policy_fingerprint"]
        put_resp = client.put(
            "/api/v1/mcp/hub/governance-packs/trust-policy",
            json={
                "policy_fingerprint": policy_fingerprint,
                "allow_local_path_sources": True,
                "allowed_local_roots": ["/srv/trusted-packs"],
                "allow_git_sources": True,
                "allowed_git_hosts": ["github.com"],
                "allowed_git_repositories": ["github.com/example/researcher-pack"],
                "allowed_git_ref_kinds": ["tag"],
                "require_git_signature_verification": True,
                "trusted_signers": [
                    {
                        "fingerprint": "efgh5678",
                        "display_name": "Release Bot",
                        "repo_bindings": [
                            "github.com/example/researcher-pack",
                            "github.com/example/",
                        ],
                        "status": "active",
                    }
                ],
                "trusted_git_key_fingerprints": ["ijkl9012"],
            },
        )

    assert get_resp.status_code == 200
    assert get_resp.json()["allowed_local_roots"] == ["/srv/packs"]
    assert "trusted_git_key_fingerprints" not in get_resp.json()

    assert put_resp.status_code == 200
    payload = put_resp.json()
    assert payload["allowed_local_roots"] == ["/srv/trusted-packs"]
    assert payload["allowed_git_ref_kinds"] == ["tag"]
    assert payload["require_git_signature_verification"] is True
    assert payload["trusted_signers"][0]["fingerprint"] == "EFGH5678"
    assert payload["trusted_signers"][0]["display_name"] == "Release Bot"
    assert payload["trusted_signers"][0]["repo_bindings"] == [
        "github.com/example/researcher-pack",
        "github.com/example/",
    ]
    assert payload["trusted_signers"][1]["fingerprint"] == "IJKL9012"
    assert payload["trusted_signers"][1]["repo_bindings"] == [
        "github.com/example/researcher-pack"
    ]
    assert "trusted_git_key_fingerprints" not in payload
    assert trust_service.update_calls[0]["actor_id"] == 7


def test_governance_pack_trust_policy_exposes_fingerprint_and_rejects_stale_write() -> None:
    trust_service = _FakeGovernancePackTrustService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE]),
        trust_service=trust_service,
    )

    with TestClient(app) as client:
        get_resp = client.get("/api/v1/mcp/hub/governance-packs/trust-policy")
        stale_resp = client.put(
            "/api/v1/mcp/hub/governance-packs/trust-policy",
            json={
                "policy_fingerprint": "stale-policy-fingerprint",
                "allow_git_sources": True,
                "allowed_git_hosts": ["github.com"],
                "allowed_git_repositories": ["github.com/example/researcher-pack"],
                "allowed_git_ref_kinds": ["tag"],
                "trusted_signers": [
                    {
                        "fingerprint": "ABCD1234",
                        "repo_bindings": ["github.com/example/researcher-pack"],
                        "status": "active",
                    }
                ],
            },
        )

    assert get_resp.status_code == 200
    assert "policy_fingerprint" in get_resp.json()
    assert get_resp.json()["policy_fingerprint"]
    assert stale_resp.status_code == 409
    assert "stale" in stale_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_governance_pack_trust_service_classifies_signer_result_codes() -> None:
    from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
        McpHubGovernancePackTrustService,
    )

    class _Repo:
        async def get_governance_pack_trust_policy(self) -> dict[str, object]:
            return {
                "policy_document": {
                    "allow_git_sources": True,
                    "allowed_git_hosts": ["github.com"],
                    "allowed_git_repositories": ["github.com/example/researcher-pack"],
                    "allowed_git_ref_kinds": ["tag"],
                    "require_git_signature_verification": True,
                    "trusted_signers": [
                        {
                            "fingerprint": "ABCD1234",
                            "display_name": "Release Bot",
                            "repo_bindings": ["github.com/example/researcher-pack"],
                            "status": "active",
                        },
                        {
                            "fingerprint": "REVOKED1",
                            "display_name": "Old Bot",
                            "repo_bindings": ["github.com/example/researcher-pack"],
                            "status": "revoked",
                        },
                        {
                            "fingerprint": "INACTIVE1",
                            "display_name": "Paused Bot",
                            "repo_bindings": ["github.com/example/researcher-pack"],
                            "status": "inactive",
                        },
                    ],
                }
            }

    service = McpHubGovernancePackTrustService(repo=_Repo())

    trusted = await service.evaluate_signer_for_repository(
        "ABCD1234",
        "github.com/example/researcher-pack",
    )
    not_allowed = await service.evaluate_signer_for_repository(
        "ABCD1234",
        "github.com/other/project",
    )
    revoked = await service.evaluate_signer_for_repository(
        "REVOKED1",
        "github.com/example/researcher-pack",
    )
    inactive = await service.evaluate_signer_for_repository(
        "INACTIVE1",
        "github.com/example/researcher-pack",
    )

    assert trusted["result_code"] == "signer_trusted_for_repo"
    assert not_allowed["result_code"] == "signer_not_allowed_for_repo"
    assert revoked["result_code"] == "signer_revoked"
    assert inactive["result_code"] == "signer_not_allowed_for_repo"


def test_governance_pack_trust_policy_rejects_invalid_repo_binding() -> None:
    class _InvalidBindingTrustService(_FakeGovernancePackTrustService):
        async def update_policy(self, policy: dict[str, object], *, actor_id: int | None) -> dict[str, object]:
            from tldw_Server_API.app.services.mcp_hub_governance_pack_trust_service import (
                _normalize_repo_binding,
            )

            for signer in policy.get("trusted_signers", []):
                for binding in signer.get("repo_bindings", []):
                    _normalize_repo_binding(binding)
            return await super().update_policy(policy, actor_id=actor_id)

    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE]),
        trust_service=_InvalidBindingTrustService(),
    )

    with TestClient(app) as client:
        get_resp = client.get("/api/v1/mcp/hub/governance-packs/trust-policy")
        resp = client.put(
            "/api/v1/mcp/hub/governance-packs/trust-policy",
            json={
                "policy_fingerprint": get_resp.json()["policy_fingerprint"],
                "allow_git_sources": True,
                "allowed_git_hosts": ["github.com"],
                "allowed_git_repositories": ["github.com/example/researcher-pack"],
                "allowed_git_ref_kinds": ["tag"],
                "trusted_signers": [
                    {
                        "fingerprint": "ABCD1234",
                        "repo_bindings": ["not-a-valid-binding"],
                        "status": "active",
                    }
                ],
            },
        )

    assert resp.status_code == 400
    assert "Unsupported git repository format" in resp.json()["detail"]


def test_governance_pack_trust_policy_rejects_blank_fingerprint() -> None:
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE]),
        trust_service=_FakeGovernancePackTrustService(),
    )

    with TestClient(app) as client:
        get_resp = client.get("/api/v1/mcp/hub/governance-packs/trust-policy")
        resp = client.put(
            "/api/v1/mcp/hub/governance-packs/trust-policy",
            json={
                "policy_fingerprint": get_resp.json()["policy_fingerprint"],
                "allow_git_sources": True,
                "allowed_git_hosts": ["github.com"],
                "allowed_git_repositories": ["github.com/example/researcher-pack"],
                "allowed_git_ref_kinds": ["tag"],
                "trusted_git_key_fingerprints": ["   "],
            },
        )

    assert resp.status_code == 422
    assert resp.json()["detail"][0]["msg"] == "Value error, fingerprint entries cannot be blank"


def test_governance_pack_trust_policy_rejects_empty_repo_bindings() -> None:
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE]),
        trust_service=_FakeGovernancePackTrustService(),
    )

    with TestClient(app) as client:
        get_resp = client.get("/api/v1/mcp/hub/governance-packs/trust-policy")
        resp = client.put(
            "/api/v1/mcp/hub/governance-packs/trust-policy",
            json={
                "policy_fingerprint": get_resp.json()["policy_fingerprint"],
                "allow_git_sources": True,
                "allowed_git_hosts": ["github.com"],
                "allowed_git_repositories": ["github.com/example/researcher-pack"],
                "allowed_git_ref_kinds": ["tag"],
                "trusted_signers": [
                    {
                        "fingerprint": "ABCD1234",
                        "repo_bindings": [],
                        "status": "active",
                    }
                ],
            },
        )

    assert resp.status_code == 422
    assert resp.json()["detail"][0]["msg"] == "Value error, trusted signer repo_bindings must not be empty"


def test_governance_pack_trust_policy_rejects_blank_repo_binding() -> None:
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE]),
        trust_service=_FakeGovernancePackTrustService(),
    )

    with TestClient(app) as client:
        get_resp = client.get("/api/v1/mcp/hub/governance-packs/trust-policy")
        resp = client.put(
            "/api/v1/mcp/hub/governance-packs/trust-policy",
            json={
                "policy_fingerprint": get_resp.json()["policy_fingerprint"],
                "allow_git_sources": True,
                "allowed_git_hosts": ["github.com"],
                "allowed_git_repositories": ["github.com/example/researcher-pack"],
                "allowed_git_ref_kinds": ["tag"],
                "trusted_signers": [
                    {
                        "fingerprint": "ABCD1234",
                        "repo_bindings": ["   "],
                        "status": "active",
                    }
                ],
            },
        )

    assert resp.status_code == 422
    assert resp.json()["detail"][0]["msg"] == "Value error, repo binding is required"


def test_governance_pack_trust_policy_get_reports_invalid_persisted_policy() -> None:
    class _InvalidPersistedTrustService(_FakeGovernancePackTrustService):
        async def get_policy(self) -> dict[str, object]:
            raise ValueError("invalid persisted governance pack trust policy: fingerprint entries cannot be blank")

    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE]),
        trust_service=_InvalidPersistedTrustService(),
    )

    with TestClient(app) as client:
        resp = client.get("/api/v1/mcp/hub/governance-packs/trust-policy")

    assert resp.status_code == 409
    assert resp.json()["detail"] == "invalid persisted governance pack trust policy: fingerprint entries cannot be blank"
