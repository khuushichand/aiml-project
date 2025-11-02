from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List

from fastapi.testclient import TestClient
from tldw_Server_API.app.core.Sandbox.streams import get_hub
from uuid import uuid4


def _client() -> TestClient:
    # Fast WS poll and deterministic behavior
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("MINIMAL_TEST_APP", "1")
    os.environ["SANDBOX_WS_POLL_TIMEOUT_SEC"] = "1"
    # Disable synthetic frames to assert true ordering
    os.environ["SANDBOX_WS_SYNTHETIC_FRAMES_FOR_TESTS"] = "false"
    # No actual execution
    os.environ["SANDBOX_ENABLE_EXECUTION"] = "false"
    os.environ["SANDBOX_BACKGROUND_EXECUTION"] = "false"
    # Ensure sandbox routes are enabled
    existing_enable = os.environ.get("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in existing_enable.split(",") if p.strip()]
    if "sandbox" not in parts:
        parts.append("sandbox")
    os.environ["ROUTES_ENABLE"] = ",".join(parts)
    from tldw_Server_API.app.main import app  # import after env vars set
    return TestClient(app)


def _new_run_id() -> str:
    # The WS stream endpoint does not require the run to be registered
    # in the store; it subscribes to the hub by run_id. We can generate
    # a fresh identifier and publish frames to that channel directly.
    return f"run-{uuid4()}"


def test_ws_burst_stdout_stderr_order_and_types() -> None:
    with _client() as client:
        run_id = _new_run_id()
        hub = get_hub()

        # Publish a large burst of mixed stdout/stderr while a client is connected
        with client.websocket_connect(f"/api/v1/sandbox/runs/{run_id}/stream") as ws:
            def _publisher() -> None:
                hub.publish_event(run_id, "start", {"source": "stress"})
                # Alternate stdout/stderr bursts
                for i in range(100):
                    hub.publish_stdout(run_id, f"out-{i}\n".encode("utf-8"))
                    hub.publish_stderr(run_id, f"err-{i}\n".encode("utf-8"))
                hub.publish_event(run_id, "end", {})

            t = threading.Thread(target=_publisher, daemon=True)
            t.start()

            frames: List[Dict[str, Any]] = []
            # read until we get an end event or a reasonable cap
            for _ in range(210):  # 100 out + 100 err + start + end + a few heartbeats possibly
                f = ws.receive_json()
                frames.append(f)
                if f.get("type") == "event" and f.get("event") == "end":
                    break

            # sanity: received some frames and proper end
            assert any(fr.get("type") == "event" and fr.get("event") == "end" for fr in frames)
            types = [fr.get("type") for fr in frames]
            # Ensure both stdout and stderr are present
            assert "stdout" in types and "stderr" in types
            # Ensure seq is strictly increasing
            seqs = [fr.get("seq") for fr in frames if isinstance(fr.get("seq"), int)]
            assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))
