from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import mcp_hub_management
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


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
        self.permission_profiles = [
            {
                "id": 5,
                "name": "Process Exec",
                "description": None,
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "mode": "custom",
                "policy_document": {"capabilities": ["process.execute"]},
                "is_active": True,
                "created_by": 7,
                "updated_by": 7,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
        self.policy_assignments = [
            {
                "id": 11,
                "target_type": "persona",
                "target_id": "researcher",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "profile_id": None,
                "inline_policy_document": {"capabilities": ["process.execute"]},
                "approval_policy_id": None,
                "is_active": True,
                "created_by": 7,
                "updated_by": 7,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
        self.approval_policies = [
            {
                "id": 17,
                "name": "Outside Profile",
                "description": None,
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "mode": "ask_outside_profile",
                "rules": {"duration_options": ["once", "session"]},
                "is_active": True,
                "created_by": 7,
                "updated_by": 7,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
        self.approval_decisions = []

    async def list_permission_profiles(self, **_kwargs):
        return list(self.permission_profiles)

    async def create_permission_profile(self, **kwargs):
        profile = {
            "id": 5,
            "name": kwargs["name"],
            "description": kwargs.get("description"),
            "owner_scope_type": kwargs["owner_scope_type"],
            "owner_scope_id": kwargs.get("owner_scope_id"),
            "mode": kwargs["mode"],
            "policy_document": kwargs["policy_document"],
            "is_active": kwargs.get("is_active", True),
            "created_by": kwargs.get("actor_id"),
            "updated_by": kwargs.get("actor_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.permission_profiles = [profile]
        return profile

    async def update_permission_profile(self, profile_id: int, **kwargs):
        if profile_id != 5:
            return None
        profile = dict(self.permission_profiles[0])
        if kwargs.get("name") is not None:
            profile["name"] = kwargs["name"]
        if kwargs.get("description") is not None:
            profile["description"] = kwargs["description"]
        if kwargs.get("mode") is not None:
            profile["mode"] = kwargs["mode"]
        if kwargs.get("policy_document") is not None:
            profile["policy_document"] = kwargs["policy_document"]
        if kwargs.get("is_active") is not None:
            profile["is_active"] = kwargs["is_active"]
        profile["updated_by"] = kwargs.get("actor_id")
        self.permission_profiles = [profile]
        return profile

    async def delete_permission_profile(self, profile_id: int, *, actor_id: int | None):
        return profile_id == 5 and actor_id == 7

    async def list_policy_assignments(self, **_kwargs):
        return list(self.policy_assignments)

    async def create_policy_assignment(self, **kwargs):
        assignment = {
            "id": 11,
            "target_type": kwargs["target_type"],
            "target_id": kwargs.get("target_id"),
            "owner_scope_type": kwargs["owner_scope_type"],
            "owner_scope_id": kwargs.get("owner_scope_id"),
            "profile_id": kwargs.get("profile_id"),
            "inline_policy_document": kwargs["inline_policy_document"],
            "approval_policy_id": kwargs.get("approval_policy_id"),
            "is_active": kwargs.get("is_active", True),
            "created_by": kwargs.get("actor_id"),
            "updated_by": kwargs.get("actor_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.policy_assignments = [assignment]
        return assignment

    async def update_policy_assignment(self, assignment_id: int, **kwargs):
        if assignment_id != 11:
            return None
        assignment = dict(self.policy_assignments[0])
        if kwargs.get("target_type") is not None:
            assignment["target_type"] = kwargs["target_type"]
        if kwargs.get("target_id") is not None:
            assignment["target_id"] = kwargs["target_id"]
        if kwargs.get("inline_policy_document") is not None:
            assignment["inline_policy_document"] = kwargs["inline_policy_document"]
        if kwargs.get("profile_id") is not None:
            assignment["profile_id"] = kwargs["profile_id"]
        if kwargs.get("approval_policy_id") is not None:
            assignment["approval_policy_id"] = kwargs["approval_policy_id"]
        if kwargs.get("is_active") is not None:
            assignment["is_active"] = kwargs["is_active"]
        assignment["updated_by"] = kwargs.get("actor_id")
        self.policy_assignments = [assignment]
        return assignment

    async def delete_policy_assignment(self, assignment_id: int, *, actor_id: int | None):
        return assignment_id == 11 and actor_id == 7

    async def list_approval_policies(self, **_kwargs):
        return list(self.approval_policies)

    async def create_approval_policy(self, **kwargs):
        policy = {
            "id": 17,
            "name": kwargs["name"],
            "description": kwargs.get("description"),
            "owner_scope_type": kwargs["owner_scope_type"],
            "owner_scope_id": kwargs.get("owner_scope_id"),
            "mode": kwargs["mode"],
            "rules": kwargs["rules"],
            "is_active": kwargs.get("is_active", True),
            "created_by": kwargs.get("actor_id"),
            "updated_by": kwargs.get("actor_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.approval_policies = [policy]
        return policy

    async def update_approval_policy(self, approval_policy_id: int, **kwargs):
        if approval_policy_id != 17:
            return None
        policy = dict(self.approval_policies[0])
        if kwargs.get("name") is not None:
            policy["name"] = kwargs["name"]
        if kwargs.get("description") is not None:
            policy["description"] = kwargs["description"]
        if kwargs.get("mode") is not None:
            policy["mode"] = kwargs["mode"]
        if kwargs.get("rules") is not None:
            policy["rules"] = kwargs["rules"]
        if kwargs.get("is_active") is not None:
            policy["is_active"] = kwargs["is_active"]
        policy["updated_by"] = kwargs.get("actor_id")
        self.approval_policies = [policy]
        return policy

    async def delete_approval_policy(self, approval_policy_id: int, *, actor_id: int | None):
        return approval_policy_id == 17 and actor_id == 7

    async def record_approval_decision(self, **kwargs):
        decision = {
            "id": 23,
            "approval_policy_id": kwargs.get("approval_policy_id"),
            "context_key": kwargs["context_key"],
            "conversation_id": kwargs.get("conversation_id"),
            "tool_name": kwargs["tool_name"],
            "scope_key": kwargs["scope_key"],
            "decision": kwargs["decision"],
            "expires_at": kwargs.get("expires_at"),
            "consume_on_match": bool(kwargs.get("consume_on_match")),
            "consumed_at": kwargs.get("consumed_at"),
            "created_by": kwargs.get("actor_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.approval_decisions = [decision]
        return decision


class _FakePolicyResolver:
    async def resolve_for_context(self, *, user_id, metadata):
        return {
            "enabled": True,
            "allowed_tools": ["Bash(git *)"],
            "denied_tools": ["Bash(rm *)"],
            "capabilities": ["process.execute"],
            "approval_policy_id": 17,
            "approval_mode": "ask_outside_profile",
            "policy_document": {
                "allowed_tools": ["Bash(git *)"],
                "denied_tools": ["Bash(rm *)"],
                "capabilities": ["process.execute"]
            },
            "sources": [
                {
                    "assignment_id": 11,
                    "target_type": "persona",
                    "target_id": metadata.get("persona_id"),
                    "owner_scope_type": "user",
                    "owner_scope_id": user_id,
                    "profile_id": 5
                }
            ]
        }


def _build_app(
    principal: AuthPrincipal,
    service: _FakePolicyService | None = None,
    resolver: _FakePolicyResolver | None = None
) -> FastAPI:
    app = FastAPI()
    app.include_router(mcp_hub_management.router, prefix="/api/v1")

    async def _fake_get_auth_principal(_request: Request) -> AuthPrincipal:  # type: ignore[override]
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_service] = lambda: service or _FakePolicyService()
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_policy_resolver_dep] = (
        lambda: resolver or _FakePolicyResolver()
    )
    return app


def test_create_permission_profile_requires_grant_authority_for_capabilities() -> None:
    app = _build_app(
        _make_principal(
            roles=[],
            permissions=[SYSTEM_CONFIGURE],
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/permission-profiles",
            json={
                "name": "Process Exec",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "mode": "custom",
                "policy_document": {"capabilities": ["process.execute"]},
                "is_active": True,
            },
        )

    assert resp.status_code == 403
    assert "grant.process.execute" in resp.json()["detail"]


def test_create_permission_profile_returns_created_payload_when_grant_is_present() -> None:
    app = _build_app(
        _make_principal(
            roles=[],
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute"],
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/permission-profiles",
            json={
                "name": "Process Exec",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "mode": "custom",
                "policy_document": {"capabilities": ["process.execute"]},
                "is_active": True,
            },
        )

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["name"] == "Process Exec"
    assert payload["policy_document"]["capabilities"] == ["process.execute"]
    assert payload["owner_scope_type"] == "user"


def test_create_policy_assignment_returns_created_payload() -> None:
    app = _build_app(
        _make_principal(
            roles=[],
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute"],
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/policy-assignments",
            json={
                "target_type": "persona",
                "target_id": "researcher",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "profile_id": None,
                "inline_policy_document": {"capabilities": ["process.execute"]},
                "approval_policy_id": None,
                "is_active": True,
            },
        )

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["target_type"] == "persona"
    assert payload["target_id"] == "researcher"
    assert payload["inline_policy_document"]["capabilities"] == ["process.execute"]


def test_create_approval_policy_returns_created_payload() -> None:
    app = _build_app(
        _make_principal(
            roles=[],
            permissions=[SYSTEM_CONFIGURE],
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/approval-policies",
            json={
                "name": "Outside Profile",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "mode": "ask_outside_profile",
                "rules": {"duration_options": ["once", "session"]},
                "is_active": True,
            },
        )

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["name"] == "Outside Profile"
    assert payload["mode"] == "ask_outside_profile"
    assert payload["rules"]["duration_options"] == ["once", "session"]


def test_record_approval_decision_returns_created_payload() -> None:
    app = _build_app(
        _make_principal(
            roles=[],
            permissions=[],
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/approval-decisions",
            json={
                "approval_policy_id": 17,
                "context_key": "user:7|group:|persona:researcher",
                "conversation_id": "sess-1",
                "tool_name": "Bash",
                "scope_key": "tool:Bash|command:abc123",
                "decision": "approved",
                "consume_on_match": True,
            },
        )

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["approval_policy_id"] == 17
    assert payload["context_key"] == "user:7|group:|persona:researcher"
    assert payload["decision"] == "approved"
    assert payload["consume_on_match"] is True


def test_record_approval_decision_rejects_foreign_context_key() -> None:
    app = _build_app(
        _make_principal(
            roles=[],
            permissions=[],
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/approval-decisions",
            json={
                "approval_policy_id": 17,
                "context_key": "user:9|group:|persona:researcher",
                "conversation_id": "sess-1",
                "tool_name": "Bash",
                "scope_key": "tool:Bash|command:abc123",
                "decision": "approved",
            },
        )

    assert resp.status_code == 403


def test_get_effective_policy_returns_resolved_payload() -> None:
    app = _build_app(
        _make_principal(
            roles=[],
            permissions=[],
        )
    )

    with TestClient(app) as client:
        resp = client.get("/api/v1/mcp/hub/effective-policy?persona_id=researcher&group_id=team-red")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["enabled"] is True
    assert payload["allowed_tools"] == ["Bash(git *)"]
    assert payload["approval_mode"] == "ask_outside_profile"
    assert payload["sources"][0]["target_id"] == "researcher"


def test_list_permission_profiles_returns_visible_rows() -> None:
    app = _build_app(
        _make_principal(
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute"],
        )
    )

    with TestClient(app) as client:
        resp = client.get("/api/v1/mcp/hub/permission-profiles")

    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "Process Exec"


def test_update_permission_profile_requires_grant_authority_for_new_capability() -> None:
    app = _build_app(
        _make_principal(
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute"],
        )
    )

    with TestClient(app) as client:
        resp = client.put(
            "/api/v1/mcp/hub/permission-profiles/5",
            json={"policy_document": {"capabilities": ["network.external"]}},
        )

    assert resp.status_code == 403
    assert "grant.network.external" in resp.json()["detail"]


def test_update_permission_profile_returns_404_when_missing() -> None:
    app = _build_app(
        _make_principal(
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute"],
        )
    )

    with TestClient(app) as client:
        resp = client.put(
            "/api/v1/mcp/hub/permission-profiles/999",
            json={"name": "Missing"},
        )

    assert resp.status_code == 404


def test_delete_permission_profile_returns_ok() -> None:
    app = _build_app(
        _make_principal(
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute"],
        )
    )

    with TestClient(app) as client:
        resp = client.delete("/api/v1/mcp/hub/permission-profiles/5")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_list_policy_assignments_returns_visible_rows() -> None:
    app = _build_app(
        _make_principal(
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute"],
        )
    )

    with TestClient(app) as client:
        resp = client.get("/api/v1/mcp/hub/policy-assignments")

    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload) == 1
    assert payload[0]["target_id"] == "researcher"


def test_update_policy_assignment_returns_updated_payload() -> None:
    app = _build_app(
        _make_principal(
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute", "grant.network.external"],
        )
    )

    with TestClient(app) as client:
        resp = client.put(
            "/api/v1/mcp/hub/policy-assignments/11",
            json={"inline_policy_document": {"capabilities": ["network.external"]}},
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["inline_policy_document"]["capabilities"] == ["network.external"]


def test_delete_policy_assignment_returns_ok() -> None:
    app = _build_app(
        _make_principal(
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute"],
        )
    )

    with TestClient(app) as client:
        resp = client.delete("/api/v1/mcp/hub/policy-assignments/11")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
