import asyncio
from importlib import import_module
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def _setup_isolated_authnz(monkeypatch, db_path: Path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables

    reset_settings()
    asyncio.run(reset_db_pool())
    ensure_authnz_tables(db_path)


def _admin_app():
    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin

    async def _pass_admin():
        return {"id": 1, "role": "admin", "username": "admin"}

    app.dependency_overrides[require_admin] = _pass_admin
    return app, require_admin


def test_admin_create_team_conflict_returns_409(monkeypatch, tmp_path):
    base_dir = tmp_path / "admin_conflict_team"
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / "authnz_admin.db"
    _setup_isolated_authnz(monkeypatch, db_path)

    app, dep = _admin_app()
    try:
        with TestClient(app) as client:
            # Create org
            r = client.post("/api/v1/admin/orgs", json={"name": "Org A"})
            assert r.status_code == 200, r.text
            org_id = r.json()["id"]
            # Create team once OK
            r1 = client.post(f"/api/v1/admin/orgs/{org_id}/teams", json={"name": "Core"})
            assert r1.status_code == 200, r1.text
            # Duplicate create -> 409
            r2 = client.post(f"/api/v1/admin/orgs/{org_id}/teams", json={"name": "Core"})
            assert r2.status_code == 409, r2.text
    finally:
        app.dependency_overrides.pop(dep, None)


def test_admin_create_role_conflict_returns_409(monkeypatch, tmp_path):
    base_dir = tmp_path / "admin_conflict_role"
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / "authnz_admin.db"
    _setup_isolated_authnz(monkeypatch, db_path)

    app, dep = _admin_app()
    try:
        with TestClient(app) as client:
            r1 = client.post("/api/v1/admin/roles", json={"name": "analyst"})
            assert r1.status_code == 200, r1.text
            r2 = client.post("/api/v1/admin/roles", json={"name": "analyst"})
            assert r2.status_code == 409, r2.text
    finally:
        app.dependency_overrides.pop(dep, None)


def test_admin_create_permission_conflict_returns_409(monkeypatch, tmp_path):
    base_dir = tmp_path / "admin_conflict_perm"
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / "authnz_admin.db"
    _setup_isolated_authnz(monkeypatch, db_path)

    app, dep = _admin_app()
    try:
        with TestClient(app) as client:
            body = {"name": "tools.execute:test", "description": "ok", "category": "tools"}
            r1 = client.post("/api/v1/admin/permissions", json=body)
            assert r1.status_code == 200, r1.text
            r2 = client.post("/api/v1/admin/permissions", json=body)
            assert r2.status_code == 409, r2.text
    finally:
        app.dependency_overrides.pop(dep, None)
