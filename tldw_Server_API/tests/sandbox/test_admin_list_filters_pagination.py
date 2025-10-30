from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.Sandbox.models import RunStatus, RunPhase, RuntimeType


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    # Use in-memory store by default (already defaulted in config)
    return TestClient(app)


def _admin_user_dep():
    # Override get_request_user to return admin
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
    return User(id=1, username="admin", roles=["admin"], is_admin=True)


def _seed_run(run_id: str, user_id: int, image_digest: str, started_offset_sec: int, phase: str = "completed") -> None:
    from tldw_Server_API.app.api.v1.endpoints import sandbox as sb
    from tldw_Server_API.app.core.Sandbox.models import RunPhase
    st = RunStatus(
        id=run_id,
        phase=RunPhase(phase),
        spec_version="1.0",
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        exit_code=0,
        started_at=(datetime.now(timezone.utc) - timedelta(seconds=started_offset_sec)),
        finished_at=datetime.now(timezone.utc),
        message="ok",
        image_digest=image_digest,
        policy_hash="deadbeefcafebabe",
    )
    sb._service._orch._store.put_run(user_id, st)  # type: ignore[attr-defined]


def test_admin_list_filters_and_pagination(monkeypatch):
    # Override dependency for admin routes
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
    app.dependency_overrides[get_request_user] = _admin_user_dep

    with _client() as client:
        # Seed 3 runs: two with d1 digest, one with d2
        _seed_run("r1", 1, "d1", 300)
        _seed_run("r2", 1, "d1", 200)
        _seed_run("r3", 1, "d2", 100)

        # Filter by digest d1, page size 1
        r = client.get("/api/v1/sandbox/admin/runs", params={"image_digest": "d1", "limit": 1, "offset": 0})
        assert r.status_code == 200
        j = r.json()
        assert j["total"] == 2
        assert j["limit"] == 1
        assert j["offset"] == 0
        assert j["has_more"] is True
        assert len(j["items"]) == 1

        # Next page
        r2 = client.get("/api/v1/sandbox/admin/runs", params={"image_digest": "d1", "limit": 1, "offset": 1})
        assert r2.status_code == 200
        j2 = r2.json()
        assert j2["total"] == 2
        assert j2["has_more"] is False
        assert len(j2["items"]) == 1

        # Date filter: only include recent (exclude r1 by from cutoff)
        recent_from = (datetime.now(timezone.utc) - timedelta(seconds=250)).isoformat()
        r3 = client.get("/api/v1/sandbox/admin/runs", params={"started_at_from": recent_from})
        assert r3.status_code == 200
        j3 = r3.json()
        # Should include r2 and r3 at least
        assert j3["total"] >= 2

    # Clear overrides
    app.dependency_overrides.clear()


def test_admin_list_filter_by_user_and_phase(monkeypatch):
    # Override dependency for admin routes
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
    app.dependency_overrides[get_request_user] = _admin_user_dep

    with _client() as client:
        # Seed runs for two users and phases
        _seed_run("u1_ok", 1, "d1", 300, phase="completed")
        _seed_run("u2_fail", 2, "d1", 200, phase="failed")
        _seed_run("u1_fail", 1, "d2", 100, phase="failed")

        # Filter: user_id=1 and phase=failed → expect only u1_fail
        r = client.get(
            "/api/v1/sandbox/admin/runs",
            params={"user_id": "1", "phase": "failed", "limit": 10, "offset": 0},
        )
        assert r.status_code == 200
        j = r.json()
        ids = [it["id"] for it in j.get("items", [])]
        assert "u1_fail" in ids
        assert "u2_fail" not in ids
        # Ensure totals align with filter (should be exactly 1 for this dataset)
        assert j.get("total") == 1

    app.dependency_overrides.clear()
