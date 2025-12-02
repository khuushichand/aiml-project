from types import SimpleNamespace
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints.media import add as media_add_mod
from tldw_Server_API.app.api.v1.schemas.media_request_models import AddMediaForm
from tldw_Server_API.app.core.AuthNZ.permissions import MEDIA_CREATE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _make_principal(
    *,
    kind: str = "user",
    is_admin: bool = False,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind=kind,
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=permissions or [],
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


def _build_app_with_overrides(
    principal: AuthPrincipal,
    *,
    user_permissions: list[str],
) -> FastAPI:
    app = FastAPI()
    # Mirror production prefix so paths stay consistent.
    app.include_router(media_add_mod.router, prefix="/api/v1/media")

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        ip = request.client.host if getattr(request, "client", None) else None
        ua = request.headers.get("User-Agent") if getattr(request, "headers", None) else None
        request_id = request.headers.get("X-Request-ID") if getattr(request, "headers", None) else None
        request.state.auth = AuthContext(
            principal=principal,
            ip=ip,
            user_agent=ua,
            request_id=request_id,
        )
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal

    async def _fake_get_request_user():
        return SimpleNamespace(
            id=1,
            username="media-user",
            is_active=True,
            roles=list(principal.roles),
            permissions=list(user_permissions),
            is_admin=principal.is_admin,
            tenant_id="default",
        )

    # add_media's current_user param
    app.dependency_overrides[media_add_mod.get_request_user] = _fake_get_request_user

    # Light stubs for other dependencies so the handler can execute when permitted.
    async def _fake_get_add_media_form() -> AddMediaForm:
        return AddMediaForm(
            media_type="video",
            urls=["https://example.com/test.mp4"],
        )

    app.dependency_overrides[media_add_mod.get_add_media_form] = _fake_get_add_media_form

    async def _fake_get_media_db_for_user():
        return SimpleNamespace()

    app.dependency_overrides[media_add_mod.get_media_db_for_user] = _fake_get_media_db_for_user

    async def _fake_get_usage_event_logger():
        class _Logger:
            async def log(self, *_args: Any, **_kwargs: Any) -> None:
                return None

        return _Logger()

    app.dependency_overrides[media_add_mod.get_usage_event_logger] = _fake_get_usage_event_logger

    async def _fake_add_media_persist(**_kwargs: Any) -> Dict[str, Any]:
        return {"ok": True}

    app.dependency_overrides[media_add_mod.add_media_persist] = _fake_add_media_persist

    return app


@pytest.mark.asyncio
async def test_media_add_forbidden_when_principal_lacks_media_create_but_user_has_claim():
    """
    PermissionChecker sees media.create on the User object, but the AuthPrincipal
    lacks MEDIA_CREATE in its permissions. The request must still be forbidden,
    demonstrating that require_permissions(MEDIA_CREATE) is the effective gate.
    """
    principal = _make_principal(
        roles=["user"],
        permissions=[],
        is_admin=False,
    )
    app = _build_app_with_overrides(
        principal,
        user_permissions=[MEDIA_CREATE],
    )

    with TestClient(app) as client:
        resp = client.post("/api/v1/media/add", data={"media_type": "video", "urls": "https://example.com"})
    assert resp.status_code == 403
    assert "media.create" in resp.json().get("detail", "")
