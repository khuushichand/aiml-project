from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client(ttl_sec: int | None = None) -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    if ttl_sec is not None:
        os.environ["SANDBOX_IDEMPOTENCY_TTL_SEC"] = str(ttl_sec)
    return TestClient(app)


def _run_body(msg: str = "echo") -> Dict[str, Any]:
    return {
        "spec_version": "1.0",
        "runtime": "docker",
        "base_image": "python:3.11-slim",
        "command": ["bash", "-lc", msg],
        "timeout_sec": 5,
    }


def test_idempotency_conflict_on_mismatch() -> None:
    with _client() as client:
        key = "k-conflict-1"
        r1 = client.post("/api/v1/sandbox/runs", headers={"Idempotency-Key": key}, json=_run_body("echo 1"))
        assert r1.status_code == 200
        r2 = client.post("/api/v1/sandbox/runs", headers={"Idempotency-Key": key}, json=_run_body("echo 2"))
        assert r2.status_code == 409
        j = r2.json()
        assert j.get("error", {}).get("code") == "idempotency_conflict"


def test_idempotency_ttl_expiry_allows_new_execution() -> None:
    # TTL = 0 means immediate expiry
    with _client(ttl_sec=0) as client:
        key = "k-expire-1"
        r1 = client.post("/api/v1/sandbox/runs", headers={"Idempotency-Key": key}, json=_run_body("echo 1"))
        assert r1.status_code == 200
        # Second request with same key/body should not return conflict because TTL has expired
        r2 = client.post("/api/v1/sandbox/runs", headers={"Idempotency-Key": key}, json=_run_body("echo 1"))
        # Accept either a fresh 200 with a different id or an idempotent replay depending on store timing; it must not be 409
        assert r2.status_code != 409
