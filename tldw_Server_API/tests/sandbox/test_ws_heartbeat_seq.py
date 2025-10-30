from __future__ import annotations

import os
import asyncio as _asyncio
import time
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app

pytestmark = pytest.mark.timeout(10)

def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    # Disable real execution so WS doesn't end immediately (to receive heartbeats)
    os.environ["SANDBOX_ENABLE_EXECUTION"] = "false"
    os.environ["SANDBOX_BACKGROUND_EXECUTION"] = "true"
    os.environ["TLDW_SANDBOX_DOCKER_FAKE_EXEC"] = "1"
    return TestClient(app)


@pytest.mark.unit
def test_ws_heartbeats_include_seq(monkeypatch: pytest.MonkeyPatch, ws_flush) -> None:
    # Speed up heartbeats by monkeypatching the sandbox asyncio.sleep
    from tldw_Server_API.app.api.v1.endpoints import sandbox as sb

    _orig_sleep = _asyncio.sleep

    async def _fast_sleep(_n: float) -> None:  # pragma: no cover - trivial
        await _orig_sleep(0.01)

    monkeypatch.setattr(sb.asyncio, "sleep", _fast_sleep, raising=True)

    with _client() as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["bash", "-lc", "echo waiting"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        run_id = r.json()["id"]

        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws:
            # Wait for a heartbeat (short deadline; heartbeat sleep patched to ~0.01s)
            deadline = time.time() + 1.0
            saw_heartbeat = False
            last_seq: int | None = None
            while time.time() < deadline:
                msg = ws.receive_json()
                if msg.get("type") == "heartbeat":
                    assert "seq" in msg and isinstance(msg["seq"], int)
                    if last_seq is not None:
                        assert msg["seq"] > last_seq
                    last_seq = msg["seq"]
                    saw_heartbeat = True
                    break
            assert saw_heartbeat, "Did not receive heartbeat with seq in time"
            ws_flush(run_id)
            ws.close()
