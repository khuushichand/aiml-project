from __future__ import annotations

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
