import time
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_wf(tmp_path, monkeypatch, auth_headers):
    monkeypatch.setenv("WORKFLOWS_FILE_BASE_DIR", str(tmp_path))
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    async def override_principal(request=None):
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="test",
            token_type="test",
            jti=None,
            roles=["admin"],
            permissions=[],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        if request is not None:
            try:
                request.state.auth = AuthContext(
                    principal=principal,
                    ip=None,
                    user_agent=None,
                    request_id=None,
                )
            except Exception:
                pass
        return principal

    def override_db():

        return db

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[get_auth_principal] = override_principal
    app.dependency_overrides[wf_mod._get_db] = override_db

    with TestClient(app, headers=auth_headers) as client:
        yield client

    app.dependency_overrides.clear()


def test_media_ingest_local_text_chunking(client_with_wf: TestClient, tmp_path):
    client = client_with_wf
    # Create a small local text file
    sample = "# Title\n\nThis is a test document. It has multiple sentences. Another line here."
    fpath = tmp_path / "doc.txt"
    fpath.write_text(sample, encoding="utf-8")

    definition = {
        "name": "ingest-local",
        "version": 1,
        "steps": [
            {
                "id": "s1",
                "type": "media_ingest",
                "config": {
                    "sources": [{"uri": f"file://{fpath}"}],
                    "extraction": {"extract_text": True},
                    "chunking": {"strategy": "sentences", "max_tokens": 50, "overlap": 0},
                },
            }
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]

    # Poll until completion
    for _ in range(100):
        data = client.get(f"/api/v1/workflows/runs/{run_id}").json()
        if data["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert data["status"] == "succeeded"
    out = data.get("outputs") or {}
    assert "text" in out and isinstance(out["text"], str)
    assert "chunks" in out and isinstance(out["chunks"], list) and len(out["chunks"]) > 0
    # basic shape
    first = out["chunks"][0]
    assert "chunker_name" in first and "metadata" in first
