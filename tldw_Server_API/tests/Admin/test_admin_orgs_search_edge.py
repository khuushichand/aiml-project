from importlib import import_module

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request


pytestmark = pytest.mark.integration


def _override_admin_dep(app):


    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
    from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext

    async def _principal_override(request: Request) -> AuthPrincipal:  # type: ignore[override]
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="admin",
            token_type="access",
            jti=None,
            roles=["admin"],
            permissions=["system.configure"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        try:
            request.state.auth = AuthContext(
                principal=principal,
                ip=None,
                user_agent=None,
                request_id=None,
            )
        except Exception:
            # Best-effort; not all test paths require request.state.auth
            _ = None
        return principal

    app.dependency_overrides[get_auth_principal] = _principal_override
    return get_auth_principal


def test_admin_orgs_search_edge_cases(monkeypatch, tmp_path):


    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'authnz_admin_search_edge.db'}")
    monkeypatch.setenv("TEST_MODE", "1")

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    require_admin = _override_admin_dep(app)

    try:
        with TestClient(app) as client:
            # Seed orgs with varied slugs
            created = []
            for name, slug in [("Delta Org", "delta-slug"), ("Epsilon", "EpsILon"), ("Zeta", None)]:
                r = client.post("/api/v1/admin/orgs", json={"name": name, "slug": slug})
                assert r.status_code == 200, r.text
                created.append(r.json())

            # Case-insensitive slug search
            r = client.get("/api/v1/admin/orgs", params={"q": "epsilon"})
            assert r.status_code == 200, r.text
            slugs = [o.get("slug", "") for o in r.json().get("items", [])]
            assert any(s.lower() == "epsilon" for s in slugs)

            # Numeric ID search should match exact string form
            target_id = str(created[0]["id"])  # Delta Org id
            r = client.get("/api/v1/admin/orgs", params={"q": target_id})
            assert r.status_code == 200, r.text
            ids = [str(o["id"]) for o in r.json().get("items", [])]
            assert target_id in ids

            # Numeric-like non-id should not match (ensure empty or unrelated results)
            r = client.get("/api/v1/admin/orgs", params={"q": "000000"})
            assert r.status_code == 200, r.text
            ids = [str(o["id"]) for o in r.json().get("items", [])]
            assert "000000" not in ids
    finally:
        app.dependency_overrides.pop(require_admin, None)
