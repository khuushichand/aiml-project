from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


def _build_app(override_user):
    from fastapi import FastAPI

    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router
    from tldw_Server_API.app.core.config import API_V1_PREFIX

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    return app


def _create_run(client: TestClient) -> int:
    suffix = uuid4().hex
    source = client.post(
        "/api/v1/watchlists/sources",
        json={
            "name": f"Role Gate Feed {suffix}",
            "url": f"https://example.com/role-gate-{suffix}.xml",
            "source_type": "rss",
        },
    )
    assert source.status_code == 200, source.text
    source_id = source.json()["id"]

    job = client.post(
        "/api/v1/watchlists/jobs",
        json={
            "name": f"Role Gate Job {suffix}",
            "scope": {"sources": [source_id]},
            "active": True,
        },
    )
    assert job.status_code == 200, job.text
    job_id = job.json()["id"]

    run = client.post(f"/api/v1/watchlists/jobs/{job_id}/run")
    assert run.status_code == 200, run.text
    return int(run.json()["id"])


def test_runs_endpoints_require_admin_when_enabled(monkeypatch):
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_runs_role_gating"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("WATCHLISTS_RUNS_REQUIRE_ADMIN", "1")

    async def override_non_admin():
        return User(
            id=971,
            username="nonadmin",
            email="nonadmin@example.com",
            role="user",
            roles=["user"],
            permissions=[],
            is_admin=False,
            is_active=True,
        )

    app = _build_app(override_non_admin)
    with TestClient(app) as client:
        _create_run(client)
        blocked = client.get("/api/v1/watchlists/runs")
        assert blocked.status_code == 403, blocked.text
        assert blocked.json().get("detail") == "watchlists_runs_admin_required"


@pytest.mark.parametrize(
    "user_factory",
    [
        lambda: User(
            id=972,
            username="admin-by-permission",
            email="a1@example.com",
            role="user",
            roles=["user"],
            permissions=["system.configure"],
            is_admin=False,
            is_active=True,
        ),
        lambda: User(
            id=973,
            username="admin-by-roles-list",
            email="a2@example.com",
            role="user",
            roles=["admin"],
            permissions=[],
            is_admin=False,
            is_active=True,
        ),
        lambda: User(
            id=974,
            username="admin-by-is-admin-claim",
            email="a3@example.com",
            role="user",
            roles=[],
            permissions=[],
            is_admin=True,
            is_active=True,
        ),
    ],
)
def test_runs_endpoints_allow_real_admin_shapes_when_enabled(monkeypatch, user_factory):
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_runs_role_gating_admin_ok"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("WATCHLISTS_RUNS_REQUIRE_ADMIN", "1")

    async def override_admin():
        return user_factory()

    app = _build_app(override_admin)
    with TestClient(app) as client:
        run_id = _create_run(client)

        listed = client.get("/api/v1/watchlists/runs")
        assert listed.status_code == 200, listed.text
        payload = listed.json()
        assert payload["total"] >= 1
        ids = [int(item["id"]) for item in payload["items"]]
        assert run_id in ids

        details = client.get(f"/api/v1/watchlists/runs/{run_id}/details")
        assert details.status_code == 200, details.text


def test_runs_endpoints_do_not_treat_role_column_as_admin_claim(monkeypatch):
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_runs_role_gating_role_column"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("WATCHLISTS_RUNS_REQUIRE_ADMIN", "1")

    async def override_role_only_admin():
        return User(
            id=975,
            username="role-only-admin",
            email="roleonly@example.com",
            role="admin",
            roles=[],
            permissions=[],
            is_admin=False,
            is_active=True,
        )

    app = _build_app(override_role_only_admin)
    with TestClient(app) as client:
        _create_run(client)
        blocked = client.get("/api/v1/watchlists/runs")
        assert blocked.status_code == 403, blocked.text
        assert blocked.json().get("detail") == "watchlists_runs_admin_required"
