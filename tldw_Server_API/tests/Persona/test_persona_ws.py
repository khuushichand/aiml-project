import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app


pytestmark = pytest.mark.unit


def _recv_until(client, predicate, timeout=2.0):
    import time
    start = time.time()
    while time.time() - start < timeout:
        msg = client.receive_text()
        try:
            data = json.loads(msg)
        except Exception:
            continue
        if predicate(data):
            return data
    raise AssertionError("Expected event not received in time")


def test_persona_websocket_plan_and_confirm():
    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            # Initial notice
            init = json.loads(ws.receive_text())
            assert init.get("event") in {"notice", "assistant_delta"}

            # Send a user message that triggers plan with ingest_url
            ws.send_text(json.dumps({"type": "user_message", "text": "https://example.com"}))

            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            assert "steps" in plan and isinstance(plan["steps"], list)
            steps = plan["steps"]
            plan_id = plan.get("plan_id")
            assert plan_id

            # Approve first step to trigger tool_call/result; include steps echo for scaffold
            ws.send_text(json.dumps({
                "type": "confirm_plan",
                "plan_id": plan_id,
                "approved_steps": [steps[0]["idx"]],
                "steps": steps,
            }))

            # Expect at least a tool_call and tool_result (result may be error in scaffold)
            evt_call = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            assert "step_idx" in evt_call
            evt_res = _recv_until(ws, lambda d: d.get("event") == "tool_result")
            assert "step_idx" in evt_res
