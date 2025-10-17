from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_admin(monkeypatch):
    async def override_user():
        # Admin user for owner overrides
        u = User(id=1, username="admin", email=None, is_active=True)
        setattr(u, "is_admin", True)
        setattr(u, "tenant_id", "default")
        return u

    fastapi_app.dependency_overrides[get_request_user] = override_user

    # Ensure scheduler is started for tests that need APScheduler instance
    svc = get_workflows_scheduler()
    asyncio.run(svc.start())

    with TestClient(fastapi_app) as client:
        yield client, svc

    # Teardown
    try:
        asyncio.run(svc.stop())
    except Exception:
        pass
    fastapi_app.dependency_overrides.clear()


def test_cron_validation_422(client_admin):
    client, _ = client_admin
    bad = {
        "cron": "not a cron",
        "timezone": "UTC",
        "inputs": {},
    }
    r = client.post("/api/v1/scheduler/workflows/dry-run", json=bad)
    assert r.status_code == 422


def test_dry_run_returns_next_run(client_admin):
    client, _ = client_admin
    body = {
        "cron": "*/15 * * * *",
        "timezone": "UTC",
        "inputs": {"x": 1},
    }
    r = client.post("/api/v1/scheduler/workflows/dry-run", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("valid") is True
    assert isinstance(data.get("next_run_at"), str) and len(data["next_run_at"]) > 0


def test_concurrency_mode_mapping_and_job_defaults(client_admin):
    client, svc = client_admin
    # queue mode should set max_instances > 1 and coalesce False
    body = {
        "workflow_id": None,
        "name": "q1",
        "cron": "*/30 * * * *",
        "timezone": "UTC",
        "inputs": {},
        "run_mode": "async",
        "validation_mode": "block",
        "enabled": True,
        "concurrency_mode": "queue",
        "misfire_grace_sec": 123,
        "coalesce": False,
    }
    rid = client.post("/api/v1/scheduler/workflows", json=body).json()["id"]
    jobs = svc._aps.get_jobs() if getattr(svc, "_aps", None) else []  # type: ignore[attr-defined]
    assert jobs, "Expected a scheduled job to be registered"
    job = next((j for j in jobs if j.id == rid), jobs[0])
    # APScheduler job exposes attributes for these settings in 3.x
    assert getattr(job, "max_instances", 1) > 1
    assert getattr(job, "misfire_grace_time", 0) == 123
    assert getattr(job, "coalesce", True) is False


def test_update_invalid_cron_returns_422(client_admin):
    client, _ = client_admin
    # Create a valid schedule
    body = {
        "name": "u1",
        "cron": "*/10 * * * *",
        "timezone": "UTC",
        "inputs": {},
        "run_mode": "async",
        "validation_mode": "block",
        "enabled": True,
    }
    sid = client.post("/api/v1/scheduler/workflows", json=body).json()["id"]
    # Attempt to update with invalid cron
    r = client.patch(f"/api/v1/scheduler/workflows/{sid}", json={"cron": "not a cron"})
    assert r.status_code == 422


def test_next_run_persisted_after_create(client_admin):
    client, _ = client_admin
    body = {
        "name": "p1",
        "cron": "*/7 * * * *",
        "timezone": "UTC",
        "inputs": {},
        "run_mode": "async",
        "validation_mode": "block",
        "enabled": True,
    }
    sid = client.post("/api/v1/scheduler/workflows", json=body).json()["id"]
    resp = client.get(f"/api/v1/scheduler/workflows/{sid}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data.get("next_run_at"), str) and len(data["next_run_at"]) > 0


@pytest.mark.asyncio
async def test_history_updates_on_fire(monkeypatch):
    # Start service directly without TestClient overhead for this unit test
    svc = get_workflows_scheduler()
    await svc.start()
    # Create a schedule via DB helper to avoid HTTP
    sid = svc.create(
        tenant_id="default",
        user_id="1",
        workflow_id=None,
        name="hist",
        cron="*/5 * * * *",
        timezone="UTC",
        inputs={},
        run_mode="async",
        validation_mode="block",
        enabled=True,
        concurrency_mode="skip",
        misfire_grace_sec=60,
        coalesce=True,
    )

    class _StubScheduler:
        async def submit(self, *args: Any, **kwargs: Any) -> str:
            return "task-1"

    # Monkeypatch core scheduler to avoid real submission
    svc._core_scheduler = _StubScheduler()  # type: ignore[attr-defined]

    # Fire the job manually
    await svc._run_schedule(sid)  # type: ignore[attr-defined]

    s = svc.get(sid)
    assert s is not None
    # last_run_at populated, last_status moved to queued
    assert isinstance(s.last_run_at, str) and len(s.last_run_at) > 0
    assert s.last_status in ("pending", "queued", "error", "running")

    await svc.stop()
