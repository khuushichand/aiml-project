from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    os.environ["SANDBOX_ENABLE_EXECUTION"] = "true"
    os.environ["SANDBOX_BACKGROUND_EXECUTION"] = "true"
    os.environ["TLDW_SANDBOX_DOCKER_FAKE_EXEC"] = "1"
    return TestClient(app)


def test_ws_stream_fake_exec_start_end() -> None:
    with _client() as client:
        # Start a run
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["python", "-c", "print('hello')"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        run_id = r.json()["id"]
        # Subscribe to WS
        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws:
            seen_start = False
            seen_end = False
            deadline = time.time() + 5
            while time.time() < deadline and not seen_end:
                msg = ws.receive_json()
                if msg.get("type") == "event" and msg.get("event") == "start":
                    seen_start = True
                if msg.get("type") == "event" and msg.get("event") == "end":
                    seen_end = True
            assert seen_start and seen_end
