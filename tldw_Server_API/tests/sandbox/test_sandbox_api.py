from __future__ import annotations

import os
from typing import Any, Dict

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client() -> TestClient:
    # Enable test-mode behaviors in auth to avoid API key requirements
    os.environ.setdefault("TEST_MODE", "1")
    return TestClient(app)


def test_runtimes_discovery_shape() -> None:
    with _client() as client:
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


def test_create_session_scaffold() -> None:
    with _client() as client:
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


def test_start_run_scaffold_returns_completed_with_metadata() -> None:
    with _client() as client:
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
