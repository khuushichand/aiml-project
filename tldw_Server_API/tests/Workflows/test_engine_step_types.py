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


def _wait_for_terminal(client: TestClient, run_id: str, timeout_s: float = 5.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        data = client.get(f"/api/v1/workflows/runs/{run_id}").json()
        if data["status"] in ("succeeded", "failed", "cancelled"):
            return data
        time.sleep(0.02)
    return client.get(f"/api/v1/workflows/runs/{run_id}").json()


def test_delay_step_then_log_succeeds(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "delay-log",
        "version": 1,
        "steps": [
            {"id": "d1", "type": "delay", "config": {"milliseconds": 10}},
            {"id": "l1", "type": "log", "config": {"message": "Done for {{ inputs.name || '' }}", "level": "info"}},
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {"name": "Alice"}}).json()["run_id"]
    data = _wait_for_terminal(client, run_id)
    assert data["status"] == "succeeded"
    # Final outputs should be from the last step (log)
    assert (data.get("outputs") or {}).get("logged") is True
    assert "Alice" in (data.get("outputs") or {}).get("message", "")


def test_log_only_outputs_shape(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "log-only",
        "version": 1,
        "steps": [
            {"id": "l1", "type": "log", "config": {"message": "Hello {{ inputs.name }}", "level": "debug"}},
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {"name": "Bob"}}).json()["run_id"]
    data = _wait_for_terminal(client, run_id)
    assert data["status"] == "succeeded"
    out = data.get("outputs") or {}
    assert out.get("logged") is True
    assert out.get("level") == "debug"
    assert out.get("message", "").endswith("Bob")

