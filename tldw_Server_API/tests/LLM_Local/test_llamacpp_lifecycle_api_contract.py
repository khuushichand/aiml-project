from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import llamacpp as lp
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _admin_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["admin"],
        permissions=[],
        is_admin=True,
        org_ids=[],
        team_ids=[],
    )


class _Logger:
    def error(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return


class _NoLlamaManager:
    logger = _Logger()
    llamacpp = None


class _StopManager:
    logger = _Logger()
    llamacpp = None

    async def stop_server(self, *, backend: str, pid=None, port=None):  # noqa: ANN001
        _ = (backend, pid, port)
        return "Llama.cpp server stopped."


def _make_app_with_manager(manager) -> FastAPI:  # noqa: ANN001
    app = FastAPI()
    app.include_router(lp.router, prefix="/api/v1")
    app.state.llm_manager = manager

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        principal = _admin_principal()
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

    async def _fake_check_rate_limit() -> None:
        return

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[auth_deps.check_rate_limit] = _fake_check_rate_limit
    app.dependency_overrides[lp.check_rate_limit] = _fake_check_rate_limit
    return app


@pytest.mark.unit
def test_llamacpp_status_returns_managed_plane_503_when_unavailable():
    app = _make_app_with_manager(_NoLlamaManager())

    with TestClient(app) as client:
        resp = client.get("/api/v1/llamacpp/status")

    assert resp.status_code == 503
    assert "managed llama.cpp" in resp.json().get("detail", "").lower()


@pytest.mark.unit
def test_llamacpp_stop_response_contains_status_and_message():
    app = _make_app_with_manager(_StopManager())

    with TestClient(app) as client:
        resp = client.post("/api/v1/llamacpp/stop_server", json={})

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "stopped"
    assert "message" in body
