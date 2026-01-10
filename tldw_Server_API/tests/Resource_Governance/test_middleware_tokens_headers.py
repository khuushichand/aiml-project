import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Resource_Governance.middleware_simple import RGSimpleMiddleware
from tldw_Server_API.app.core.Resource_Governance.governor import RGDecision


pytestmark = pytest.mark.rate_limit


class _Snap:
    def __init__(self, route_map):
             self.route_map = route_map


class _Loader:
    def __init__(self, route_map, policy):
             self._snap = _Snap(route_map)
        self._policy = policy

    def get_snapshot(self):

             return self._snap

    def get_policy(self, policy_id: str):
        return dict(self._policy or {})


class _Gov:
    def __init__(self):
             pass

    async def reserve(self, req, op_id=None):
        pid = (req.tags or {}).get("policy_id")
        dec = RGDecision(
            allowed=True,
            retry_after=None,
            details={
                "policy_id": pid,
                "categories": {
                    "requests": {"allowed": True, "limit": 2, "retry_after": 0},
                    "tokens": {"allowed": True, "limit": 60, "retry_after": 0},
                },
            },
        )
        return dec, "h2"

    async def commit(self, handle_id, actuals=None):
        return None

    async def peek_with_policy(self, entity, categories, policy_id):
        # Pretend that one request and 1 token unit were consumed
        out = {}
        for c in categories:
            if c == "requests":
                out[c] = {"remaining": 1, "reset": 0}
            elif c == "tokens":
                out[c] = {"remaining": 59, "reset": 0}
            else:
                out[c] = {"remaining": None, "reset": 0}
        return out


def _make_app_with_tokens_headers():


     app = FastAPI()
    app.add_middleware(RGSimpleMiddleware)

    @app.get("/api/v1/chat/completions", tags=["chat"])
    async def chat_route():  # pragma: no cover
        return {"ok": True}

    # route_map maps path to a policy id; loader also responds with a tokens policy
    route_map = {"by_path": {"/api/v1/chat/*": "allow.chat.tokens"}}
    policy = {"tokens": {"per_min": 60}}
    app.state.rg_policy_loader = _Loader(route_map, policy)
    app.state.rg_governor = _Gov()
    return app


@pytest.mark.asyncio
async def test_middleware_adds_tokens_headers_on_success():
    app = _make_app_with_tokens_headers()
    with TestClient(app) as c:
        r = c.get("/api/v1/chat/completions")
        assert r.status_code == 200
        # Requests headers
        assert r.headers.get("X-RateLimit-Limit") == "2"
        assert r.headers.get("X-RateLimit-Remaining") == "1"
        # Tokens headers
        assert r.headers.get("X-RateLimit-Tokens-Remaining") == "59"
        assert r.headers.get("X-RateLimit-PerMinute-Limit") == "60"
        assert r.headers.get("X-RateLimit-PerMinute-Remaining") == "59"
