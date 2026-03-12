from __future__ import annotations

import os
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client(monkeypatch) -> TestClient:


    monkeypatch.setenv("TEST_MODE", "1")
    # Ensure sandbox routes are enabled in case route gating is active
    monkeypatch.setenv("ROUTES_ENABLE", "sandbox")
    # Make firecracker appear unavailable regardless of host
    monkeypatch.setenv("TLDW_SANDBOX_FIRECRACKER_AVAILABLE", "0")
    # Keep fallback suggestion behavior deterministic in tests.
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_AVAILABLE", "1")
    return TestClient(app)


def test_run_firecracker_unavailable_returns_503(monkeypatch) -> None:


    with _client(monkeypatch) as client:
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


def test_session_firecracker_unavailable_returns_503(monkeypatch) -> None:


    with _client(monkeypatch) as client:
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


def test_firecracker_unavailable_without_docker_has_empty_suggestions(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ROUTES_ENABLE", "sandbox")
    monkeypatch.setenv("TLDW_SANDBOX_FIRECRACKER_AVAILABLE", "0")
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_AVAILABLE", "0")

    with TestClient(app) as client:
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
        d = j.get("error", {}).get("details", {})
        assert d.get("runtime") == "firecracker"
        assert d.get("suggested") == []


def test_vz_linux_unavailable_returns_503_without_fallback_suggestions(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ROUTES_ENABLE", "sandbox")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_LINUX_AVAILABLE", "0")

    with TestClient(app) as client:
        body = {
            "spec_version": "1.0",
            "runtime": "vz_linux",
            "base_image": "ubuntu-24.04",
            "command": ["echo", "ok"],
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 503
        j = r.json()
        d = j.get("error", {}).get("details", {})
        assert d.get("runtime") == "vz_linux"
        assert d.get("available") is False
        assert d.get("suggested") == []


def test_vz_macos_unavailable_returns_503_without_fallback_suggestions(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ROUTES_ENABLE", "sandbox")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_MACOS_AVAILABLE", "0")

    with TestClient(app) as client:
        body = {
            "spec_version": "1.0",
            "runtime": "vz_macos",
            "base_image": "macos-15",
            "command": ["echo", "ok"],
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 503
        j = r.json()
        d = j.get("error", {}).get("details", {})
        assert d.get("runtime") == "vz_macos"
        assert d.get("available") is False
        assert d.get("suggested") == []


def test_seatbelt_unavailable_returns_503_without_fallback_suggestions(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ROUTES_ENABLE", "sandbox")
    monkeypatch.setenv("TLDW_SANDBOX_SEATBELT_AVAILABLE", "0")

    with TestClient(app) as client:
        body = {
            "spec_version": "1.0",
            "runtime": "seatbelt",
            "base_image": "host-local",
            "command": ["echo", "ok"],
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 503
        j = r.json()
        d = j.get("error", {}).get("details", {})
        assert d.get("runtime") == "seatbelt"
        assert d.get("available") is False
        assert d.get("suggested") == []
