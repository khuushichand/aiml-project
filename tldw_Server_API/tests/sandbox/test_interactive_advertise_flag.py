from __future__ import annotations

import os
from fastapi.testclient import TestClient
from tldw_Server_API.app.core.config import clear_config_cache


def _client(monkeypatch) -> TestClient:
    # Minimal app with only sandbox router to avoid heavy imports
    monkeypatch.setenv("TEST_MODE", "1")
    # Ensure execution is enabled for advertising purposes
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "true")
    # Pretend docker is available (avoid shelling out)
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_AVAILABLE", "1")
    clear_config_cache()
    from fastapi import FastAPI
    from tldw_Server_API.app.api.v1.endpoints.sandbox import router as sandbox_router
    app = FastAPI()
    app.include_router(sandbox_router, prefix="/api/v1")
    return TestClient(app)


def test_interactive_supported_advertised_when_execution_enabled(monkeypatch) -> None:
    with _client(monkeypatch) as client:
        r = client.get("/api/v1/sandbox/runtimes")
        assert r.status_code == 200
        data = r.json()
        docker = next((rt for rt in data.get("runtimes", []) if rt.get("name") == "docker"), None)
        assert docker is not None
        assert docker.get("interactive_supported") is True

