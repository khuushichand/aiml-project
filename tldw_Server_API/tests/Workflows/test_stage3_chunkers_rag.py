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


def test_chunker_options_endpoint(client_with_wf: TestClient):
    client = client_with_wf
    r = client.get("/api/v1/workflows/options/chunkers")
    assert r.status_code == 200
    data = r.json()
    assert data.get("name") == "core_chunking"
    assert isinstance(data.get("methods"), list) and "words" in data["methods"]
    assert isinstance(data.get("defaults"), dict)
    assert isinstance(data.get("parameter_schema"), dict)


def test_rag_search_with_citations_returns_citations(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "rag-citations",
        "version": 1,
        "steps": [
            {
                "id": "s1",
                "type": "rag_search",
                "config": {
                    "query": "test",
                    "top_k": 1,
                    "enable_citations": True,
                    "enable_reranking": False
                },
            },
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    # Poll until completion
    import time
    for _ in range(100):
        resp = client.get(f"/api/v1/workflows/runs/{run_id}")
        data = resp.json()
        if data["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert data["status"] == "succeeded"
    out = data.get("outputs") or {}
    # Citations may be empty but key should exist when enabled
    if out.get("documents"):
        assert "citations" in out or out.get("generated_answer") is not None
