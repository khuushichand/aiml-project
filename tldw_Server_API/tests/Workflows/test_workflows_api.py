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


def test_step_types_and_runs_listing(client_with_workflows_db: TestClient):
    client = client_with_workflows_db

    # Step types discovery
    st = client.get("/api/v1/workflows/step-types")
    assert st.status_code == 200
    items = st.json()
    names = [i.get("name") for i in items]
    assert "prompt" in names and "rag_search" in names

    # Create two definitions: one succeeds, one fails
    ok_def = {
        "name": "list-ok",
        "version": 1,
        "steps": [{"id": "s1", "type": "prompt", "config": {"template": "Hello"}}],
    }
    fail_def = {
        "name": "list-fail",
        "version": 1,
        "steps": [{"id": "s1", "type": "prompt", "config": {"template": "bad", "force_error": True}}],
    }
    ok_id = client.post("/api/v1/workflows", json=ok_def).json()["id"]
    fail_id = client.post("/api/v1/workflows", json=fail_def).json()["id"]

    ok_run = client.post(f"/api/v1/workflows/{ok_id}/run", json={"inputs": {}}).json()["run_id"]
    fail_run = client.post(f"/api/v1/workflows/{fail_id}/run", json={"inputs": {}}).json()["run_id"]

    import time
    # Wait for terminal statuses
    deadline = time.time() + 5
    statuses = {}
    while time.time() < deadline and (len(statuses) < 2):
        for rid in (ok_run, fail_run):
            if rid in statuses:
                continue
            data = client.get(f"/api/v1/workflows/runs/{rid}").json()
            if data["status"] in ("succeeded", "failed", "cancelled"):
                statuses[rid] = data["status"]
        time.sleep(0.05)
    assert statuses.get(ok_run) == "succeeded"
    assert statuses.get(fail_run) == "failed"

    # List succeeded
    lst_ok = client.get("/api/v1/workflows/runs", params={"status": ["succeeded"], "limit": 10, "offset": 0}).json()
    assert any(r["run_id"] == ok_run for r in lst_ok.get("runs", []))
    # List failed
    lst_fail = client.get("/api/v1/workflows/runs", params=[("status", "failed")]).json()
    assert any(r["run_id"] == fail_run for r in lst_fail.get("runs", []))
    # Ordering and pagination
    lst_page = client.get("/api/v1/workflows/runs", params={"limit": 1, "offset": 0, "order_by": "created_at", "order": "desc"}).json()
    assert isinstance(lst_page.get("runs"), list) and len(lst_page["runs"]) == 1
    if lst_page.get("next_offset") is not None:
        lst_next = client.get("/api/v1/workflows/runs", params={"limit": 1, "offset": lst_page["next_offset"]}).json()
        assert isinstance(lst_next.get("runs"), list)


def test_runs_list_created_after_before(client_with_workflows_db: TestClient):
    client = client_with_workflows_db
    # Create two runs with a small time gap
    d = {"name": "time-filter", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "ok"}}]}
    wid = client.post("/api/v1/workflows", json=d).json()["id"]
    r1 = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    import time
    time.sleep(0.05)
    r2 = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]

    # Extract created_at via DB
    from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
    from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
    db: WorkflowsDatabase = client.app.dependency_overrides[wf_mod._get_db]()
    c1 = db.get_run(r1).created_at
    c2 = db.get_run(r2).created_at

    # created_after just after c1 should include r2 only
    from datetime import datetime, timedelta
    try:
        dt1 = datetime.fromisoformat(c1)
    except Exception:
        dt1 = datetime.strptime(c1.split('.') [0], "%Y-%m-%dT%H:%M:%S")
    ca = (dt1 + timedelta(milliseconds=1)).isoformat()
    lst_after = client.get("/api/v1/workflows/runs", params={"created_after": ca}).json()
    after_ids = [r["run_id"] for r in lst_after.get("runs", [])]
    assert r2 in after_ids
    # created_before just before c2 should include r1 only (if ordering tight)
    try:
        dt2 = datetime.fromisoformat(c2)
    except Exception:
        dt2 = datetime.strptime(c2.split('.') [0], "%Y-%m-%dT%H:%M:%S")
    cb = (dt2 - timedelta(milliseconds=1)).isoformat()
    lst_before = client.get("/api/v1/workflows/runs", params={"created_before": cb}).json()
    before_ids = [r["run_id"] for r in lst_before.get("runs", [])]
    assert r1 in before_ids
