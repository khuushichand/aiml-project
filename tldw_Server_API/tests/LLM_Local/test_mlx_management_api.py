from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import mlx as mlx_ep
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError, ChatProviderError


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


class _RegistryStub:
    def __init__(
        self,
        *,
        load_result=None,
        unload_result=None,
        status_result=None,
        load_error: Exception | None = None,
    ) -> None:
        self._load_result = load_result
        self._unload_result = unload_result
        self._status_result = status_result
        self._load_error = load_error
        self.last_model_path = None
        self.last_overrides = None

    def load(self, *, model_path=None, overrides=None):
        self.last_model_path = model_path
        self.last_overrides = dict(overrides or {})
        if self._load_error is not None:
            raise self._load_error
        if self._load_result is not None:
            return self._load_result
        return {"active": True, "model": model_path}

    def unload(self):
        if self._unload_result is not None:
            return self._unload_result
        return {"status": "unloaded"}

    def status(self):
        if self._status_result is not None:
            return self._status_result
        return {"active": True, "model": "stub-model"}


def _make_app_with_registry(registry: _RegistryStub) -> FastAPI:
    app = FastAPI()
    app.include_router(mlx_ep.router, prefix="/api/v1")

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
    app.dependency_overrides[mlx_ep.check_rate_limit] = _fake_check_rate_limit
    app.dependency_overrides[mlx_ep._resolve_mlx_registry] = lambda: registry
    return app


@pytest.mark.unit
def test_mlx_load_uses_default_model_path_and_adds_backend(monkeypatch):
    registry = _RegistryStub(load_result={"active": True, "model": "stub-model"})
    monkeypatch.setattr(mlx_ep, "_default_settings", lambda: {"model_path": "stub-model"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post("/api/v1/llm/providers/mlx/load", json={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["backend"] == "mlx"
    assert registry.last_model_path == "stub-model"
    assert registry.last_overrides == {}


@pytest.mark.unit
def test_mlx_load_preserves_explicit_model_path_and_overrides(monkeypatch):
    registry = _RegistryStub()
    monkeypatch.setattr(mlx_ep, "_default_settings", lambda: {"model_path": "default-model"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/llm/providers/mlx/load",
            json={"model_path": "explicit-model", "max_concurrent": 2},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["backend"] == "mlx"
    assert registry.last_model_path == "explicit-model"
    assert registry.last_overrides == {"max_concurrent": 2}


@pytest.mark.unit
def test_mlx_unload_adds_backend():
    registry = _RegistryStub(unload_result={"status": "unloaded"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post("/api/v1/llm/providers/mlx/unload", json={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "unloaded"
    assert body["backend"] == "mlx"


@pytest.mark.unit
def test_mlx_status_adds_backend():
    registry = _RegistryStub(status_result={"active": False, "model": None})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.get("/api/v1/llm/providers/mlx/status")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["active"] is False
    assert body["backend"] == "mlx"


@pytest.mark.unit
def test_mlx_load_maps_bad_request_error_to_400(monkeypatch):
    registry = _RegistryStub(load_error=ChatBadRequestError(provider="mlx", message="model_path is required"))
    monkeypatch.setattr(mlx_ep, "_default_settings", lambda: {"model_path": "stub-model"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post("/api/v1/llm/providers/mlx/load", json={})

    assert response.status_code == 400
    assert "model_path is required" in response.json().get("detail", "")


@pytest.mark.unit
def test_mlx_load_maps_provider_error_to_500(monkeypatch):
    registry = _RegistryStub(load_error=ChatProviderError(provider="mlx", message="mlx-lm is not installed"))
    monkeypatch.setattr(mlx_ep, "_default_settings", lambda: {"model_path": "stub-model"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post("/api/v1/llm/providers/mlx/load", json={})

    assert response.status_code == 500
    assert "mlx-lm is not installed" in response.json().get("detail", "")
