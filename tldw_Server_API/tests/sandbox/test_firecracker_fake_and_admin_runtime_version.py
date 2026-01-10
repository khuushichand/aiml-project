from __future__ import annotations

import os
from typing import Any, Dict

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client(monkeypatch) -> TestClient:


     monkeypatch.setenv("TEST_MODE", "1")
    # Enable execution and mark firecracker as available for this test
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "true")
    monkeypatch.setenv("SANDBOX_BACKGROUND_EXECUTION", "false")
    monkeypatch.setenv("TLDW_SANDBOX_FIRECRACKER_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_FIRECRACKER_VERSION", "9.9.9")
    return TestClient(app)


def test_firecracker_fake_exec_and_admin_details_runtime_version(monkeypatch) -> None:


     with _client(monkeypatch) as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "firecracker",
            "base_image": "python:3.11-slim",
            "command": ["python", "-c", "print('ok')"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        j = r.json()
        run_id = j["id"]
        assert j.get("runtime") == "firecracker"
        assert j.get("runtime_version") == "9.9.9"
        # Admin details should include runtime_version as well
        d = client.get(f"/api/v1/sandbox/admin/runs/{run_id}")
        assert d.status_code == 200
        jj = d.json()
        assert jj.get("runtime_version") == "9.9.9"
