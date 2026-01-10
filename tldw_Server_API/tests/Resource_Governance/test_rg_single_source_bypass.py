import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import auth_deps, prompt_studio_deps
from tldw_Server_API.app.core.Resource_Governance.middleware_simple import RGSimpleMiddleware
from tldw_Server_API.app.core.Resource_Governance.governor import RGDecision


class _Snap:
    def __init__(self, route_map):
             self.route_map = route_map


class _Loader:
    def __init__(self, route_map):
             self._snap = _Snap(route_map)

    def get_snapshot(self):

             return self._snap

    def get_policy(self, _pid):  # pragma: no cover - not needed for these tests
        return {}


class _AllowGov:
    async def reserve(self, req, op_id=None):
        pid = (req.tags or {}).get("policy_id")
        dec = RGDecision(
            allowed=True,
            retry_after=None,
            details={"policy_id": pid, "categories": {"requests": {"allowed": True, "limit": 10, "retry_after": 0}}},
        )
        return dec, "h1"

    async def commit(self, handle_id, actuals=None):
        return None


class _DenyLimiter:
    enabled = True

    async def check_rate_limit(self, *args, **kwargs):  # pragma: no cover - should not be called
        raise AssertionError("legacy limiter should be bypassed on RG-governed routes")


@pytest.mark.asyncio
async def test_auth_deps_check_rate_limit_bypasses_when_rg_policy_present(monkeypatch):
    # Build app with RG middleware and a route that still uses legacy check_rate_limit.
    app = FastAPI()
    app.add_middleware(RGSimpleMiddleware)

    @app.get("/api/v1/rag/search", dependencies=[Depends(auth_deps.check_rate_limit)])
    async def rag_search():
        return {"ok": True}

    app.state.rg_policy_loader = _Loader({"by_path": {"/api/v1/rag/*": "rag.default"}})
    app.state.rg_governor = _AllowGov()

    async def _fake_rate_limiter():
        return _DenyLimiter()

    app.dependency_overrides[auth_deps.get_rate_limiter_dep] = _fake_rate_limiter

    with TestClient(app) as client:
        resp = client.get("/api/v1/rag/search")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_prompt_studio_check_rate_limit_bypasses_when_rg_policy_present(monkeypatch):
    async def _raise_if_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError("Prompt Studio legacy limiter should be bypassed on RG-governed routes")

    monkeypatch.setattr(prompt_studio_deps, "_authnz_check_rate_limit", _raise_if_called)

    user_ctx = {"user_id": "u1", "rg_policy_id": "prompt_studio.default"}
    sec = type("Sec", (), {"enable_rate_limiting": True})()

    ok = await prompt_studio_deps.check_rate_limit(
        operation="create_project",
        user_context=user_ctx,
        security_config=sec,
    )
    assert ok is True
