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

    def get_policy(self, _policy_id: str):
        return dict(self._policy or {})


class _CaptureGov:
    def __init__(self):
        self.seen_categories = []

    async def reserve(self, req, op_id=None):
        _ = op_id
        self.seen_categories.append(dict(req.categories or {}))
        pid = (req.tags or {}).get("policy_id")
        dec = RGDecision(
            allowed=True,
            retry_after=None,
            details={"policy_id": pid, "categories": {"requests": {"allowed": True, "limit": 2, "retry_after": 0}}},
        )
        return dec, "h3"

    async def commit(self, handle_id, actuals=None):
        _ = handle_id, actuals
        return None

    async def peek_with_policy(self, entity, categories, policy_id):
        _ = entity, policy_id
        # Report a single remaining request for deterministic headers
        return {c: {"remaining": 1, "reset": 0} for c in categories}


@pytest.mark.asyncio
async def test_middleware_ignores_tokens_env_and_sends_requests_only(monkeypatch):
    # These legacy env vars should no longer change middleware behavior.
    monkeypatch.setenv("RG_MIDDLEWARE_ENFORCE_TOKENS", "1")
    monkeypatch.setenv("RG_ENDPOINT_ENFORCE_TOKENS", "0")

    app = FastAPI()
    app.add_middleware(RGSimpleMiddleware)

    @app.get("/api/v1/chat/completions", tags=["chat"])
    async def chat_route():  # pragma: no cover
        return {"ok": True}

    app.state.rg_policy_loader = _Loader({"by_path": {"/api/v1/chat/*": "chat.default"}}, {"requests": {"rpm": 2}})
    gov = _CaptureGov()
    app.state.rg_governor = gov

    with TestClient(app) as c:
        r = c.get("/api/v1/chat/completions")
        assert r.status_code == 200
        assert r.headers.get("X-RateLimit-Limit") == "2"
        assert r.headers.get("X-RateLimit-Remaining") == "1"
        assert r.headers.get("X-RateLimit-Tokens-Remaining") is None

    assert gov.seen_categories == [{"requests": {"units": 1}}]


@pytest.mark.asyncio
async def test_middleware_ignores_streams_env_and_sends_requests_only(monkeypatch):
    monkeypatch.setenv("RG_MIDDLEWARE_ENFORCE_STREAMS", "1")

    app = FastAPI()
    app.add_middleware(RGSimpleMiddleware)

    @app.get("/api/v1/audio/stream", tags=["audio"])
    async def audio_route():  # pragma: no cover
        return {"ok": True}

    app.state.rg_policy_loader = _Loader({"by_path": {"/api/v1/audio/*": "audio.default"}}, {"requests": {"rpm": 2}})
    gov = _CaptureGov()
    app.state.rg_governor = gov

    with TestClient(app) as c:
        r = c.get("/api/v1/audio/stream")
        assert r.status_code == 200
        assert r.headers.get("X-RateLimit-Limit") == "2"
        assert r.headers.get("X-RateLimit-Remaining") == "1"

    assert gov.seen_categories == [{"requests": {"units": 1}}]
