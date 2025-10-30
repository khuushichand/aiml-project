from __future__ import annotations

import os
import time
from typing import List

from fastapi.testclient import TestClient
import pytest

pytestmark = pytest.mark.timeout(10)

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.Sandbox.streams import get_hub


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    return TestClient(app)


def test_ws_truncated_frame_behavior(ws_flush) -> None:
    with _client() as client:
        run_id = "ws_trunc_1"
        hub = get_hub()
        # Publish two chunks with a small cap: first consumes the cap (5 bytes),
        # second triggers a truncated frame without adding more data
        hub.publish_stdout(run_id, b"0123456789", max_log_bytes=5)
        hub.publish_stdout(run_id, b"more", max_log_bytes=5)

        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws:
            # First frame should be stdout, second should be truncated
            first = ws.receive_json()
            second = ws.receive_json()
            assert first.get("type") == "stdout"
            assert second.get("type") == "truncated" and second.get("reason") == "log_cap"
            ws_flush(run_id)
            ws.close()


def test_ws_binary_stdout_base64_encoding(ws_flush) -> None:
    with _client() as client:
        run_id = "ws_bin_1"
        hub = get_hub()
        # Non-UTF8 bytes should be base64 encoded
        hub.publish_stdout(run_id, b"\xff\xfe\xfd", max_log_bytes=1024)

        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws:
            msg = ws.receive_json()
            assert msg.get("type") in ("stdout", "stderr")
            assert msg.get("encoding") == "base64"
            data = msg.get("data")
            assert isinstance(data, str) and len(data) > 0
            ws_flush(run_id)
            ws.close()


@pytest.mark.unit
def test_ws_heartbeats_include_seq_consolidated(ws_flush):
    # Avoid relying on server's background heartbeat loop; publish via hub directly
    with _client() as client:
        run_id = "ws_hb_seq_1"
        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws:
            hub = get_hub()
            hub.publish_heartbeat(run_id)
            msg = ws.receive_json()
            assert msg.get("type") == "heartbeat"
            assert "seq" in msg and isinstance(msg["seq"], int)
            ws_flush(run_id)
            ws.close()
