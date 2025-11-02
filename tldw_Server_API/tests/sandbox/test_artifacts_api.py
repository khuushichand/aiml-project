from __future__ import annotations

import os
from typing import Any, Dict

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    # Allow scaffold execution path and fake docker
    os.environ.setdefault("SANDBOX_ENABLE_EXECUTION", "true")
    os.environ.setdefault("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "1")
    return TestClient(app)


def test_artifacts_list_and_download_roundtrip() -> None:
    with _client() as client:
        # Start a run (fake exec)
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["python", "-c", "print('ok')"],
            "timeout_sec": 5,
            "capture_patterns": ["results.txt", "data.bin"],
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        run = r.json()
        run_id = run["id"]

        # Inject artifacts via service orchestrator
        from tldw_Server_API.app.api.v1.endpoints.sandbox import _service  # type: ignore

        payload = {
            "results.txt": b"hello world",
            "data.bin": bytes([0, 1, 2, 3, 4]),
        }
        _service._orch.store_artifacts(run_id, payload)  # type: ignore[attr-defined]

        # List artifacts
        lr = client.get(f"/api/v1/sandbox/runs/{run_id}/artifacts")
        assert lr.status_code == 200
        items = lr.json().get("items")
        assert isinstance(items, list)
        names = {i.get("path") for i in items}
        assert "results.txt" in names and "data.bin" in names

        # Download and check content
        dr = client.get(f"/api/v1/sandbox/runs/{run_id}/artifacts/results.txt")
        assert dr.status_code == 200
        assert dr.content == b"hello world"
