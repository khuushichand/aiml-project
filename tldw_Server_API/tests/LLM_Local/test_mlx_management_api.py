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
def test_mlx_load_trims_explicit_model_path(monkeypatch):
    registry = _RegistryStub()
    monkeypatch.setattr(mlx_ep, "_default_settings", lambda: {"model_path": "default-model"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/llm/providers/mlx/load",
            json={"model_path": "  explicit-model  "},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["backend"] == "mlx"
    assert registry.last_model_path == "explicit-model"


@pytest.mark.unit
def test_mlx_load_blank_explicit_model_path_falls_back_to_default(monkeypatch):
    registry = _RegistryStub()
    monkeypatch.setattr(mlx_ep, "_default_settings", lambda: {"model_path": "default-model"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/llm/providers/mlx/load",
            json={"model_path": "   "},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["backend"] == "mlx"
    assert registry.last_model_path == "default-model"


@pytest.mark.unit
def test_mlx_load_accepts_empty_post_body(monkeypatch):
    registry = _RegistryStub(load_result={"active": True, "model": "stub-model"})
    monkeypatch.setattr(mlx_ep, "_default_settings", lambda: {"model_path": "stub-model"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post("/api/v1/llm/providers/mlx/load")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["backend"] == "mlx"
    assert registry.last_model_path == "stub-model"
    assert registry.last_overrides == {}


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
def test_mlx_unload_accepts_empty_post_body():
    registry = _RegistryStub(unload_result={"status": "unloaded"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post("/api/v1/llm/providers/mlx/unload")

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


@pytest.mark.unit
def test_mlx_models_returns_200_with_warning_when_model_dir_unset():
    registry = _RegistryStub()
    registry.last_refresh = None

    def _list_models(*, refresh: bool = False):
        registry.last_refresh = refresh
        return {
            "model_dir": None,
            "model_dir_configured": False,
            "warnings": ["MLX_MODEL_DIR is not configured"],
            "available_models": [],
        }

    registry.list_models = _list_models  # type: ignore[attr-defined]
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.get("/api/v1/llm/providers/mlx/models")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["backend"] == "mlx"
    assert body["available_models"] == []
    assert body["warnings"]
    assert registry.last_refresh is False


@pytest.mark.unit
def test_mlx_load_with_model_id_resolves_and_calls_registry(monkeypatch):
    registry = _RegistryStub()
    registry.last_model_id = None
    registry.last_refresh_discovery = None

    def _resolve_model_id(model_id: str, *, refresh_discovery: bool = False) -> str:
        registry.last_model_id = model_id
        registry.last_refresh_discovery = refresh_discovery
        return f"/tmp/mlx-models/{model_id}"

    registry.resolve_model_id = _resolve_model_id  # type: ignore[attr-defined]
    monkeypatch.setattr(mlx_ep, "_default_settings", lambda: {"model_path": "default-model", "model_dir": "/tmp/mlx-models"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/llm/providers/mlx/load",
            json={"model_id": "family/model-a", "max_concurrent": 2},
        )

    assert response.status_code == 200, response.text
    assert registry.last_model_id == "family/model-a"
    assert registry.last_model_path == "/tmp/mlx-models/family/model-a"
    assert registry.last_overrides == {"max_concurrent": 2}


@pytest.mark.unit
def test_mlx_load_rejects_traversal_model_id(monkeypatch):
    registry = _RegistryStub()

    def _resolve_model_id(model_id: str, *, refresh_discovery: bool = False) -> str:
        raise ChatBadRequestError(provider="mlx", message="model_id resolves outside MLX_MODEL_DIR")

    registry.resolve_model_id = _resolve_model_id  # type: ignore[attr-defined]
    monkeypatch.setattr(mlx_ep, "_default_settings", lambda: {"model_dir": "/tmp/mlx-models"})
    app = _make_app_with_registry(registry)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/llm/providers/mlx/load",
            json={"model_id": "../escape"},
        )

    assert response.status_code == 400
    assert "outside MLX_MODEL_DIR" in response.json().get("detail", "")
