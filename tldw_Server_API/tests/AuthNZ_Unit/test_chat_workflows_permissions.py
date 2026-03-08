from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import chat_workflows as chat_workflows_mod
from tldw_Server_API.app.core.AuthNZ.permissions import CHAT_WORKFLOWS_RUN
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


class _FakeChatWorkflowsDb:
    pass


def _make_principal(*, permissions: list[str]) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["user"],
        permissions=permissions,
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )


def _build_app(principal_permissions: list[str]) -> FastAPI:
    app = FastAPI()
    app.include_router(chat_workflows_mod.router)
    principal = _make_principal(permissions=principal_permissions)

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        request.state.auth = AuthContext(
            principal=principal,
            ip=request.client.host if getattr(request, "client", None) else None,
            user_agent=request.headers.get("User-Agent"),
            request_id=request.headers.get("X-Request-ID"),
        )
        return principal

    async def _fake_get_user_context() -> dict[str, Any]:
        return {
            "user_id": "1",
            "tenant_id": "default",
            "client_id": "test-client",
            "is_admin": False,
            "permissions": list(principal_permissions),
        }

    async def _fake_get_db():
        return _FakeChatWorkflowsDb()

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[chat_workflows_mod._get_user_context] = _fake_get_user_context
    app.dependency_overrides[chat_workflows_mod._get_db] = _fake_get_db
    return app


@pytest.mark.asyncio
async def test_chat_workflows_run_endpoint_forbidden_without_permission():
    app = _build_app(principal_permissions=[])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat-workflows/runs",
            json={"template_id": 1, "selected_context_refs": []},
        )

    assert response.status_code == 403
    assert CHAT_WORKFLOWS_RUN in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_chat_workflows_run_endpoint_allows_permission():
    app = _build_app(principal_permissions=[CHAT_WORKFLOWS_RUN])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat-workflows/runs",
            json={"template_id": 1, "selected_context_refs": []},
        )

    assert response.status_code != 403
