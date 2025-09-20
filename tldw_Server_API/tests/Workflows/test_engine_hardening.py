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


def test_cancel_during_long_prompt(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "cancel-long",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "prompt", "config": {"template": "X", "simulate_delay_ms": 1500}},
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]

    # Immediately cancel
    r = client.post(f"/api/v1/workflows/runs/{run_id}/cancel")
    assert r.status_code == 200

    # Poll for cancelled
    status = None
    for _ in range(100):
        data = client.get(f"/api/v1/workflows/runs/{run_id}").json()
        status = data["status"]
        if status in ("cancelled", "failed", "succeeded"):
            break
        time.sleep(0.02)
    assert status == "cancelled"


def test_step_timeout_and_retry_failure(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "timeout-retry",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "prompt", "retry": 1, "timeout_seconds": 0.05, "config": {"template": "Y", "simulate_delay_ms": 200}},
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]

    # Wait for completion
    for _ in range(200):
        data = client.get(f"/api/v1/workflows/runs/{run_id}").json()
        if data["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.02)
    assert data["status"] == "failed"
    ev = client.get(f"/api/v1/workflows/runs/{run_id}/events").json()
    types = [e["event_type"] for e in ev]
    assert "step_timeout" in types or "run_failed" in types


def test_heartbeat_written_for_step(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "hb",
        "version": 1,
        "steps": [
            {"id": "s1", "type": "prompt", "config": {"template": "hello"}},
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]

    # wait briefly for step to record
    time.sleep(0.05)
    # fetch from DB (via events identify step_run_id not exposed; query table)
    db: WorkflowsDatabase = app.dependency_overrides[wf_mod._get_db]()
    rows = db._conn.cursor().execute("SELECT heartbeat_at FROM workflow_step_runs WHERE run_id = ?", (run_id,)).fetchall()
    assert rows, "No step runs recorded"
    assert any(r[0] is not None for r in rows)

