from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_db(tmp_path):
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))

    async def override_admin():
        return User(id=1, username="admin", email="a@x", is_active=True, is_admin=True)

    def override_db():
        return db

    app.dependency_overrides[get_request_user] = override_admin
    app.dependency_overrides[wf_mod._get_db] = override_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def _wait_terminal(client: TestClient, rid: str, to: float = 5.0):
    deadline = time.time() + to
    while time.time() < deadline:
        d = client.get(f"/api/v1/workflows/runs/{rid}").json()
        if d["status"] in ("succeeded", "failed", "cancelled"):
            return d
        time.sleep(0.02)
    return client.get(f"/api/v1/workflows/runs/{rid}").json()


def test_list_multi_status_plus_date_range(client_with_db: TestClient):
    c = client_with_db
    ok_def = {"name": "msdr-ok", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "ok"}}]}
    bad_def = {"name": "msdr-bad", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "bad", "force_error": True}}]}
    w_ok = c.post("/api/v1/workflows", json=ok_def).json()["id"]
    w_bad = c.post("/api/v1/workflows", json=bad_def).json()["id"]
    r1 = c.post(f"/api/v1/workflows/{w_ok}/run", json={"inputs": {}}).json()["run_id"]
    time.sleep(0.05)
    r2 = c.post(f"/api/v1/workflows/{w_bad}/run", json={"inputs": {}}).json()["run_id"]
    _wait_terminal(c, r1)
    _wait_terminal(c, r2)

    db: WorkflowsDatabase = app.dependency_overrides[wf_mod._get_db]()
    c1 = db.get_run(r1).created_at
    c2 = db.get_run(r2).created_at
    try:
        dt1 = datetime.fromisoformat(c1)
        dt2 = datetime.fromisoformat(c2)
    except Exception:
        dt1 = datetime.strptime(c1.split('.') [0], "%Y-%m-%dT%H:%M:%S")
        dt2 = datetime.strptime(c2.split('.') [0], "%Y-%m-%dT%H:%M:%S")

    created_after = (dt1 - timedelta(seconds=1)).isoformat()
    created_before = (dt2 + timedelta(seconds=1)).isoformat()

    resp = c.get(
        "/api/v1/workflows/runs",
        params=[
            ("status", "succeeded"),
            ("status", "failed"),
            ("created_after", created_after),
            ("created_before", created_before),
            ("order", "asc"),
            ("order_by", "created_at"),
        ],
    )
    assert resp.status_code == 200
    runs = resp.json().get("runs", [])
    ids = [r.get("run_id") for r in runs]
    assert r1 in ids and r2 in ids
    # ASC tie-breaker: if timestamps equal, ensure stable total ordering by run_id
    # (we only assert sort does not explode and returns both)


def test_admin_owner_override_and_tenant_isolation(client_with_db: TestClient):
    c = client_with_db
    # Create as admin (user 1)
    d1 = {"name": "own1", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "a"}}]}
    w1 = c.post("/api/v1/workflows", json=d1).json()["id"]
    r_admin = c.post(f"/api/v1/workflows/{w1}/run", json={"inputs": {}}).json()["run_id"]

    # Now simulate user 2 creating a run
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User, get_request_user as _gru
    prev = c.app.dependency_overrides[_gru]

    async def override_user2():
        return _User(id=2, username="u2", email="u2@x", is_active=True, is_admin=False)

    c.app.dependency_overrides[_gru] = override_user2
    d2 = {"name": "own2", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "b"}}]}
    w2 = c.post("/api/v1/workflows", json=d2).json()["id"]
    r_user2 = c.post(f"/api/v1/workflows/{w2}/run", json={"inputs": {}}).json()["run_id"]
    # Back to admin
    c.app.dependency_overrides[_gru] = prev

    # Admin can force owner filter to 2 and see that run
    resp = c.get("/api/v1/workflows/runs", params={"owner": "2", "limit": 100}).json()
    ids = [r.get("run_id") for r in resp.get("runs", [])]
    assert r_user2 in ids

    # As non-admin (user 2), owner override should be ignored; they only see their runs
    c.app.dependency_overrides[_gru] = override_user2
    resp2 = c.get("/api/v1/workflows/runs", params={"owner": "1", "limit": 100}).json()
    runs2 = resp2.get("runs", [])
    assert runs2 and all(str(r.get("user_id")) == "2" for r in runs2)
    # restore
    c.app.dependency_overrides[_gru] = prev
