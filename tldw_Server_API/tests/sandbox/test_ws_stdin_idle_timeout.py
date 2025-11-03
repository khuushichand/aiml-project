from __future__ import annotations

import os
import time
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.timeout(10)


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "true")
    monkeypatch.setenv("SANDBOX_BACKGROUND_EXECUTION", "true")
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "1")
    # Ensure sandbox router active
    existing_enable = os.environ.get("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in existing_enable.split(",") if p.strip()]
    if "sandbox" not in parts:
        parts.append("sandbox")
    monkeypatch.setenv("ROUTES_ENABLE", ",".join(parts))
    from tldw_Server_API.app.main import app as _app
    return TestClient(_app)


def test_ws_stdin_idle_timeout_emits_truncated_and_closes(ws_flush, monkeypatch) -> None:
    with _client(monkeypatch) as client:
        body: Dict[str, Any] = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["python", "-c", "print('idle')"],
            "timeout_sec": 5,
            "interactive": True,
            "stdin_idle_timeout_sec": 1,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        run_id = r.json()["id"]

        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws:
            # Do not send any stdin frames; wait for idle timeout
            saw_idle_notice = False
            closed_by_idle = False
            deadline = time.time() + 3
            while time.time() < deadline:
                try:
                    msg = ws.receive_json()
                except Exception:
                    # Closed by server due to idle timeout before frame delivery
                    closed_by_idle = True
                    break
                if msg.get("type") == "heartbeat":
                    continue
                if msg.get("type") == "truncated" and msg.get("reason") == "stdin_idle":
                    saw_idle_notice = True
                    # Next receive should detect close soon
                    try:
                        _ = ws.receive_json()
                    except Exception:
                        closed_by_idle = True
                    break
            assert saw_idle_notice or closed_by_idle, "Expected truncated(stdin_idle) or idle-close"
            ws_flush(run_id)
            # Connection is expected to be closed by server; ensure it does not hang
            try:
                ws.close()
            except Exception:
                pass
