from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import workflows as workflows_mod
from tldw_Server_API.app.core.AuthNZ.permissions import WORKFLOWS_RUNS_READ
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _make_principal(
    *,
    kind: str = "user",
    is_admin: bool = False,
    roles: List[str] | None = None,
    permissions: List[str] | None = None,
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


class _FakeArtifactsDb:
    def get_run(self, run_id: str) -> Any:  # pragma: no cover - simple data shape
        return SimpleNamespace(
            run_id=run_id,
            tenant_id="default",
            user_id=1,
            validation_mode=None,
        )

    def get_artifact(self, artifact_id: str) -> Dict[str, Any] | None:
        return {
            "artifact_id": artifact_id,
            "run_id": "run-123",
            "uri": "file:///nonexistent/path",
            "size_bytes": 0,
            "mime_type": "text/plain",
            "checksum_sha256": None,
            "metadata_json": {},
        }


def _build_app_with_overrides(
    principal: AuthPrincipal,
    *,
    user_permissions: List[str],
) -> FastAPI:
    app = FastAPI()
    app.include_router(workflows_mod.router)

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
            username="wf-artifacts-user",
            is_active=True,
            roles=list(principal.roles),
            permissions=list(user_permissions),
            is_admin=principal.is_admin,
            tenant_id="default",
        )

    app.dependency_overrides[workflows_mod.get_request_user] = _fake_get_request_user

    async def _fake_get_db():
        return _FakeArtifactsDb()

    app.dependency_overrides[workflows_mod._get_db] = _fake_get_db

    return app


@pytest.mark.asyncio
async def test_workflows_artifacts_verify_batch_forbidden_when_principal_lacks_permission_but_user_has():
    principal = _make_principal(
        roles=["user"],
        permissions=[],
        is_admin=False,
    )
    app = _build_app_with_overrides(
        principal,
        user_permissions=[WORKFLOWS_RUNS_READ],
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/workflows/runs/run-123/artifacts/verify-batch",
            json={"items": [{"artifact_id": "art-1"}]},
        )
    assert resp.status_code == 403
    assert WORKFLOWS_RUNS_READ in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_workflows_artifacts_verify_batch_allowed_with_read_permission():
    principal = _make_principal(
        roles=["user"],
        permissions=[WORKFLOWS_RUNS_READ],
        is_admin=False,
    )
    app = _build_app_with_overrides(
        principal,
        user_permissions=[WORKFLOWS_RUNS_READ],
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/workflows/runs/run-123/artifacts/verify-batch",
            json={"items": [{"artifact_id": "art-1"}]},
        )
    # The handler may return 200 with a results payload; we only assert that
    # authorization succeeded (no 403 from require_permissions).
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_workflows_artifact_download_forbidden_when_principal_lacks_permission_but_user_has():
    principal = _make_principal(
        roles=["user"],
        permissions=[],
        is_admin=False,
    )
    app = _build_app_with_overrides(
        principal,
        user_permissions=[WORKFLOWS_RUNS_READ],
    )

    with TestClient(app) as client:
        resp = client.get("/api/v1/workflows/artifacts/art-1/download")
    assert resp.status_code == 403
    assert WORKFLOWS_RUNS_READ in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_workflows_artifact_download_reaches_handler_with_read_permission():
    principal = _make_principal(
        roles=["user"],
        permissions=[WORKFLOWS_RUNS_READ],
        is_admin=False,
    )
    app = _build_app_with_overrides(
        principal,
        user_permissions=[WORKFLOWS_RUNS_READ],
    )

    with TestClient(app) as client:
        resp = client.get("/api/v1/workflows/artifacts/art-1/download")
    # Under our fake DB, the artifact points to a non-existent file path.
    # The handler should therefore reach the file check and respond with 404,
    # rather than failing with a 403 from require_permissions.
    assert resp.status_code in {200, 400, 404, 409}
    assert resp.status_code != 403
