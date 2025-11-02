import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.unit


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


def test_cycle_detection_blocks_definition(client_with_wf: TestClient):
    client = client_with_wf
    # Explicit cycle: step a -> b, step b -> a via on_success routing
    definition = {
        "name": "cycle-def",
        "version": 1,
        "steps": [
            {"id": "a", "type": "log", "config": {"message": "A"}, "on_success": "b"},
            {"id": "b", "type": "log", "config": {"message": "B"}, "on_success": "a"},
        ],
    }
    r = client.post("/api/v1/workflows", json=definition)
    assert r.status_code == 422
    assert "cycle" in r.json().get("detail", "").lower()
