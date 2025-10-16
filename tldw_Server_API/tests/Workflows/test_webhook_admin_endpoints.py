import json
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.DB_Manager import create_workflows_database, get_content_backend_instance
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


def test_dlq_list_and_replay_simulated(monkeypatch):
    # Simulate admin user via single-user mode and enable test-mode replay short-circuit
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("WORKFLOWS_TEST_REPLAY_SUCCESS", "true")
    # Override deps to simulate admin
    db_for_app = WorkflowsDatabase("Databases/test_wf_dlq.db")
    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)
    def override_db():
        return db_for_app
    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[wf_mod._get_db] = override_db

    with TestClient(app) as client:
        # Seed a DLQ row into the same DB the app uses
        db_for_app.enqueue_webhook_dlq(tenant_id="default", run_id="r1", url="https://example.com/hook", body={"ok": True}, last_error="init")
        # List DLQ
        resp = client.get("/api/v1/workflows/webhooks/dlq?limit=10")
        assert resp.status_code == 200
        items = resp.json().get("items") or []
        assert len(items) >= 1
        dlq_id = items[0]["id"]
        # Replay simulated (deletes row)
        r2 = client.post(f"/api/v1/workflows/webhooks/dlq/{dlq_id}/replay")
        assert r2.status_code == 200
        assert r2.json().get("ok") is True
    app.dependency_overrides.clear()
