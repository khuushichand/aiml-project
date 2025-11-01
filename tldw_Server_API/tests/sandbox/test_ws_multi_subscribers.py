from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi.testclient import TestClient
from tldw_Server_API.app.core.Sandbox.streams import get_hub


def _client() -> TestClient:
    # Ensure quick WS polling and disable synthetic frames for deterministic assertions
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("MINIMAL_TEST_APP", "1")
    os.environ["SANDBOX_WS_POLL_TIMEOUT_SEC"] = "1"
    os.environ["SANDBOX_WS_SYNTHETIC_FRAMES_FOR_TESTS"] = "false"
    # Disable execution/background to avoid runner events
    os.environ["SANDBOX_ENABLE_EXECUTION"] = "false"
    os.environ["SANDBOX_BACKGROUND_EXECUTION"] = "false"
    # Ensure sandbox routes enabled
    existing_enable = os.environ.get("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in existing_enable.split(",") if p.strip()]
    if "sandbox" not in parts:
        parts.append("sandbox")
    os.environ["ROUTES_ENABLE"] = ",".join(parts)
    from tldw_Server_API.app.main import app  # import after env is set
    return TestClient(app)


def _create_run(client: TestClient) -> str:
    body: Dict[str, Any] = {
        "spec_version": "1.0",
        "runtime": "docker",
        "base_image": "python:3.11-slim",
        "command": ["echo", "ok"],
        "timeout_sec": 5,
    }
    r = client.post("/api/v1/sandbox/runs", json=body)
    assert r.status_code == 200
    return r.json()["id"]


def test_ws_multi_subscribers_receive_same_order() -> None:
    with _client() as client:
        run_id = _create_run(client)
        hub = get_hub()
        # Publish a small sequence of frames before any subscriber connects
        hub.publish_event(run_id, "start", {"source": "test"})
        hub.publish_stdout(run_id, b"A\n")
        hub.publish_stdout(run_id, b"B\n")
        hub.publish_event(run_id, "end", {})

        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws1, \
             client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws2:
            frames1: List[Dict[str, Any]] = []
            frames2: List[Dict[str, Any]] = []
            # Read 4 frames from each (start, stdout A, stdout B, end)
            for _ in range(4):
                frames1.append(ws1.receive_json())
                frames2.append(ws2.receive_json())
            # Verify seq monotonic and identical ordering across subscribers
            seqs1 = [f.get("seq") for f in frames1]
            seqs2 = [f.get("seq") for f in frames2]
            assert all(isinstance(s, int) for s in seqs1)
            assert all(isinstance(s, int) for s in seqs2)
            assert seqs1 == sorted(seqs1)
            assert seqs2 == sorted(seqs2)
            assert seqs1 == seqs2


def test_ws_reconnect_drain_buffer() -> None:
    with _client() as client:
        run_id = _create_run(client)
        hub = get_hub()
        # Publish two frames, then connect first subscriber
        hub.publish_event(run_id, "start", {"source": "test"})
        hub.publish_stdout(run_id, b"X\n")

        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws1:
            f1 = ws1.receive_json()
            assert f1.get("type") in {"event", "stdout", "stderr"}
            f2 = ws1.receive_json()
            assert f2.get("type") in {"stdout", "stderr", "event"}

        # Publish more frames and connect a second subscriber later
        hub.publish_stdout(run_id, b"Y\n")
        hub.publish_event(run_id, "end", {})

        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws2:
            frames = [ws2.receive_json(), ws2.receive_json(), ws2.receive_json(), ws2.receive_json()]
            # Should receive at least the buffered frames including the latest 'end'
            types = [f.get("type") for f in frames]
            assert "event" in types and any((f.get("event") == "end") for f in frames if f.get("type") == "event")
            seqs = [f.get("seq") for f in frames]
            assert seqs == sorted(seqs)


def test_ws_multi_subs_live_stream() -> None:
    """Two subscribers connected while frames are being published should observe identical ordering.

    This test simulates a small live stream by publishing frames from a background thread
    while two clients are connected. Both should receive the same seq-ordered frames.
    """
    with _client() as client:
        run_id = _create_run(client)
        hub = get_hub()

        # Connect two subscribers first
        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws1, \
             client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws2:
            import threading, time

            def _publisher():
                try:
                    hub.publish_event(run_id, "start", {"source": "live"})
                    time.sleep(0.02)
                    hub.publish_stdout(run_id, b"L1\n")
                    time.sleep(0.02)
                    hub.publish_stdout(run_id, b"L2\n")
                    time.sleep(0.02)
                    hub.publish_event(run_id, "end", {})
                except Exception:
                    pass

            t = threading.Thread(target=_publisher, daemon=True)
            t.start()

            frames1 = [ws1.receive_json(), ws1.receive_json(), ws1.receive_json(), ws1.receive_json()]
            frames2 = [ws2.receive_json(), ws2.receive_json(), ws2.receive_json(), ws2.receive_json()]

            seqs1 = [f.get("seq") for f in frames1]
            seqs2 = [f.get("seq") for f in frames2]
            assert seqs1 == sorted(seqs1)
            assert seqs2 == sorted(seqs2)
            assert seqs1 == seqs2
