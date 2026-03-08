from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("ROUTES_ENABLE", "sandbox")
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "false")
    monkeypatch.setenv("SANDBOX_BACKGROUND_EXECUTION", "false")
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "1")

    from tldw_Server_API.app.api.v1.endpoints.sandbox import router as sandbox_router

    app = FastAPI()
    app.include_router(sandbox_router, prefix="/api/v1")
    return TestClient(app)


@pytest.mark.unit
def test_started_metric_not_emitted_for_runtime_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    import tldw_Server_API.app.api.v1.endpoints.sandbox as sandbox_endpoint

    def _inc(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(sandbox_endpoint, "increment_counter", _inc, raising=True)
    monkeypatch.setenv("TLDW_SANDBOX_FIRECRACKER_AVAILABLE", "0")
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_AVAILABLE", "1")

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/v1/sandbox/runs",
            json={
                "spec_version": "1.0",
                "runtime": "firecracker",
                "base_image": "python:3.11-slim",
                "command": ["bash", "-lc", "echo"],
                "timeout_sec": 5,
            },
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "runtime_unavailable"
    assert not any(args and args[0] == "sandbox_runs_started_total" for args, _kwargs in calls)


@pytest.mark.unit
def test_started_metric_emitted_for_accepted_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    import tldw_Server_API.app.api.v1.endpoints.sandbox as sandbox_endpoint

    def _inc(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(sandbox_endpoint, "increment_counter", _inc, raising=True)

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/v1/sandbox/runs",
            json={
                "spec_version": "1.0",
                "runtime": "docker",
                "base_image": "python:3.11-slim",
                "command": ["bash", "-lc", "echo ok"],
                "timeout_sec": 5,
            },
        )

    assert response.status_code == 200
    assert any(args and args[0] == "sandbox_runs_started_total" for args, _kwargs in calls)
