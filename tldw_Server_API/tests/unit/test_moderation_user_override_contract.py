from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import moderation as moderation_mod
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _make_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["admin"],
        permissions=[SYSTEM_CONFIGURE],
        is_admin=True,
        org_ids=[1],
        team_ids=[],
    )


def _build_app(stub) -> FastAPI:
    app = FastAPI()
    app.include_router(moderation_mod.router, prefix="/api/v1")

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        principal = _make_principal()
        request.state.auth = AuthContext(
            principal=principal,
            ip=None,
            user_agent=None,
            request_id=None,
        )
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    moderation_mod.get_moderation_service = lambda: stub  # type: ignore[assignment]
    return app


class _StubModerationService:
    def __init__(self, overrides: dict[str, dict] | None = None):
        self.overrides = dict(overrides or {})
        self.last_set: tuple[str, dict] | None = None

    def list_user_overrides(self) -> dict[str, dict]:
        return self.overrides

    def set_user_override(self, user_id: str, override: dict) -> dict:
        self.last_set = (user_id, dict(override))
        self.overrides[str(user_id)] = dict(override)
        return {"ok": True, "persisted": True}

    def delete_user_override(self, user_id: str) -> dict:
        if str(user_id) not in self.overrides:
            return {"ok": False, "persisted": False, "error": "not found"}
        self.overrides.pop(str(user_id), None)
        return {"ok": True, "persisted": True}


@pytest.mark.unit
def test_get_user_override_returns_rules_payload():
    stub = _StubModerationService(
        {
            "alice": {
                "enabled": True,
                "rules": [
                    {
                        "id": "r1",
                        "pattern": "bad",
                        "is_regex": False,
                        "action": "block",
                        "phase": "both",
                    }
                ],
            }
        }
    )
    app = _build_app(stub)

    with TestClient(app) as client:
        resp = client.get("/api/v1/moderation/users/alice")

    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["rules"][0]["action"] == "block"


@pytest.mark.unit
def test_put_user_override_persists_rules_payload():
    stub = _StubModerationService()
    app = _build_app(stub)

    payload = {
        "enabled": True,
        "rules": [
            {
                "id": "n1",
                "pattern": "heads up",
                "is_regex": False,
                "action": "warn",
                "phase": "both",
            }
        ],
    }

    with TestClient(app) as client:
        resp = client.put("/api/v1/moderation/users/alice", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["persisted"] is True
    assert body["rules"][0]["pattern"] == "heads up"
    assert body["rules"][0]["action"] == "warn"
    assert stub.last_set is not None
    assert stub.last_set[0] == "alice"
    assert stub.last_set[1]["rules"][0]["phase"] == "both"


@pytest.mark.unit
def test_get_user_override_missing_returns_404():
    stub = _StubModerationService()
    app = _build_app(stub)

    with TestClient(app) as client:
        resp = client.get("/api/v1/moderation/users/missing")

    assert resp.status_code == 404
    assert resp.json().get("detail") == "Override not found"
