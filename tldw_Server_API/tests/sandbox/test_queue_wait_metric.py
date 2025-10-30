from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from fastapi.testclient import TestClient
import pytest

from tldw_Server_API.app.main import app


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    os.environ["SANDBOX_ENABLE_EXECUTION"] = "true"
    os.environ["SANDBOX_BACKGROUND_EXECUTION"] = "true"
    os.environ["TLDW_SANDBOX_DOCKER_FAKE_EXEC"] = "1"
    return TestClient(app)


@pytest.mark.unit
def test_queue_wait_metric_emitted(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[Tuple[Tuple[Any, ...], Dict[str, Any]]] = []

    # Patch the observe_histogram reference in service module
    import tldw_Server_API.app.core.Sandbox.service as svc

    def _obs(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(svc, "observe_histogram", _obs, raising=True)

    with _client() as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["bash", "-lc", "echo q"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200

    # Expect at least one call to sandbox_queue_wait_seconds
    names = [a[0] if a else None for (a, _k) in calls]
    assert any(name == "sandbox_queue_wait_seconds" for name in names)
    # Validate kwargs of first matching call
    for (a, k) in calls:
        if a and a[0] == "sandbox_queue_wait_seconds":
            assert "value" in k and isinstance(k["value"], float)
            assert "labels" in k and isinstance(k["labels"], dict)
            break
