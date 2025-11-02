from __future__ import annotations

import os
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    # Ensure sandbox routes are enabled in case route gating is active
    os.environ.setdefault("ROUTES_ENABLE", "sandbox")
    # Make firecracker appear unavailable regardless of host
    os.environ["TLDW_SANDBOX_FIRECRACKER_AVAILABLE"] = "0"
    return TestClient(app)


def test_run_firecracker_unavailable_returns_503() -> None:
    with _client() as client:
        body = {
            "spec_version": "1.0",
            "runtime": "firecracker",
            "base_image": "python:3.11-slim",
            "command": ["bash", "-lc", "echo"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 503
        j = r.json()
        assert j.get("error", {}).get("code") == "runtime_unavailable"
        d = j.get("error", {}).get("details", {})
        assert d.get("runtime") == "firecracker"
        assert d.get("available") is False
        assert isinstance(d.get("suggested"), list) and "docker" in d.get("suggested")


def test_session_firecracker_unavailable_returns_503() -> None:
    with _client() as client:
        body = {
            "spec_version": "1.0",
            "runtime": "firecracker",
            "base_image": "python:3.11-slim",
        }
        r = client.post("/api/v1/sandbox/sessions", json=body)
        assert r.status_code == 503
        j = r.json()
        assert j.get("error", {}).get("code") == "runtime_unavailable"
        d = j.get("error", {}).get("details", {})
        assert d.get("runtime") == "firecracker"
        assert d.get("available") is False
        assert isinstance(d.get("suggested"), list) and "docker" in d.get("suggested")

