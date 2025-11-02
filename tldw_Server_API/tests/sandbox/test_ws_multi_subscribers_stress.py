from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Tuple

from fastapi.testclient import TestClient
from tldw_Server_API.app.core.Sandbox.streams import get_hub
from uuid import uuid4


def _client() -> TestClient:
    # Ensure quick WS polling and deterministic behavior
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("MINIMAL_TEST_APP", "1")
    os.environ["SANDBOX_WS_POLL_TIMEOUT_SEC"] = "1"
    os.environ["SANDBOX_WS_SYNTHETIC_FRAMES_FOR_TESTS"] = "false"
    os.environ["SANDBOX_ENABLE_EXECUTION"] = "false"
    os.environ["SANDBOX_BACKGROUND_EXECUTION"] = "false"
    # Enable sandbox routes
    existing_enable = os.environ.get("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in existing_enable.split(",") if p.strip()]
    if "sandbox" not in parts:
        parts.append("sandbox")
    os.environ["ROUTES_ENABLE"] = ",".join(parts)
    from tldw_Server_API.app.main import app  # import after env is set
    return TestClient(app)


def _new_run_id() -> str:
    return f"run-{uuid4()}"


def test_ws_multi_subscribers_burst_identical_ordering() -> None:
    with _client() as client:
        run_id = _new_run_id()
        hub = get_hub()

        # Connect two subscribers
        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws1, \
             client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws2:

            def _publisher() -> None:
                # Let exceptions surface to fail the test if publishing breaks
                hub.publish_event(run_id, "start", {"source": "stress-multi"})
                for i in range(200):
                    hub.publish_stdout(run_id, f"o{i}\n".encode("utf-8"))
                    hub.publish_stderr(run_id, f"e{i}\n".encode("utf-8"))
                hub.publish_event(run_id, "end", {})

            t = threading.Thread(target=_publisher, daemon=True)
            t.start()

            def _drain(ws) -> Tuple[List[Dict[str, Any]], int]:
                frames: List[Dict[str, Any]] = []
                end_seen = 0
                # Cap reads to avoid hangs; should break on 'end'
                for _ in range(450):
                    f = ws.receive_json()
                    frames.append(f)
                    if f.get("type") == "event" and f.get("event") == "end":
                        end_seen += 1
                        break
                return frames, end_seen

            frames1, end1 = _drain(ws1)
            frames2, end2 = _drain(ws2)

            assert end1 == 1 and end2 == 1

            # Extract seq and ensure identical ordering and strictly increasing
            seqs1 = [int(f["seq"]) for f in frames1 if isinstance(f.get("seq"), int)]
            seqs2 = [int(f["seq"]) for f in frames2 if isinstance(f.get("seq"), int)]
            assert seqs1 == sorted(seqs1) and len(seqs1) == len(set(seqs1))
            assert seqs2 == sorted(seqs2) and len(seqs2) == len(set(seqs2))
            assert seqs1 == seqs2
