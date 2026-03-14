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
    ) -> dict[str, object]:
        self.import_calls.append(
            {
                "document": dict(document),
                "owner_scope_type": owner_scope_type,
                "owner_scope_id": owner_scope_id,
                "actor_id": actor_id,
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


def _build_app(
    principal: AuthPrincipal,
    *,
    policy_service: _FakePolicyService | None = None,
    governance_service: _FakeGovernancePackService | None = None,
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

    assert detail_resp.status_code == 200
    detail_payload = detail_resp.json()
    assert detail_payload["imported_objects"][0]["source_object_id"] == "researcher.profile"
    assert detail_payload["imported_objects"][1]["object_type"] == "policy_assignment"
