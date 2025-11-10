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


def test_rg_capabilities_endpoint_redis_stub(monkeypatch):
    # Keep lightweight app; we will inject a Redis governor stub instance
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    # Ensure we use the in-memory Redis stub
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("RG_REAL_REDIS_URL", raising=False)

    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User

    async def _admin_user():
        return User(id=2, username="admin", email="admin@example.com", is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = _admin_user

    # Prepare a RedisResourceGovernor using the in-memory Redis stub
    from tldw_Server_API.app.core.Resource_Governance.governor_redis import RedisResourceGovernor

    class _DummyLoader:
        def get_policy(self, _pid):
            return {}

    gov = RedisResourceGovernor(policy_loader=_DummyLoader())

    # Preload tokens Lua so capabilities reflect loaded state
    import asyncio

    asyncio.run(gov._ensure_tokens_lua())  # type: ignore[attr-defined]

    with TestClient(app) as c:
        # Override any startup-initialized governor with our Redis instance
        app.state.rg_governor = gov
        r = c.get("/api/v1/resource-governor/diag/capabilities")
        assert r.status_code == 200
        caps = (r.json().get("capabilities") or {})
        assert caps.get("backend") == "redis"
        # Depending on stub implementation, real_redis may report either False or True;
        # focus on script capability signal for this test.
        assert caps.get("tokens_lua_loaded") is True

    app.dependency_overrides.pop(get_request_user, None)
