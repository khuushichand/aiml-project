from __future__ import annotations

import builtins
import importlib
import sys

import pytest
from fastapi import APIRouter, FastAPI


@pytest.mark.unit
def test_router_contract_includes_key_paths() -> None:
    from tldw_Server_API.app.main import app

    paths = {route.path for route in app.routes}
    expected_paths = {
        "/health",
        "/openapi.json",
        "/api/v1/chat/completions",
        "/api/v1/rag/search",
    }
    missing_paths = sorted(expected_paths - paths)
    assert not missing_paths, f"Missing expected paths: {missing_paths}"
    assert any(path.startswith("/api/v1/media/process") for path in paths), (
        "Expected at least one media process route under /api/v1/media/process*"
    )


@pytest.mark.integration
def test_openapi_contains_core_tags(client_user_only) -> None:
    response = client_user_only.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    tags = {tag["name"] for tag in payload.get("tags", [])}
    expected_tags = {"chat", "audio", "media", "rag-unified"}
    missing_tags = sorted(expected_tags - tags)
    assert not missing_tags, f"Missing expected tags: {missing_tags}"


@pytest.mark.unit
def test_router_registry_idempotent_registration() -> None:
    from tldw_Server_API.app.api.v1.router_registry import include_router_idempotent

    app = FastAPI()
    test_router = APIRouter()

    @test_router.get("/health")
    def _health() -> dict[str, str]:
        return {"status": "ok"}

    include_router_idempotent(app, test_router, prefix="/api/v1", tags=["health"])
    include_router_idempotent(app, test_router, prefix="/api/v1", tags=["health"])

    route_signatures = {
        (route.path, tuple(sorted(getattr(route, "methods", set()))))
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/v1")
    }
    assert route_signatures == {("/api/v1/health", ("GET",))}


@pytest.mark.integration
def test_minimal_app_uses_router_registry(client_user_only) -> None:
    assert hasattr(client_user_only.app.state, "_tldw_router_registry")


@pytest.mark.unit
def test_minimal_app_import_survives_setup_router_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")

    original_import = builtins.__import__
    existing_main = sys.modules.pop("tldw_Server_API.app.main", None)

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "tldw_Server_API.app.api.v1.endpoints.setup":
            raise ImportError("setup router unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)

    try:
        imported_main = importlib.import_module("tldw_Server_API.app.main")
        assert imported_main.app is not None
        assert any(route.path == "/health" for route in imported_main.app.routes)
    finally:
        sys.modules.pop("tldw_Server_API.app.main", None)
        if existing_main is not None:
            sys.modules["tldw_Server_API.app.main"] = existing_main
