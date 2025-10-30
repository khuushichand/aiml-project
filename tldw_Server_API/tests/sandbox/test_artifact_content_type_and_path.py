from __future__ import annotations

import os
from typing import Any, Dict

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    return TestClient(app)


def test_artifact_content_type_and_invalid_path() -> None:
    with _client() as client:
        # Create a run
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["bash", "-lc", "echo"],
            "timeout_sec": 5,
            "capture_patterns": ["out.txt"],
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        run_id = r.json()["id"]

        # Seed artifact
        from tldw_Server_API.app.api.v1.endpoints import sandbox as sb
        payload = b"hello world"
        sb._service._orch.store_artifacts(run_id, {"out.txt": payload})  # type: ignore[attr-defined]

        # Full download: expect content-type text/plain
        r2 = client.get(f"/api/v1/sandbox/runs/{run_id}/artifacts/out.txt")
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("text/plain")
        assert r2.content == payload

        # Invalid path: traversal
        r3 = client.get(f"/api/v1/sandbox/runs/{run_id}/artifacts/../secret.txt")
        assert r3.status_code == 400
        # Invalid path: absolute
        r4 = client.get(f"/api/v1/sandbox/runs/{run_id}/artifacts//etc/passwd")
        assert r4.status_code == 400

        # Invalid range header → 416
        r5 = client.get(
            f"/api/v1/sandbox/runs/{run_id}/artifacts/out.txt",
            headers={"Range": "bytes=100-50"},
        )
        assert r5.status_code == 416
