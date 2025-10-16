import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


@pytest.fixture()
def client(tmp_path) -> TestClient:
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    def override_db():
        return db

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[wf_mod._get_db] = override_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_templates_list_and_get(client: TestClient):
    # List templates
    r = client.get("/api/v1/workflows/templates")
    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list)
    assert any(it.get("name") == "paper_roundup" for it in items), items
    # Ensure human-friendly title present
    one = next((x for x in items if x.get("name") == "paper_roundup"), None)
    assert one is not None and isinstance(one.get("title"), str) and len(one.get("title")) > 0

    # Retrieve one by name
    r2 = client.get("/api/v1/workflows/templates/paper_roundup")
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert isinstance(data, dict)
    assert data.get("name") == "paper_roundup"
    assert isinstance(data.get("steps"), list)


def test_templates_invalid_and_missing(client: TestClient):
    # Invalid name rejected
    # Non-encoded traversal may be normalized by the router; accept 400 or 404
    bad = client.get("/api/v1/workflows/templates/../../etc/passwd")
    assert bad.status_code in (400, 404)

    # URL-encoded traversal should be rejected with 400 (guarded before resolution)
    bad_enc = client.get("/api/v1/workflows/templates/%2E%2E/%2E%2E/etc/passwd")
    assert bad_enc.status_code == 400

    # Missing name 404
    miss = client.get("/api/v1/workflows/templates/not_a_template")
    assert miss.status_code == 404


def test_template_create_and_run_flow(client: TestClient):
    # Fetch a template and create+run
    tpl = client.get("/api/v1/workflows/templates/paper_roundup").json()
    create = client.post("/api/v1/workflows", json=tpl)
    assert create.status_code in (200, 201), create.text
    wid = create.json().get("id")
    assert wid, create.text

    run = client.post(f"/api/v1/workflows/{wid}/run?mode=async", json={"inputs": {}})
    assert run.status_code == 200, run.text
    run_id = run.json().get("run_id")
    assert run_id, run.text

    # Fetch status at least once and verify shape
    st = client.get(f"/api/v1/workflows/runs/{run_id}")
    assert st.status_code == 200, st.text
    sj = st.json()
    assert isinstance(sj, dict) and sj.get("id") == run_id and sj.get("status")

    # Events should be retrievable
    ev = client.get(f"/api/v1/workflows/runs/{run_id}/events")
    assert ev.status_code == 200, ev.text
    assert isinstance(ev.json(), list)


def test_templates_tags_endpoint(client: TestClient):
    r = client.get("/api/v1/workflows/templates/tags")
    assert r.status_code == 200, r.text
    tags = r.json()
    assert isinstance(tags, list)
    # Should include a few known tags from bundled templates
    expected = {"tts", "pdf", "research", "rag", "policy"}
    assert expected.issubset(set(tags)), f"Missing tags: {expected - set(tags)} in {tags}"
