import os

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

pytestmark = pytest.mark.rate_limit

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


class _GovAllow:
    async def reserve(self, req, op_id=None):
        dec = RGDecision(
            allowed=True,
            retry_after=None,
            details={"policy_id": req.tags.get("policy_id"), "categories": {"requests": {"allowed": True, "limit": 2, "retry_after": 0}}},
        )
        return dec, "h-allow"

    async def commit(self, handle_id, actuals=None):
        return None


def _make_app_probe():
    app = FastAPI()
    app.add_middleware(RGSimpleMiddleware)

    @app.get("/probe")
    async def probe(request: Request):  # pragma: no cover - exercised via client
        return {"client_ip": getattr(request.state, "rg_client_ip", None)}

    # Route mapping for middleware policy resolution
    route_map = {"by_path": {"/probe": "allow.probe"}}
    app.state.rg_policy_loader = _Loader(route_map)
    app.state.rg_governor = _GovAllow()
    return app


@pytest.mark.asyncio
async def test_middleware_sets_rg_client_ip_from_xff_when_proxy_trusted(monkeypatch):
    # Trust the local peer and read X-Forwarded-For
    monkeypatch.setenv("RG_TRUSTED_PROXIES", "127.0.0.1")
    monkeypatch.setenv("RG_CLIENT_IP_HEADER", "X-Forwarded-For")

    app = _make_app_probe()
    with TestClient(app) as c:
        r = c.get("/probe", headers={"X-Forwarded-For": "203.0.113.9, 127.0.0.1"})
        assert r.status_code == 200
        assert r.json().get("client_ip") == "203.0.113.9"


@pytest.mark.asyncio
async def test_middleware_ignores_xff_without_trusted_proxy(monkeypatch):
    monkeypatch.delenv("RG_TRUSTED_PROXIES", raising=False)
    monkeypatch.setenv("RG_CLIENT_IP_HEADER", "X-Forwarded-For")

    app = _make_app_probe()
    with TestClient(app) as c:
        r = c.get("/probe", headers={"X-Forwarded-For": "198.51.100.7"})
        assert r.status_code == 200
        # When proxy is not trusted, fallback to peer (TestClient defaults to 127.0.0.1)
        assert r.json().get("client_ip") in {"127.0.0.1", "::1"}
