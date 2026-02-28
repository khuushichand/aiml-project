from __future__ import annotations

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ROUTES_ENABLE", "sandbox")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_AVAILABLE", "0")
    return TestClient(app)


def test_explicit_lima_run_unavailable_has_no_fallback_suggestions(monkeypatch) -> None:
    with _client(monkeypatch) as client:
        body = {
            "spec_version": "1.0",
            "runtime": "lima",
            "base_image": "ubuntu:24.04",
            "command": ["echo", "ok"],
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 503
        j = r.json()
        assert j.get("error", {}).get("code") == "runtime_unavailable"
        details = j.get("error", {}).get("details", {})
        assert details.get("runtime") == "lima"
        assert details.get("suggested") == []


def test_explicit_lima_session_unavailable_has_no_fallback_suggestions(monkeypatch) -> None:
    with _client(monkeypatch) as client:
        body = {
            "spec_version": "1.0",
            "runtime": "lima",
            "base_image": "ubuntu:24.04",
        }
        r = client.post("/api/v1/sandbox/sessions", json=body)
        assert r.status_code == 503
        j = r.json()
        assert j.get("error", {}).get("code") == "runtime_unavailable"
        details = j.get("error", {}).get("details", {})
        assert details.get("runtime") == "lima"
        assert details.get("suggested") == []

