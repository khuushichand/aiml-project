from __future__ import annotations

import os
from typing import List

from fastapi.testclient import TestClient
import pytest

from tldw_Server_API.app.core.Sandbox.streams import get_hub


pytestmark = pytest.mark.timeout(10)


def _client(monkeypatch) -> TestClient:


    monkeypatch.setenv("TEST_MODE", "1")
    # Ensure sandbox router enabled
    existing = os.environ.get("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in existing.split(",") if p.strip()]
    if "sandbox" not in parts:
        parts.append("sandbox")
    monkeypatch.setenv("ROUTES_ENABLE", ",".join(parts))
    from tldw_Server_API.app.main import app
    return TestClient(app)


def test_ws_resume_from_seq_replays_only_newer(ws_flush, monkeypatch) -> None:


    run_id = "resume_seq_run1"
    hub = get_hub()
    # Publish a handful of frames before connecting
    hub.publish_event(run_id, "start", {"n": 1})
    hub.publish_stdout(run_id, b"hello", max_log_bytes=1024)
    hub.publish_stdout(run_id, b"world", max_log_bytes=1024)
    hub.publish_event(run_id, "end", {"n": 2})

    with _client(monkeypatch) as client:
        # Ask to resume from seq=3; subscribe should only deliver frames with seq>=3
        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream?from_seq=3") as ws:
            seqs: List[int] = []
            for _ in range(4):
                msg = ws.receive_json()
                if msg.get("type") == "heartbeat":
                    continue
                assert "seq" in msg and isinstance(msg["seq"], int)
                seqs.append(int(msg["seq"]))
                # We expect at least one delivered
                if len(seqs) >= 1 and msg.get("type") == "event" and msg.get("event") == "end":
                    break
            # Ensure at least one non-heartbeat frame was received
            assert len(seqs) >= 1
            # All delivered frames should be >= requested from_seq
            assert all(s >= 3 for s in seqs)
            ws_flush(run_id)
            ws.close()
