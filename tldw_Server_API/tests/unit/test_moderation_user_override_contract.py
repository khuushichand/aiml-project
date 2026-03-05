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


def _build_app() -> FastAPI:
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
    return app


class _Svc:
    def __init__(self, overrides: dict[str, dict[str, object]]) -> None:
        self._overrides = overrides

    def list_user_overrides(self) -> dict[str, dict[str, object]]:
        return dict(self._overrides)


@pytest.mark.unit
def test_get_user_override_returns_exists_false_for_missing_override(monkeypatch):
    monkeypatch.setattr(moderation_mod, "get_moderation_service", lambda: _Svc({}))
    app = _build_app()

    with TestClient(app) as client:
        resp = client.get("/api/v1/moderation/users/new-user")

    assert resp.status_code == 200
    assert resp.json() == {"exists": False, "override": {}}


@pytest.mark.unit
def test_get_user_override_returns_exists_true_with_override_payload(monkeypatch):
    monkeypatch.setattr(
        moderation_mod,
        "get_moderation_service",
        lambda: _Svc({"alice": {"enabled": True, "input_action": "warn"}}),
    )
    app = _build_app()

    with TestClient(app) as client:
        resp = client.get("/api/v1/moderation/users/alice")

    assert resp.status_code == 200
    assert resp.json() == {
        "exists": True,
        "override": {"enabled": True, "input_action": "warn"},
    }
