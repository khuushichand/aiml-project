import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from importlib import import_module

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_user(monkeypatch):
    async def override_user():
        return User(id=777, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    # Do not auto-start workflows scheduler in lifespan; we may start it explicitly
    monkeypatch.setenv("WORKFLOWS_SCHEDULER_ENABLED", "false")

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def client_admin(monkeypatch):
    async def override_user():
        u = User(id=1, username="admin", email=None, is_active=True)
        setattr(u, "is_admin", True)
        return u

    base_dir = Path.cwd() / "Databases" / "test_user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("WORKFLOWS_SCHEDULER_ENABLED", "false")

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_create_job_sets_next_and_schedule_id(client_admin):
    c = client_admin
    # Create job with cron/timezone
    body = {
        "name": "Daily 8am",
        "scope": {"tags": ["alpha"]},
        "schedule_expr": "0 8 * * *",
        "timezone": "UTC+8",
        "active": True,
    }
    r = c.post("/api/v1/watchlists/jobs", json=body)
    assert r.status_code == 200, r.text
    job = r.json()
    jid = job["id"]
    # next_run_at should be set even if scheduler service is not running
    assert job["next_run_at"] is not None
    # Admin can request internal fields to see linkage
    r = c.get(f"/api/v1/watchlists/jobs/{jid}", params={"include_internal": True})
    assert r.status_code == 200
    got = r.json()
    assert got.get("wf_schedule_id"), "Expected wf_schedule_id to be present for admin"


def test_update_job_recomputes_next_and_updates_enabled(client_user):
    c = client_user
    # Create a simple job
    body = {"name": "Quarter Hour", "scope": {}, "schedule_expr": "*/30 * * * *", "timezone": "UTC", "active": True}
    r = c.post("/api/v1/watchlists/jobs", json=body)
    assert r.status_code == 200
    job = r.json()
    jid = job["id"]
    # Update cron and timezone and active flag
    r = c.patch(f"/api/v1/watchlists/jobs/{jid}", json={"schedule_expr": "*/15 * * * *", "timezone": "UTC+8", "active": False})
    assert r.status_code == 200
    upd = r.json()
    assert upd["next_run_at"] is not None
    assert upd["active"] is False


def test_run_now_updates_last_and_next(client_user):
    c = client_user
    body = {"name": "Every Minute", "scope": {}, "schedule_expr": "* * * * *", "timezone": "UTC", "active": True}
    r = c.post("/api/v1/watchlists/jobs", json=body)
    assert r.status_code == 200
    jid = r.json()["id"]
    # Trigger run-now
    r = c.post(f"/api/v1/watchlists/jobs/{jid}/run")
    assert r.status_code == 200
    # Fetch job and verify last/next set
    r = c.get(f"/api/v1/watchlists/jobs/{jid}")
    assert r.status_code == 200
    job = r.json()
    assert job["last_run_at"] is not None
    assert job["next_run_at"] is not None
    # Details endpoint includes stats and logs (stats default zeros without pipeline)
    rid = c.post(f"/api/v1/watchlists/jobs/{jid}/run").json()["id"]
    r = c.get(f"/api/v1/watchlists/runs/{rid}/details")
    assert r.status_code == 200
    det = r.json()
    assert set(det.get("stats", {}).keys()) >= {"items_found", "items_ingested"}
