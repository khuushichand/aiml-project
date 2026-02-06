from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_user(monkeypatch):
    async def override_user():
        return User(id=9201, username="scheduler-user", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_scheduler_controls"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("WORKFLOWS_SCHEDULER_ENABLED", "false")

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_job_scheduler_controls_roundtrip(client_user):
    r = client_user.post(
        "/api/v1/watchlists/jobs",
        json={
            "name": "Scheduler Controls",
            "scope": {},
            "schedule_expr": "*/15 * * * *",
            "timezone": "UTC",
            "active": True,
            "max_concurrency": 3,
            "per_host_delay_ms": 250,
        },
    )
    assert r.status_code == 200, r.text
    created = r.json()
    job_id = int(created["id"])
    assert created["max_concurrency"] == 3
    assert created["per_host_delay_ms"] == 250
    assert created["next_run_at"] is not None

    r = client_user.get(f"/api/v1/watchlists/jobs/{job_id}")
    assert r.status_code == 200, r.text
    fetched = r.json()
    assert fetched["max_concurrency"] == 3
    assert fetched["per_host_delay_ms"] == 250

    r = client_user.get("/api/v1/watchlists/jobs")
    assert r.status_code == 200, r.text
    rows = [row for row in r.json().get("items", []) if int(row["id"]) == job_id]
    assert len(rows) == 1
    assert rows[0]["max_concurrency"] == 3
    assert rows[0]["per_host_delay_ms"] == 250


def test_update_scheduler_controls_and_run_timestamps(client_user):
    r = client_user.post(
        "/api/v1/watchlists/jobs",
        json={
            "name": "Job Update",
            "scope": {},
            "schedule_expr": "*/30 * * * *",
            "timezone": "UTC",
            "active": True,
            "max_concurrency": 1,
            "per_host_delay_ms": 50,
        },
    )
    assert r.status_code == 200, r.text
    job_id = int(r.json()["id"])

    r = client_user.patch(
        f"/api/v1/watchlists/jobs/{job_id}",
        json={
            "schedule_expr": "*/10 * * * *",
            "timezone": "UTC",
            "max_concurrency": 5,
            "per_host_delay_ms": 500,
            "active": False,
        },
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["max_concurrency"] == 5
    assert updated["per_host_delay_ms"] == 500
    assert updated["active"] is False
    assert updated["next_run_at"] is not None

    # run-now should refresh history timestamps even after scheduler control updates
    r = client_user.post(f"/api/v1/watchlists/jobs/{job_id}/run")
    assert r.status_code == 200, r.text

    r = client_user.get(f"/api/v1/watchlists/jobs/{job_id}")
    assert r.status_code == 200, r.text
    fetched = r.json()
    assert fetched["last_run_at"] is not None
    assert fetched["next_run_at"] is not None
