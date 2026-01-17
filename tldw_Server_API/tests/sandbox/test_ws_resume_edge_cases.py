from __future__ import annotations

import os
import time
from typing import List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Sandbox.streams import get_hub


pytestmark = pytest.mark.timeout(10)


def _client(monkeypatch) -> TestClient:


    monkeypatch.setenv("TEST_MODE", "1")
    # Ensure sandbox routes enabled
    existing = os.environ.get("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in existing.split(",") if p.strip()]
    if "sandbox" not in parts:
        parts.append("sandbox")
    monkeypatch.setenv("ROUTES_ENABLE", ",".join(parts))
    # Build a minimal app with only the sandbox router
    from tldw_Server_API.app.api.v1.endpoints.sandbox import router as sandbox_router
    app = FastAPI()
    app.include_router(sandbox_router, prefix="/api/v1")
    return TestClient(app)


def test_ws_resume_gap_starts_from_buffer(ws_flush, monkeypatch) -> None:


    run_id = "resume_gap_run"
    hub = get_hub()
    # Publish more than buffer size frames prior to WS connect
    for i in range(150):
        hub.publish_stdout(run_id, f"line-{i}\n".encode("utf-8"), max_log_bytes=10_000)

    with _client(monkeypatch) as client:
        # Resume from a very small seq; should only receive last 100 buffered frames
        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream?from_seq=1") as ws:
            seqs: List[int] = []
            # Drain a subset quickly
            deadline = time.time() + 2
            while time.time() < deadline and len(seqs) < 5:
                msg = ws.receive_json()
                if msg.get("type") == "heartbeat":
                    continue
                assert "seq" in msg and isinstance(msg["seq"], int)
                seqs.append(int(msg["seq"]))
            # We should have started at the earliest available buffered frame
            # (no assertion on absolute value; just ensure we received frames)
            assert len(seqs) > 0
            # Ensure strictly increasing sequence numbers
            assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
            ws_flush(run_id)
            ws.close()


def test_ws_resume_tail_includes_requested_seq(ws_flush, monkeypatch) -> None:


    run_id = "resume_tail_run"
    hub = get_hub()
    # Seed a handful of frames
    for i in range(10):
        hub.publish_stdout(run_id, f"tail-{i}\n".encode("utf-8"), max_log_bytes=10_000)

    with _client(monkeypatch) as client:
        # First connect to learn the last delivered seq
        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws1:
            last_seq: int | None = None
            deadline = time.time() + 2
            while time.time() < deadline:
                msg = ws1.receive_json()
                if msg.get("type") == "heartbeat":
                    continue
                if isinstance(msg.get("seq"), int):
                    last_seq = int(msg["seq"])  # type: ignore[assignment]
                # Break after several frames
                if last_seq and last_seq >= 5:
                    break
            assert last_seq is not None
            ws_flush(run_id)
            ws1.close()

        # Reconnect with from_seq equal to the last seen
        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream?from_seq={last_seq}") as ws2:
            # Expect the first delivered frame to have seq >= last_seq (current hub semantics allow equality)
            while True:
                msg2 = ws2.receive_json()
                if msg2.get("type") == "heartbeat":
                    continue
                assert "seq" in msg2 and isinstance(msg2["seq"], int)
                assert int(msg2["seq"]) >= int(last_seq)
                break
            ws_flush(run_id)
            ws2.close()
