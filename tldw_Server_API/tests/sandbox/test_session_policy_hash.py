from __future__ import annotations

import os
from typing import Any, Dict

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    return TestClient(app)


def test_session_creation_returns_policy_hash() -> None:
    with _client() as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
        }
        r = client.post("/api/v1/sandbox/sessions", json=body)
        assert r.status_code == 200
        j = r.json()
        assert "policy_hash" in j
        assert isinstance(j.get("policy_hash"), (str, type(None)))
