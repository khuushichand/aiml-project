import os
import json
import time
import threading
import tempfile
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
    get_unified_evaluation_service_for_user,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def _auth_headers(client: TestClient):
    # In TEST_MODE + single_user, any token works; include CSRF token if present
    csrf = getattr(client, "csrf_token", "")
    return {"X-API-KEY": "test-token", "X-CSRF-Token": csrf}


@pytest.mark.unit
def test_embeddings_abtest_events_sse_smoke_heartbeat_and_done():
    # Use a per-test DB file for Evaluations to avoid cross-test interference
    with tempfile.NamedTemporaryFile(suffix="_evals.db", delete=False) as f:
        eval_db_path = f.name

    try:
        # Configure fast heartbeats in data mode for reliable detection
        os.environ.setdefault("TEST_MODE", "1")
        os.environ.setdefault("STREAM_HEARTBEAT_MODE", "data")
        os.environ.setdefault("STREAM_HEARTBEAT_INTERVAL_S", "0.05")
        os.environ.setdefault("EVALUATIONS_TEST_DB_PATH", eval_db_path)

        with TestClient(app) as client:
            # Get CSRF token cookie (some deployments may require it)
            resp = client.get("/api/v1/health")
            client.csrf_token = resp.cookies.get("csrf_token", "")

            # 1) Create a minimal A/B test
            create_payload = {
                "name": "sse_smoke",
                "config": {
                    "arms": [{"provider": "openai", "model": "text-embedding-3-small"}],
                    "media_ids": [],
                    "retrieval": {"k": 3, "search_mode": "vector"},
                    "queries": [{"text": "hello"}],
                },
            }
            r = client.post(
                "/api/v1/evaluations/embeddings/abtest",
                json=create_payload,
                headers=_auth_headers(client),
            )
            assert r.status_code == 200, r.text
            test_id = r.json()["test_id"]

            # 2) Flip the test to completed after a short delay to allow heartbeats
            def _complete_later():
                # Allow a couple of heartbeat intervals to pass
                time.sleep(0.2)
                try:
                    user_id = DatabasePaths.get_single_user_id()
                    svc = get_unified_evaluation_service_for_user(user_id)
                    svc.db.set_abtest_status(test_id, "completed", stats_json={"progress": {"phase": 1.0}})
                except Exception:
                    # Do not fail the test from the helper thread
                    pass

            t = threading.Thread(target=_complete_later, daemon=True)
            t.start()

            # 3) Start the SSE stream and collect buffered result
            sse = client.get(
                f"/api/v1/evaluations/embeddings/abtest/{test_id}/events",
                headers={**_auth_headers(client), "Accept": "text/event-stream"},
            )
            assert sse.status_code == 200
            assert "text/event-stream" in sse.headers.get("content-type", "").lower()

            lines = sse.text.splitlines()
            # Expect at least one heartbeat in data mode and a final [DONE]
            heartbeat_seen = any(
                line.startswith("data: ") and "\"heartbeat\": true" in line for line in lines
            )
            done_seen = any(line.strip() == "data: [DONE]" for line in lines)
            assert heartbeat_seen, f"No heartbeat frame found in SSE lines: {lines[:10]}..."
            assert done_seen, f"No [DONE] frame found in SSE lines: {lines[-10:]}"

    finally:
        try:
            os.unlink(eval_db_path)
        except Exception:
            pass

