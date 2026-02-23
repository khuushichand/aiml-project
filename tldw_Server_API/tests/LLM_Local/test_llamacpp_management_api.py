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


class _ManagedStub:
    logger = _Logger()

    def __init__(self) -> None:
        self.llamacpp = self

    async def start_server(self, *, backend: str, model_name: str, server_args=None, **kwargs):  # noqa: ANN001
        _ = kwargs
        return {
            "status": "started",
            "backend": backend,
            "model": model_name,
            "server_args": server_args or {},
        }

    async def stop_server(self, *, backend: str, pid=None, port=None):  # noqa: ANN001
        _ = (backend, pid, port)
        return "Llama.cpp server stopped."

    async def get_server_status(self, backend: str):
        return {"status": "running", "model": "mock.gguf", "backend": backend}

    async def list_models(self):
        return ["mock.gguf", "other.gguf"]


class _FallbackModelsStub:
    logger = _Logger()
    llamacpp = None

    async def list_local_models(self, backend: str):
        return ["fallback.gguf"] if backend == "llamacpp" else []


class _StatusNoBackendStub(_ManagedStub):
    async def get_server_status(self, backend: str):
        _ = backend
        return {"status": "running", "model": "mock.gguf"}


class _StartNoStatusStub(_ManagedStub):
    async def start_server(self, *, backend: str, model_name: str, server_args=None, **kwargs):  # noqa: ANN001
        _ = (backend, server_args, kwargs)
        return {"model": model_name, "pid": 12345}


class _MetricsSyncStub(_ManagedStub):
    def get_metrics(self):
        return {"requests_total": 3}


class _MetricsAsyncStub(_ManagedStub):
    async def get_metrics(self):
        return {"requests_total": 7}


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
def test_llamacpp_start_server_happy_path():
    app = _make_app_with_manager(_ManagedStub())

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/llamacpp/start_server",
            json={"model_filename": "mock.gguf", "server_args": {"port": 8080}},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "started"
    assert body["model"] == "mock.gguf"


@pytest.mark.unit
def test_llamacpp_start_server_adds_status_when_missing():
    app = _make_app_with_manager(_StartNoStatusStub())

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/llamacpp/start_server",
            json={"model_filename": "mock.gguf", "server_args": {"port": 8080}},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"] == "mock.gguf"
    assert body["pid"] == 12345
    assert body["status"] == "started"


@pytest.mark.unit
def test_llamacpp_stop_server_happy_path():
    app = _make_app_with_manager(_ManagedStub())

    with TestClient(app) as client:
        r = client.post("/api/v1/llamacpp/stop_server", json={})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "stopped"
    assert "message" in body


@pytest.mark.unit
def test_llamacpp_status_happy_path():
    app = _make_app_with_manager(_ManagedStub())

    with TestClient(app) as client:
        r = client.get("/api/v1/llamacpp/status")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "running"
    assert body["model"] == "mock.gguf"
    assert body["backend"] == "llamacpp"


@pytest.mark.unit
def test_llamacpp_status_adds_backend_when_missing():
    app = _make_app_with_manager(_StatusNoBackendStub())

    with TestClient(app) as client:
        r = client.get("/api/v1/llamacpp/status")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "running"
    assert body["model"] == "mock.gguf"
    assert body["backend"] == "llamacpp"


@pytest.mark.unit
def test_llamacpp_models_happy_path():
    app = _make_app_with_manager(_ManagedStub())

    with TestClient(app) as client:
        r = client.get("/api/v1/llamacpp/models")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available_models"] == ["mock.gguf", "other.gguf"]


@pytest.mark.unit
def test_llamacpp_models_fallback_to_manager_when_handler_missing():
    app = _make_app_with_manager(_FallbackModelsStub())

    with TestClient(app) as client:
        r = client.get("/api/v1/llamacpp/models")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available_models"] == ["fallback.gguf"]


@pytest.mark.unit
def test_llamacpp_metrics_happy_path_sync():
    app = _make_app_with_manager(_MetricsSyncStub())

    with TestClient(app) as client:
        r = client.get("/api/v1/llamacpp/metrics")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requests_total"] == 3
    assert body["backend"] == "llamacpp"


@pytest.mark.unit
def test_llamacpp_metrics_happy_path_async():
    app = _make_app_with_manager(_MetricsAsyncStub())

    with TestClient(app) as client:
        r = client.get("/api/v1/llamacpp/metrics")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requests_total"] == 7
    assert body["backend"] == "llamacpp"
