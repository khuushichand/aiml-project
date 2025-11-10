import pytest
pytestmark = pytest.mark.rate_limit
from fastapi import FastAPI
from fastapi.testclient import TestClient

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


class _Gov:
    def __init__(self):
        pass

    async def reserve(self, req, op_id=None):
        pid = (req.tags or {}).get("policy_id")
        # Any policy id starting with 'deny' will be denied
        if pid and pid.startswith("deny"):
            dec = RGDecision(
                allowed=False,
                retry_after=12,
                details={
                    "policy_id": pid,
                    "categories": {"requests": {"allowed": False, "retry_after": 12, "limit": 2}},
                },
            )
            return dec, None
        dec = RGDecision(
            allowed=True,
            retry_after=None,
            details={"policy_id": pid, "categories": {"requests": {"allowed": True, "limit": 2, "retry_after": 0}}},
        )
        return dec, "h1"

    async def commit(self, handle_id, actuals=None):
        return None


def _make_app(route_map):
    app = FastAPI()
    app.add_middleware(RGSimpleMiddleware)

    @app.get("/api/v1/chat/completions", tags=["chat"])
    async def chat_route():  # pragma: no cover - exercised via client
        return {"ok": True}

    @app.get("/api/v1/embeddings/vec")
    async def emb_route():  # pragma: no cover
        return {"ok": True}

    # Attach RG components
    app.state.rg_policy_loader = _Loader(route_map)
    app.state.rg_governor = _Gov()
    return app


@pytest.mark.asyncio
async def test_middleware_denies_with_retry_after_and_headers_by_tag():
    route_map = {"by_tag": {"chat": "deny.chat"}, "by_path": {"/api/v1/chat/*": "deny.chat"}}
    app = _make_app(route_map)
    with TestClient(app) as c:
        r = c.get("/api/v1/chat/completions")
        assert r.status_code == 429
        assert r.json().get("policy_id") == "deny.chat"
        # Headers present
        assert r.headers.get("Retry-After") == "12"
        assert r.headers.get("X-RateLimit-Limit") == "2"
        assert r.headers.get("X-RateLimit-Remaining") == "0"
        assert r.headers.get("X-RateLimit-Reset") == "12"


@pytest.mark.asyncio
async def test_middleware_denies_with_retry_after_by_path():
    route_map = {"by_path": {"/api/v1/embeddings*": "deny.emb"}}
    app = _make_app(route_map)
    with TestClient(app) as c:
        r = c.get("/api/v1/embeddings/vec")
        assert r.status_code == 429
        assert r.json().get("policy_id") == "deny.emb"
        assert r.headers.get("Retry-After") == "12"


@pytest.mark.asyncio
async def test_middleware_allows_when_policy_allows():
    route_map = {"by_tag": {"chat": "allow.chat"}, "by_path": {"/api/v1/chat/*": "allow.chat"}}
    app = _make_app(route_map)
    with TestClient(app) as c:
        r = c.get("/api/v1/chat/completions")
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # Success-path rate-limit headers present
        assert r.headers.get("X-RateLimit-Limit") == "2"
        assert r.headers.get("X-RateLimit-Remaining") == "1"
