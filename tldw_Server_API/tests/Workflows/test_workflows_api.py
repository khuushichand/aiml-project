import json
import time
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_workflows_db(tmp_path):
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


def test_create_and_run_saved_workflow(client_with_workflows_db: TestClient):
    client = client_with_workflows_db

    definition = {
        "name": "hello",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "prompt", "config": {"template": "Hello {{ inputs.name }}"}},
        ],
    }

    # Create
    resp = client.post("/api/v1/workflows", json=definition)
    assert resp.status_code == 201, resp.text
    wid = resp.json()["id"]

    # Run
    run_resp = client.post(f"/api/v1/workflows/{wid}/run?mode=async", json={"inputs": {"name": "Alice"}})
    assert run_resp.status_code == 200, run_resp.text
    run_id = run_resp.json()["run_id"]

    # Poll until complete
    for _ in range(50):
        r = client.get(f"/api/v1/workflows/runs/{run_id}")
        assert r.status_code == 200
        data = r.json()
        if data["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert data["status"] == "succeeded"
    assert (data.get("outputs") or {}).get("text") == "Hello Alice"

    # Events include run_completed
    ev = client.get(f"/api/v1/workflows/runs/{run_id}/events")
    assert ev.status_code == 200
    types = [e["event_type"] for e in ev.json()]
    assert "run_completed" in types


def test_adhoc_limits_and_validation(client_with_workflows_db: TestClient):
    client = client_with_workflows_db

    # Unknown step type
    bad_def = {
        "definition": {
            "name": "x",
            "version": 1,
            "steps": [{"id": "s", "type": "unknown", "config": {}}],
        },
        "inputs": {},
    }
    r = client.post("/api/v1/workflows/run", json=bad_def)
    assert r.status_code == 422

    # Too large definition (>256KB)
    large_payload = "x" * (260 * 1024)
    big_def = {
        "definition": {
            "name": "big",
            "version": 1,
            "steps": [{"id": "s", "type": "prompt", "config": {"template": large_payload}}],
        }
    }
    r2 = client.post("/api/v1/workflows/run", json=big_def)
    assert r2.status_code == 413


def test_websocket_auth_and_events(client_with_workflows_db: TestClient):
    client = client_with_workflows_db

    # Create def and run
    definition = {
        "name": "hello-ws",
        "version": 1,
        "steps": [{"id": "s1", "type": "prompt", "config": {"template": "Hi {{ inputs.name }}"}}],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {"name": "Bob"}}).json()["run_id"]

    # Token for user id 1
    jwtm = get_jwt_manager()
    token = jwtm.create_access_token(subject="1", username="tester", roles=["user"], permissions=[])

    # Connect and receive snapshot
    with client.websocket_connect(f"/api/v1/workflows/ws?run_id={run_id}&token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "snapshot"

    # Unauthorized with wrong user
    bad_token = jwtm.create_access_token(subject="999", username="intruder", roles=["user"], permissions=[])
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/workflows/ws?run_id={run_id}&token={bad_token}"):
            pass
