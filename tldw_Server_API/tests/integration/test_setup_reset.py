from fastapi import FastAPI
from fastapi.testclient import TestClient

import tldw_Server_API.app.api.v1.endpoints.setup as setup_endpoint
from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext
from starlette.requests import Request


def test_admin_reset_calls_reset_flags(mocker):
    app = FastAPI()
    app.include_router(setup_endpoint.router, prefix="/api/v1")

    # Override claim-first principal dependency to present an admin principal
    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="admin",
            token_type="access",
            jti=None,
            roles=["admin"],
            permissions=["system.configure"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        try:
            request.state.auth = AuthContext(
                principal=principal,
                ip=None,
                user_agent=None,
                request_id=None,
            )
        except Exception:
            pass
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal

    called = {"count": 0}
    def fake_reset():
        called["count"] += 1

    mocker.patch.object(setup_endpoint.setup_manager, "reset_setup_flags", side_effect=fake_reset)

    with TestClient(app) as client:
        resp = client.post("/api/v1/setup/reset")

    # Cleanup override
    app.dependency_overrides.pop(auth_deps.get_auth_principal, None)

    assert resp.status_code == 200
    assert called["count"] == 1
    body = resp.json()
    assert body.get('success') is True
    assert body.get('requires_restart') is True
