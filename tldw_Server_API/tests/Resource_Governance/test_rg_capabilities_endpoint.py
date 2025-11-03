import os
import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.rate_limit


def test_rg_capabilities_endpoint_admin(monkeypatch):
    # Ensure lightweight app behavior in tests and memory backend
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("RG_BACKEND", "memory")

    from tldw_Server_API.app.main import app
    # Override request user to satisfy RoleChecker("admin") guards if needed
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User

    async def _admin_user():
        return User(id=1, username="admin", email="admin@example.com", is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = _admin_user

    # Ensure a governor instance exists even if startup skipped it
    try:
        from tldw_Server_API.app.core.Resource_Governance.governor import MemoryResourceGovernor
        if getattr(app.state, "rg_governor", None) is None:
            app.state.rg_governor = MemoryResourceGovernor()
    except Exception:
        pass

    with TestClient(app) as c:
        r = c.get("/api/v1/resource-governor/diag/capabilities")
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "ok"
        caps = body.get("capabilities") or {}
        assert isinstance(caps, dict) and "backend" in caps

    # cleanup override
    app.dependency_overrides.pop(get_request_user, None)
