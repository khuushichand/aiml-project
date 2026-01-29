from __future__ import annotations

import os
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client(monkeypatch) -> TestClient:


    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ROUTES_ENABLE", "sandbox")
    # Force Firecracker to appear available while real mode is enabled
    monkeypatch.setenv("SANDBOX_FIRECRACKER_ENABLE_REAL", "1")
    monkeypatch.setenv("TLDW_SANDBOX_FIRECRACKER_AVAILABLE", "1")
    # Ensure no kernel/rootfs configured
    monkeypatch.delenv("SANDBOX_FC_KERNEL_PATH", raising=False)
    monkeypatch.delenv("SANDBOX_FC_ROOTFS_PATH", raising=False)
    return TestClient(app)


def test_run_firecracker_missing_kernel_rootfs_returns_400(monkeypatch) -> None:


    with _client(monkeypatch) as client:
        body = {
            "spec_version": "1.0",
            "runtime": "firecracker",
            "base_image": "python:3.11-slim",
            "command": ["bash", "-lc", "echo ok"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 400
        j = r.json()
        assert j.get("error", {}).get("code") == "invalid_firecracker_config"
        details = j.get("error", {}).get("details", {})
        assert details.get("runtime") == "firecracker"
        errors = details.get("errors", {})
        assert errors.get("kernel_path") == "missing"
        assert errors.get("rootfs_path") == "missing"


def test_session_firecracker_missing_kernel_rootfs_returns_400(monkeypatch) -> None:


    with _client(monkeypatch) as client:
        body = {
            "spec_version": "1.0",
            "runtime": "firecracker",
            "base_image": "python:3.11-slim",
        }
        r = client.post("/api/v1/sandbox/sessions", json=body)
        assert r.status_code == 400
        j = r.json()
        assert j.get("error", {}).get("code") == "invalid_firecracker_config"
