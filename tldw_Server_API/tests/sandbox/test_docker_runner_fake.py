from __future__ import annotations

import os
from typing import Any, Dict

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    # Enable execution but fake docker to avoid host dependency
    os.environ["SANDBOX_ENABLE_EXECUTION"] = "true"
    os.environ["TLDW_SANDBOX_DOCKER_FAKE_EXEC"] = "1"
    return TestClient(app)


def test_docker_fake_exec_path() -> None:
    with _client() as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["python", "-c", "print('ok')"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        j = r.json()
        assert j["phase"] == "completed"
        # In fake mode, message comes from DockerRunner
        assert "message" in j and isinstance(j["message"], str)
