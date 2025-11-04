from __future__ import annotations

from typing import Any, Dict

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "false")
    monkeypatch.setenv("SANDBOX_BACKGROUND_EXECUTION", "true")
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "1")
    return TestClient(app)


def _seed_run_and_artifact(client: TestClient) -> tuple[str, str]:
    body: Dict[str, Any] = {
        "spec_version": "1.0",
        "runtime": "docker",
        "base_image": "python:3.11-slim",
        "command": ["bash", "-lc", "echo done"],
        "timeout_sec": 5,
        "capture_patterns": ["out.txt"],
    }
    r = client.post("/api/v1/sandbox/runs", json=body)
    assert r.status_code == 200
    run_id = r.json()["id"]

    from tldw_Server_API.app.api.v1.endpoints import sandbox as sb

    payload = b"0123456789"
    sb._service._orch.store_artifacts(run_id, {"out.txt": payload})  # type: ignore[attr-defined]
    return run_id, "out.txt"


def test_artifact_download_multiple_ranges_unsupported(monkeypatch) -> None:
    with _client(monkeypatch) as client:
        run_id, path = _seed_run_and_artifact(client)
        r = client.get(
            f"/api/v1/sandbox/runs/{run_id}/artifacts/{path}",
            headers={"Range": "bytes=0-1,3-4"},
        )
        assert r.status_code == 416
        assert r.headers.get("Content-Range") == "bytes */10"


def test_artifact_download_invalid_range_returns_416(monkeypatch) -> None:
    with _client(monkeypatch) as client:
        run_id, path = _seed_run_and_artifact(client)
        # Start > end
        r = client.get(
            f"/api/v1/sandbox/runs/{run_id}/artifacts/{path}",
            headers={"Range": "bytes=7-5"},
        )
        assert r.status_code == 416
        assert r.headers.get("Content-Range") == "bytes */10"

