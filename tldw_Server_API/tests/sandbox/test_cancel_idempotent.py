from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    os.environ["SANDBOX_ENABLE_EXECUTION"] = "false"
    os.environ["SANDBOX_BACKGROUND_EXECUTION"] = "true"
    os.environ["TLDW_SANDBOX_DOCKER_FAKE_EXEC"] = "1"
    return TestClient(app)


def test_cancel_idempotent() -> None:
    with _client() as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["bash", "-lc", "echo X"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        run_id = r.json()["id"]

        # First cancel should return cancelled=True
        r1 = client.post(f"/api/v1/sandbox/runs/{run_id}/cancel")
        assert r1.status_code == 200
        assert r1.json().get("cancelled") is True

        # Second cancel should be idempotent and return cancelled=False
        r2 = client.post(f"/api/v1/sandbox/runs/{run_id}/cancel")
        assert r2.status_code == 200
        assert r2.json().get("cancelled") is False
