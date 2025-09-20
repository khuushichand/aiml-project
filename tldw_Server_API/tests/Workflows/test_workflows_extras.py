import time
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_wf(tmp_path):
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    def override_db():
        return db

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[wf_mod._get_db] = override_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_rag_search_workflow(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "rag",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "rag_search", "config": {"query": "hello world", "top_k": 1}},
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    # wait for completion
    for _ in range(50):
        r = client.get(f"/api/v1/workflows/runs/{run_id}")
        data = r.json()
        if data["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert data["status"] == "succeeded"
    out = data.get("outputs") or {}
    assert isinstance(out.get("documents", []), list)


def test_ws_events_stream(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "ws-events",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "prompt", "config": {"template": "A"}},
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]

    # Create token via MCP JWT manager
    from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
    jwtm = get_jwt_manager()
    token = jwtm.create_access_token(subject="1", username="tester", roles=["user"], permissions=[])

    with client.websocket_connect(f"/api/v1/workflows/ws?run_id={run_id}&token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "snapshot"
        # Read next few messages until run_completed
        got_completed = False
        deadline = time.time() + 2
        while time.time() < deadline and not got_completed:
            ev = ws.receive_json()
            if ev.get("event_type") == "run_completed":
                got_completed = True
        assert got_completed


def test_mcp_tool_workflow(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "mcp-echo",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "mcp_tool", "config": {"tool_name": "echo", "arguments": {"message": "ping"}}},
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    for _ in range(50):
        data = client.get(f"/api/v1/workflows/runs/{run_id}").json()
        if data["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert data["status"] == "succeeded"
    assert (data.get("outputs") or {}).get("result") == "ping"


def test_webhook_step_noop(client_with_wf: TestClient, monkeypatch):
    client = client_with_wf
    # Ensure webhook manager will not attempt outbound calls
    monkeypatch.setenv("TEST_MODE", "1")
    definition = {
        "name": "webhook-noop",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "webhook", "config": {"event": "evaluation.progress", "data": {"x": 1}}},
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {"user_id": "1"}}).json()["run_id"]
    for _ in range(50):
        data = client.get(f"/api/v1/workflows/runs/{run_id}").json()
        if data["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert data["status"] == "succeeded"
