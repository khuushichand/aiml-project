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
    # owner exposed for admin review (present even for single-user)
    assert "user_id" in lst_ok.get("runs", [])[0]
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


def test_runs_multi_status_and_ordering(client_with_workflows_db: TestClient):
    client = client_with_workflows_db
    # Prepare: one success, one failure
    ok_def = {"name": "ms-ok", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "ok"}}]}
    bad_def = {"name": "ms-bad", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "bad", "force_error": True}}]}
    wid_ok = client.post("/api/v1/workflows", json=ok_def).json()["id"]
    wid_bad = client.post("/api/v1/workflows", json=bad_def).json()["id"]
    rid_ok = client.post(f"/api/v1/workflows/{wid_ok}/run", json={"inputs": {}}).json()["run_id"]
    import time as _t
    _t.sleep(0.02)
    rid_fail = client.post(f"/api/v1/workflows/{wid_bad}/run", json={"inputs": {}}).json()["run_id"]

    # Wait for terminal
    deadline = _t.time() + 5
    while _t.time() < deadline:
        st_ok = client.get(f"/api/v1/workflows/runs/{rid_ok}").json()["status"]
        st_fail = client.get(f"/api/v1/workflows/runs/{rid_fail}").json()["status"]
        if st_ok in ("succeeded","failed","cancelled") and st_fail in ("succeeded","failed","cancelled"):
            break
        _t.sleep(0.02)

    # Filter for both statuses together
    both = client.get("/api/v1/workflows/runs", params=[("status","succeeded"),("status","failed"), ("order","asc"), ("order_by","created_at"), ("limit", 50)]).json()
    ids = [r["run_id"] for r in both.get("runs", [])]
    assert rid_ok in ids and rid_fail in ids
    # Asc ordering should have the earlier run first
    idx_ok = ids.index(rid_ok)
    idx_fail = ids.index(rid_fail)
    assert idx_ok < idx_fail


def test_artifact_download_scope_non_strict(monkeypatch, client_with_workflows_db: TestClient):
    client = client_with_workflows_db
    # Relax validation to non-strict
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_VALIDATE_STRICT", "false")

    # Create definition and run to own the artifact
    d = {"name": "artifacts", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "ok"}}]}
    wid = client.post("/api/v1/workflows", json=d).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]

    # Prepare a temp file outside of the recorded workdir
    import os, tempfile, pathlib
    fd, path = tempfile.mkstemp(prefix="wf_non_strict_")
    os.write(fd, b"hello")
    os.close(fd)
    uri = f"file://{path}"

    # Add artifact with a different workdir in metadata to trigger scope mismatch
    from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
    db = client.app.dependency_overrides[wf_mod._get_db]()
    art_id = "a_non_strict"
    db.add_artifact(
        artifact_id=art_id,
        tenant_id="default",
        run_id=run_id,
        step_run_id=None,
        type="file",
        uri=uri,
        size_bytes=5,
        mime_type="text/plain",
        metadata={"workdir": str(pathlib.Path.cwd())},
    )
    # Download should succeed due to non-strict
    r = client.get(f"/api/v1/workflows/artifacts/{art_id}/download")
    assert r.status_code == 200
    # Now strict mode should block
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_VALIDATE_STRICT", "true")
    r2 = client.get(f"/api/v1/workflows/artifacts/{art_id}/download")
    assert r2.status_code == 400


def test_artifact_download_per_run_non_block(monkeypatch, client_with_workflows_db: TestClient):
    """Per-run validation_mode='non-block' should allow download even when env is strict."""
    client = client_with_workflows_db
    # Ensure env strict mode
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_VALIDATE_STRICT", "true")

    # Create definition and run
    d = {"name": "artifacts2", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "ok"}}]}
    wid = client.post("/api/v1/workflows", json=d).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]

    # Prepare a temp file outside of the recorded workdir
    import os, tempfile, pathlib
    fd, path = tempfile.mkstemp(prefix="wf_non_block_")
    os.write(fd, b"hello2")
    os.close(fd)
    uri = f"file://{path}"

    # Add artifact with different workdir to trigger scope mismatch
    from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
    db = client.app.dependency_overrides[wf_mod._get_db]()
    art_id = "a_per_run"
    db.add_artifact(
        artifact_id=art_id,
        tenant_id="default",
        run_id=run_id,
        step_run_id=None,
        type="file",
        uri=uri,
        size_bytes=6,
        mime_type="text/plain",
        metadata={"workdir": str(pathlib.Path.cwd())},
    )

    # First, strict mode should block
    r_block = client.get(f"/api/v1/workflows/artifacts/{art_id}/download")
    assert r_block.status_code == 400

    # Patch get_run to return validation_mode='non-block' for this run
    orig_get_run = db.get_run
    def _patched_get_run(rid: str):
        run = orig_get_run(rid)
        if run and run.run_id == run_id:
            try:
                setattr(run, 'validation_mode', 'non-block')
            except Exception:
                pass
        return run
    monkeypatch.setattr(db, 'get_run', _patched_get_run, raising=False)

    # Now should succeed even with strict env due to per-run override
    r_nonblock = client.get(f"/api/v1/workflows/artifacts/{art_id}/download")
    assert r_nonblock.status_code == 200


def test_runs_admin_owner_filter(client_with_workflows_db: TestClient):
    """Admins can filter by owner; non-admins cannot override owner param."""
    client = client_with_workflows_db

    # Create one run as admin (user id=1)
    def_admin = {"name": "admin-def", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "hi"}}]}
    wid_admin = client.post("/api/v1/workflows", json=def_admin).json()["id"]
    r_admin = client.post(f"/api/v1/workflows/{wid_admin}/run", json={"inputs": {}}).json()["run_id"]

    # Swap dependency to simulate a different, non-admin owner (user id=2)
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User, get_request_user as _gru
    from tldw_Server_API.app.api.v1.endpoints import workflows as _wf_mod
    prev_dep = client.app.dependency_overrides[_gru]

    async def override_user2():
        return _User(id=2, username="owner2", email="o2@x", is_active=True, is_admin=False)

    client.app.dependency_overrides[_gru] = override_user2
    def_u2 = {"name": "u2-def", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "yo"}}]}
    wid_u2 = client.post("/api/v1/workflows", json=def_u2).json()["id"]
    r_u2 = client.post(f"/api/v1/workflows/{wid_u2}/run", json={"inputs": {}}).json()["run_id"]

    # Restore admin for listing operations
    client.app.dependency_overrides[_gru] = prev_dep


def test_step_types_includes_branch_map(client_with_workflows_db: TestClient):
    client = client_with_workflows_db
    r = client.get("/api/v1/workflows/step-types")
    assert r.status_code == 200
    names = [s.get("name") for s in r.json()]
    assert "branch" in names
    assert "map" in names
    # Schemas include example and min_engine_version
    for st in r.json():
        assert "schema" in st
        assert "min_engine_version" in st


def test_artifact_manifest_verify_mismatch(monkeypatch, client_with_workflows_db: TestClient):
    client = client_with_workflows_db
    # Create definition and run
    d = {"name": "manifest", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "ok"}}]}
    wid = client.post("/api/v1/workflows", json=d).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]

    # Create temp artifact with wrong checksum
    import os, tempfile
    fd, path = tempfile.mkstemp(prefix="wf_manifest_")
    os.write(fd, b"data")
    os.close(fd)
    uri = f"file://{path}"
    from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
    db = client.app.dependency_overrides[wf_mod._get_db]()
    db.add_artifact(
        artifact_id="a_manifest",
        tenant_id="default",
        run_id=run_id,
        step_run_id=None,
        type="file",
        uri=uri,
        size_bytes=4,
        mime_type="text/plain",
        checksum_sha256="deadbeef",
        metadata={}
    )
    r = client.get(f"/api/v1/workflows/runs/{run_id}/artifacts/manifest", params={"verify": True})
    assert r.status_code == 200
    body = r.json()
    assert body.get("integrity_summary", {}).get("mismatch_count", 0) >= 1


def test_completion_webhook_tenant_denylist_blocked(monkeypatch, client_with_workflows_db: TestClient):
    client = client_with_workflows_db
    # Deny host globally
    monkeypatch.setenv("WORKFLOWS_WEBHOOK_DENYLIST", "deny.test")
    definition = {
        "name": "webhook-deny",
        "version": 1,
        "on_completion_webhook": {"url": "https://deny.test/hook", "include_outputs": False},
        "steps": [
            {"id": "s1", "type": "prompt", "config": {"template": "ok"}},
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    # Wait for completion
    import time
    deadline = time.time() + 3
    while time.time() < deadline:
        st = client.get(f"/api/v1/workflows/runs/{run_id}").json()["status"]
        if st in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(0.05)
    ev = client.get(f"/api/v1/workflows/runs/{run_id}/events").json()
    statuses = [e.get("payload", {}).get("status") for e in ev if e.get("event_type") == "webhook_delivery"]
    # blocked event should be present
    assert "blocked" in statuses

    # Admin can filter by specific owner (user 2) and should see that run
    # Ensure there is at least one run owned by user id=2
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User, get_request_user as _gru
    prev_dep = client.app.dependency_overrides[_gru]
    async def override_user2():
        return _User(id=2, username="owner2", email="o2@x", is_active=True, is_admin=False)
    client.app.dependency_overrides[_gru] = override_user2
    def_u2 = {"name": "u2-def", "version": 1, "steps": [{"id": "s1", "type": "prompt", "config": {"template": "yo"}}]}
    wid_u2 = client.post("/api/v1/workflows", json=def_u2).json()["id"]
    r_u2 = client.post(f"/api/v1/workflows/{wid_u2}/run", json={"inputs": {}}).json()["run_id"]
    client.app.dependency_overrides[_gru] = prev_dep

    lst_owner2 = client.get("/api/v1/workflows/runs", params={"owner": "2", "limit": 50}).json()
    ids2 = [r.get("run_id") for r in lst_owner2.get("runs", [])]
    assert r_u2 in ids2

    # Non-admin cannot override owner: they should only see their own runs (user id=2)
    client.app.dependency_overrides[_gru] = override_user2
    lst_nonadmin = client.get("/api/v1/workflows/runs", params={"owner": "1", "limit": 50}).json()
    runs = lst_nonadmin.get("runs", [])
    assert runs, "expected some runs for non-admin user"
    assert all(str(r.get("user_id")) == "2" for r in runs)
    # Restore admin override after test
    client.app.dependency_overrides[_gru] = prev_dep
