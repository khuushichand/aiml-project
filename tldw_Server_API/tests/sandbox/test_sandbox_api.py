from __future__ import annotations

import os
from typing import Any, Dict
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunStatus, RuntimeType, TrustLevel


def _client(monkeypatch) -> TestClient:


     # Enable test-mode behaviors in auth to avoid API key requirements
    monkeypatch.setenv("TEST_MODE", "1")
    return TestClient(app)


def test_runtimes_discovery_shape(monkeypatch) -> None:


    with _client(monkeypatch) as client:
        r = client.get("/api/v1/sandbox/runtimes")
        assert r.status_code == 200
        data = r.json()
        assert "runtimes" in data and isinstance(data["runtimes"], list)
        assert len(data["runtimes"]) >= 1
        first = data["runtimes"][0]
        for key in [
            "name",
            "available",
            "default_images",
            "max_cpu",
            "max_mem_mb",
            "max_upload_mb",
            "max_log_bytes",
            "workspace_cap_mb",
            "artifact_ttl_hours",
            "supported_spec_versions",
        ]:
            assert key in first


def test_create_session_scaffold(monkeypatch) -> None:


    with _client(monkeypatch) as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "timeout_sec": 60,
        }
        r = client.post("/api/v1/sandbox/sessions", json=body, headers={"Idempotency-Key": "abc-123"})
        assert r.status_code == 200
        j = r.json()
        assert "id" in j and j["runtime"] in {"docker", "firecracker"}
        # Replay with same key/body returns same id
        r2 = client.post("/api/v1/sandbox/sessions", json=body, headers={"Idempotency-Key": "abc-123"})
        assert r2.status_code == 200
        assert r2.json()["id"] == j["id"]
        # Change body with same key triggers 409
        body2 = {**body, "timeout_sec": 61}
        r3 = client.post("/api/v1/sandbox/sessions", json=body2, headers={"Idempotency-Key": "abc-123"})
        assert r3.status_code == 409


def test_create_session_returns_execution_defaults(monkeypatch) -> None:
    with _client(monkeypatch) as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.12-slim",
            "cpu_limit": 1.5,
            "memory_mb": 768,
            "timeout_sec": 77,
            "network_policy": "deny_all",
            "env": {"SESSION_TOKEN": "present"},
            "labels": {"team": "sandbox"},
            "trust_level": "trusted",
        }
        r = client.post("/api/v1/sandbox/sessions", json=body)
        assert r.status_code == 200
        j = r.json()
        assert j["base_image"] == "python:3.12-slim"
        assert j["cpu_limit"] == 1.5
        assert j["memory_mb"] == 768
        assert j["timeout_sec"] == 77
        assert j["network_policy"] == "deny_all"
        assert j["env"] == {"SESSION_TOKEN": "present"}
        assert j["labels"] == {"team": "sandbox"}
        assert j["trust_level"] == "trusted"


def test_start_run_scaffold_returns_completed_with_metadata(monkeypatch) -> None:


    with _client(monkeypatch) as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["python", "-c", "print('hello')"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body, headers={"Idempotency-Key": "idem-run-1"})
        assert r.status_code == 200
        j = r.json()
        assert j["phase"] == "completed"
        # Spec and metadata fields present
        assert j.get("spec_version") == "1.0"
        assert j.get("runtime") in {"docker", "firecracker"}
        # policy_hash may be present; if provided, must be non-empty
        if "policy_hash" in j and j["policy_hash"] is not None:
            assert isinstance(j["policy_hash"], str) and len(j["policy_hash"]) > 0
        # Replay with same key/body returns same run id
        r2 = client.post("/api/v1/sandbox/runs", json=body, headers={"Idempotency-Key": "idem-run-1"})
        assert r2.status_code == 200
        assert r2.json()["id"] == j["id"]
        # Change body with same key triggers 409
        body2 = {**body, "timeout_sec": 6}
        r3 = client.post("/api/v1/sandbox/runs", json=body2, headers={"Idempotency-Key": "idem-run-1"})
        assert r3.status_code == 409


def test_start_run_rejects_missing_session_and_base_image(monkeypatch) -> None:
    with _client(monkeypatch) as client:
        r = client.post(
            "/api/v1/sandbox/runs",
            json={
                "spec_version": "1.0",
                "command": ["python", "-c", "print('hello')"],
            },
        )
        assert r.status_code == 422


def test_start_run_rejects_both_session_and_base_image(monkeypatch) -> None:
    with _client(monkeypatch) as client:
        session_resp = client.post(
            "/api/v1/sandbox/sessions",
            json={
                "spec_version": "1.0",
                "runtime": "docker",
                "base_image": "python:3.11-slim",
            },
        )
        assert session_resp.status_code == 200
        session_id = str(session_resp.json()["id"])

        r = client.post(
            "/api/v1/sandbox/runs",
            json={
                "spec_version": "1.0",
                "session_id": session_id,
                "base_image": "python:3.11-slim",
                "command": ["python", "-c", "print('hello')"],
            },
        )
        assert r.status_code == 422


def test_session_backed_run_inherits_session_defaults(monkeypatch) -> None:
    from tldw_Server_API.app.api.v1.endpoints import sandbox as sb

    captured: dict[str, Any] = {}

    def _fake_start_run_scaffold(*, user_id, spec, spec_version, idem_key, raw_body):
        captured["user_id"] = user_id
        captured["spec"] = spec
        return RunStatus(
            id="run-session-defaults",
            phase=RunPhase.queued,
            spec_version=spec_version,
            runtime=spec.runtime or RuntimeType.docker,
            base_image=spec.base_image,
            session_id=spec.session_id,
            started_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(sb._service, "start_run_scaffold", _fake_start_run_scaffold)

    with _client(monkeypatch) as client:
        session_resp = client.post(
            "/api/v1/sandbox/sessions",
            json={
                "spec_version": "1.0",
                "runtime": "docker",
                "base_image": "python:3.12-slim",
                "cpu_limit": 1.5,
                "memory_mb": 768,
                "timeout_sec": 77,
                "network_policy": "deny_all",
                "env": {"SESSION_TOKEN": "present"},
                "trust_level": "trusted",
            },
        )
        assert session_resp.status_code == 200
        session_id = str(session_resp.json()["id"])

        run_resp = client.post(
            "/api/v1/sandbox/runs",
            json={
                "spec_version": "1.0",
                "session_id": session_id,
                "command": ["python", "-c", "print('hello')"],
            },
        )
        assert run_resp.status_code == 200
        assert run_resp.json()["base_image"] == "python:3.12-slim"

    spec = captured["spec"]
    assert spec.session_id == session_id
    assert spec.runtime == RuntimeType.docker
    assert spec.base_image == "python:3.12-slim"
    assert spec.cpu == 1.5
    assert spec.memory_mb == 768
    assert spec.timeout_sec == 77
    assert spec.network_policy == "deny_all"
    assert spec.env == {"SESSION_TOKEN": "present"}
    assert spec.trust_level == TrustLevel.trusted


def test_delete_session_cancels_and_drains_active_runs(monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "0")

    with _client(monkeypatch) as client:
        session_resp = client.post(
            "/api/v1/sandbox/sessions",
            json={
                "spec_version": "1.0",
                "runtime": "docker",
                "base_image": "python:3.11-slim",
            },
        )
        assert session_resp.status_code == 200
        session_id = str(session_resp.json()["id"])

        run_resp = client.post(
            "/api/v1/sandbox/runs",
            json={
                "spec_version": "1.0",
                "runtime": "docker",
                "session_id": session_id,
                "command": ["python", "-c", "print('queued')"],
                "timeout_sec": 15,
            },
        )
        assert run_resp.status_code == 200
        run_id = str(run_resp.json()["id"])
        assert run_resp.json()["phase"] == "queued"

        delete_resp = client.delete(f"/api/v1/sandbox/sessions/{session_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json().get("ok") is True

        run_after = client.get(f"/api/v1/sandbox/runs/{run_id}")
        assert run_after.status_code == 200
        assert run_after.json().get("phase") == "killed"
