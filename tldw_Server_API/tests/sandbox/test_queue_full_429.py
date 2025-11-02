from __future__ import annotations

import os
from typing import Any, Dict

from fastapi.testclient import TestClient


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("MINIMAL_TEST_APP", "1")
    # Disable execution to isolate queue path
    os.environ.setdefault("SANDBOX_ENABLE_EXECUTION", "false")
    # Force queue capacity to zero to trigger 429
    os.environ["SANDBOX_QUEUE_MAX_LENGTH"] = "0"
    # Ensure sandbox routes are enabled
    existing_enable = os.environ.get("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in existing_enable.split(",") if p.strip()]
    if "sandbox" not in parts:
        parts.append("sandbox")
    os.environ["ROUTES_ENABLE"] = ",".join(parts)
    from tldw_Server_API.app.main import app  # import after env configured
    return TestClient(app)


def test_queue_full_returns_429_retry_after() -> None:
    with _client() as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["echo", "hi"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 429
        # Check Retry-After header and error shape
        ra = r.headers.get("Retry-After")
        assert ra is not None and int(ra) >= 1
        j = r.json()
        assert j.get("error", {}).get("code") == "queue_full"
