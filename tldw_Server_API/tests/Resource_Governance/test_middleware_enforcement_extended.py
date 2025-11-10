import os
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
    """Governor stub that enforces tokens and streams in addition to requests."""
    def __init__(self, ttl=10, per_min=2):
        self.ttl = ttl
        self.per_min = per_min
        self._streams_acquired = 0
        self._tokens_used = 0

    async def reserve(self, req, op_id=None):
        cats = req.categories or {}
        # streams first: limit 1
        if "streams" in cats and self._streams_acquired >= 1:
            dec = RGDecision(
                allowed=False,
                retry_after=self.ttl,
                details={"policy_id": req.tags.get("policy_id"), "categories": {"streams": {"allowed": False, "limit": 1, "retry_after": self.ttl, "ttl_sec": self.ttl}}},
            )
            return dec, None
        if "tokens" in cats and self._tokens_used >= self.per_min:
            dec = RGDecision(
                allowed=False,
                retry_after=60,
                details={"policy_id": req.tags.get("policy_id"), "categories": {"tokens": {"allowed": False, "limit": self.per_min, "retry_after": 60}}},
            )
            return dec, None
        # Allow
        if "streams" in cats:
            self._streams_acquired += 1
        if "tokens" in cats:
            self._tokens_used += 1
        dec = RGDecision(
            allowed=True,
            retry_after=None,
            details={
                "policy_id": req.tags.get("policy_id"),
                "categories": {
                    "requests": {"allowed": True, "limit": 2, "retry_after": 0},
                    **({"tokens": {"allowed": True, "limit": self.per_min, "retry_after": 0}} if "tokens" in cats else {}),
                    **({"streams": {"allowed": True, "limit": 1, "retry_after": 0, "ttl_sec": self.ttl}} if "streams" in cats else {}),
                },
            },
        )
        return dec, "h3"

    async def commit(self, handle_id, actuals=None):
        # No-op: keep stream acquired to simulate long-held stream session across requests
        return None

    async def peek_with_policy(self, entity, categories, policy_id):
        out = {}
        for c in categories:
            if c == "requests":
                out[c] = {"remaining": 1, "reset": 0}
            elif c == "tokens":
                out[c] = {"remaining": max(0, self.per_min - self._tokens_used), "reset": 0}
            elif c == "streams":
                out[c] = {"remaining": max(0, 1 - self._streams_acquired), "reset": 0}
            else:
                out[c] = {"remaining": None, "reset": 0}
        return out


def _make_app_enforce_tokens(per_min=2):
    os.environ["RG_MIDDLEWARE_ENFORCE_TOKENS"] = "1"
    app = FastAPI()
    app.add_middleware(RGSimpleMiddleware)

    @app.get("/api/v1/chat/completions", tags=["chat"])
    async def chat_route():
        return {"ok": True}

    route_map = {"by_path": {"/api/v1/chat/*": "allow.tokens"}}
    policy = {"tokens": {"per_min": per_min}}
    app.state.rg_policy_loader = _Loader(route_map, policy)
    app.state.rg_governor = _Gov(ttl=10, per_min=per_min)
    return app


def _make_app_enforce_streams(ttl=10):
    os.environ["RG_MIDDLEWARE_ENFORCE_STREAMS"] = "1"
    app = FastAPI()
    app.add_middleware(RGSimpleMiddleware)

    @app.get("/api/v1/audio/stream", tags=["audio"])
    async def audio_route():
        return {"ok": True}

    route_map = {"by_path": {"/api/v1/audio/*": "allow.streams"}}
    policy = {"streams": {"max_concurrent": 1, "ttl_sec": ttl}}
    app.state.rg_policy_loader = _Loader(route_map, policy)
    app.state.rg_governor = _Gov(ttl=ttl, per_min=2)
    return app


@pytest.mark.asyncio
async def test_middleware_tokens_enforcement_denies_and_sets_per_minute_headers():
    app = _make_app_enforce_tokens(per_min=2)
    with TestClient(app) as c:
        r1 = c.get("/api/v1/chat/completions")
        assert r1.status_code == 200
        r2 = c.get("/api/v1/chat/completions")
        assert r2.status_code == 200
        r3 = c.get("/api/v1/chat/completions")
        assert r3.status_code == 429
        assert r3.headers.get("Retry-After") == "60"
        assert r3.headers.get("X-RateLimit-PerMinute-Limit") == "2"
        assert r3.headers.get("X-RateLimit-PerMinute-Remaining") == "0"
        assert r3.headers.get("X-RateLimit-Tokens-Remaining") == "0"


@pytest.mark.asyncio
async def test_middleware_streams_enforcement_denies_second_request_with_retry_after():
    app = _make_app_enforce_streams(ttl=10)
    with TestClient(app) as c:
        r1 = c.get("/api/v1/audio/stream")
        assert r1.status_code == 200
        r2 = c.get("/api/v1/audio/stream")
        assert r2.status_code == 429
        assert r2.headers.get("Retry-After") == "10"
