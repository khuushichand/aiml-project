import time
import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_wf(tmp_path, monkeypatch):
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    def override_db():
        return db

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[wf_mod._get_db] = override_db

    # Ensure tests do not attempt network
    monkeypatch.setenv("TEST_MODE", "1")

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_media_ingest_local_persists_to_db(client_with_wf: TestClient, tmp_path):
    client = client_with_wf
    sample_text = "Sample document for DB integration."
    p = tmp_path / "sample.txt"
    p.write_text(sample_text, encoding="utf-8")

    definition = {
        "name": "ingest-db",
        "version": 1,
        "steps": [
            {
                "id": "ing",
                "type": "media_ingest",
                "config": {
                    "sources": [{"uri": f"file://{p}", "media_type": "document"}],
                    "extraction": {"extract_text": True},
                    "indexing": {"index_in_rag": True},
                    "metadata": {"title": "Sample", "tags": ["workflow", "test"]},
                },
            }
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    # Wait for completion
    for _ in range(100):
        data = client.get(f"/api/v1/workflows/runs/{run_id}").json()
        if data["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert data["status"] == "succeeded"
    out = data.get("outputs") or {}
    # Should include media_ids when indexing requested
    mids = out.get("media_ids") or []
    assert isinstance(mids, list) and (len(mids) >= 1)
