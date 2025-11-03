from __future__ import annotations

import os
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.timeout(10)


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "true")
    monkeypatch.setenv("SANDBOX_BACKGROUND_EXECUTION", "false")
    # Make firecracker appear available and set a fake version
    monkeypatch.setenv("TLDW_SANDBOX_FIRECRACKER_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_FIRECRACKER_VERSION", "1.0.0-test")
    # Ensure sandbox router
    existing = os.environ.get("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in existing.split(",") if p.strip()]
    if "sandbox" not in parts:
        parts.append("sandbox")
    monkeypatch.setenv("ROUTES_ENABLE", ",".join(parts))
    from tldw_Server_API.app.main import app
    return TestClient(app)


def _admin_user_dep():
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
    return User(id=1, username="admin", roles=["admin"], is_admin=True)


def test_firecracker_run_succeeds_and_reports_runtime_version(monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
    with _client(monkeypatch) as client:
        client.app.dependency_overrides[get_request_user] = _admin_user_dep
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "firecracker",
            "base_image": "python:3.11-slim",
            "command": ["python", "-c", "print('ok')"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        run_id = r.json()["id"]
        # Admin details should expose runtime_version from firecracker runner
        rd = client.get(f"/api/v1/sandbox/admin/runs/{run_id}")
        assert rd.status_code == 200
        j = rd.json()
        assert j.get("runtime") == "firecracker"
        assert j.get("runtime_version") == "1.0.0-test"
        client.app.dependency_overrides.clear()

