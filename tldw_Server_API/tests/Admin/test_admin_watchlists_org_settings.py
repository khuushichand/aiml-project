import os
from importlib import import_module
import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def test_admin_update_org_watchlists_settings(monkeypatch, tmp_path):
    # Isolate AuthNZ DB and enable TEST_MODE
    base_dir = tmp_path / "test_admin_org_settings"
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / "authnz_admin.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TEST_MODE", "1")
    # Force single-user mode to avoid Postgres path picked from prior tests
    monkeypatch.setenv("AUTH_MODE", "single_user")

    # Reset cached settings / DB pool and ensure schema for isolated DB
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables

    reset_settings()
    asyncio.run(reset_db_pool())
    ensure_authnz_tables(db_path)

    # Spin up app and override admin requirement
    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin

    async def _pass_admin():
        return {"id": 1, "role": "admin", "username": "admin"}

    app.dependency_overrides[require_admin] = _pass_admin

    with TestClient(app) as client:
        # Create an organization (should succeed on a fresh DB)
        r = client.post("/api/v1/admin/orgs", json={"name": "Alpha Org"})
        assert r.status_code == 200, r.text
        org = r.json()
        org_id = org["id"]

        # Initial GET (no metadata yet)
        r = client.get(f"/api/v1/admin/orgs/{org_id}/watchlists/settings")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["org_id"] == org_id
        assert data.get("require_include_default") in (None, False)

        # Enable include-only default
        r = client.patch(
            f"/api/v1/admin/orgs/{org_id}/watchlists/settings",
            json={"require_include_default": True},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["org_id"] == org_id
        assert data.get("require_include_default") is True

        # GET after enabling
        r = client.get(f"/api/v1/admin/orgs/{org_id}/watchlists/settings")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["org_id"] == org_id
        assert data.get("require_include_default") is True

        # Disable include-only default
        r = client.patch(
            f"/api/v1/admin/orgs/{org_id}/watchlists/settings",
            json={"require_include_default": False},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["org_id"] == org_id
        assert data.get("require_include_default") is False

        # GET after disabling
        r = client.get(f"/api/v1/admin/orgs/{org_id}/watchlists/settings")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["org_id"] == org_id
        assert data.get("require_include_default") is False

    app.dependency_overrides.pop(require_admin, None)


def test_admin_create_org_conflict_returns_409(monkeypatch, tmp_path):
    # Isolate DB; verify second creation conflicts
    base_dir = tmp_path / "test_admin_org_settings_conflict"
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / "authnz_admin_conflict.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "single_user")

    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables

    reset_settings()
    asyncio.run(reset_db_pool())
    ensure_authnz_tables(db_path)

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin

    async def _pass_admin():
        return {"id": 1, "role": "admin", "username": "admin"}

    app.dependency_overrides[require_admin] = _pass_admin

    with TestClient(app) as client:
        # First create OK
        r1 = client.post("/api/v1/admin/orgs", json={"name": "Alpha Org"})
        assert r1.status_code == 200, r1.text
        # Second create with same name should 409
        r2 = client.post("/api/v1/admin/orgs", json={"name": "Alpha Org"})
        assert r2.status_code == 409, r2.text

    app.dependency_overrides.pop(require_admin, None)


def test_admin_watchlists_org_settings_404(monkeypatch):
    # Isolate DB
    base_dir = Path.cwd() / "Databases" / "test_admin_org_settings_404"
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / "authnz_admin_404.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "single_user")

    # Reset cached settings / DB pool and ensure schema for isolated DB
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables

    reset_settings()
    asyncio.run(reset_db_pool())
    ensure_authnz_tables(db_path)

    # App + admin override
    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin

    async def _pass_admin():
        return {"id": 1, "role": "admin", "username": "admin"}

    app.dependency_overrides[require_admin] = _pass_admin

    with TestClient(app) as client:
        missing_id = 9999
        # GET on missing org
        r = client.get(f"/api/v1/admin/orgs/{missing_id}/watchlists/settings")
        assert r.status_code == 404
        # PATCH on missing org
        r = client.patch(
            f"/api/v1/admin/orgs/{missing_id}/watchlists/settings",
            json={"require_include_default": True},
        )
        assert r.status_code == 404

    app.dependency_overrides.pop(require_admin, None)
