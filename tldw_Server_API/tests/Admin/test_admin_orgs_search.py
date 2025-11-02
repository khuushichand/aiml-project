import os
from importlib import import_module
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def _override_admin_dep(app):
    # Override admin dependency for tests
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin

    async def _pass_admin():
        return {"id": 1, "role": "admin", "username": "admin"}

    app.dependency_overrides[require_admin] = _pass_admin
    return require_admin


def test_admin_orgs_list_with_total_and_search(monkeypatch, tmp_path):
    # Use SQLite and TEST_MODE to avoid network and simplify setup
    db_path = tmp_path / "authnz_admin_search.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TEST_MODE", "1")

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    require_admin = _override_admin_dep(app)

    try:
        with TestClient(app) as client:
            # Seed a few organizations
            created = []
            for name, slug in [("Alpha Org", "alpha"), ("Beta Company", "betaco"), ("Gamma Labs", "gammalabs")]:
                r = client.post("/api/v1/admin/orgs", json={"name": name, "slug": slug})
                assert r.status_code == 200, r.text
                created.append(r.json())

            # Basic list with pagination metadata
            r = client.get("/api/v1/admin/orgs", params={"limit": 2, "offset": 0})
            assert r.status_code == 200, r.text
            data = r.json()
            assert isinstance(data.get("items"), list)
            assert isinstance(data.get("total"), int)
            assert data.get("limit") == 2
            assert data.get("offset") == 0
            # If total > 2, has_more should be True
            assert data.get("has_more") == (data["total"] > 2)

            # Search by name (case-insensitive)
            r = client.get("/api/v1/admin/orgs", params={"q": "beta"})
            assert r.status_code == 200, r.text
            data = r.json()
            names = [o["name"].lower() for o in data.get("items", [])]
            assert any("beta" in n for n in names)

            # Search by slug
            r = client.get("/api/v1/admin/orgs", params={"q": "gammalabs"})
            assert r.status_code == 200, r.text
            data = r.json()
            slugs = [o.get("slug") for o in data.get("items", [])]
            assert any(s == "gammalabs" for s in slugs)

            # Search by ID textual
            target_id = str(created[0]["id"])  # Alpha Org id
            r = client.get("/api/v1/admin/orgs", params={"q": target_id})
            assert r.status_code == 200, r.text
            data = r.json()
            ids = [str(o["id"]) for o in data.get("items", [])]
            assert target_id in ids
    finally:
        app.dependency_overrides.pop(require_admin, None)
