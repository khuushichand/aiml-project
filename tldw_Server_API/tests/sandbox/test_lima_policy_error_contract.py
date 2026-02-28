from __future__ import annotations

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ROUTES_ENABLE", "sandbox")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_ENFORCER_DENY_ALL_READY", "1")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_ENFORCER_ALLOWLIST_READY", "0")
    return TestClient(app)


def test_lima_policy_unsupported_includes_reasons(monkeypatch) -> None:
    payload = {
        "spec_version": "1.0",
        "runtime": "lima",
        "base_image": "ubuntu:24.04",
        "command": ["echo", "ok"],
        "network_policy": "allowlist",
    }
    with _client(monkeypatch) as client:
        resp = client.post("/api/v1/sandbox/runs", json=payload)
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "policy_unsupported"
        details = data["error"]["details"]
        assert details["runtime"] == "lima"
        assert details["requirement"] == "allowlist"
        assert "strict_allowlist_not_supported" in details["reasons"]


def test_lima_runtime_unavailable_includes_permission_denied_reason(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ROUTES_ENABLE", "sandbox")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_ENFORCER_PERMISSION_DENIED", "1")

    payload = {
        "spec_version": "1.0",
        "runtime": "lima",
        "base_image": "ubuntu:24.04",
        "command": ["echo", "ok"],
        "network_policy": "deny_all",
    }
    with TestClient(app) as client:
        resp = client.post("/api/v1/sandbox/runs", json=payload)
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "runtime_unavailable"
        details = data["error"]["details"]
        assert details["runtime"] == "lima"
        assert details["available"] is False
        assert details["suggested"] == []
        assert "permission_denied_host_enforcement" in details["reasons"]
