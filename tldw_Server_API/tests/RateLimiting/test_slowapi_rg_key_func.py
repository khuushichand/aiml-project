import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.middleware import SlowAPIMiddleware

from tldw_Server_API.app.api.v1.API_Deps.rate_limiting import (
    get_test_aware_remote_address,
    limiter,
)
from tldw_Server_API.app.core.Resource_Governance.middleware_simple import RGSimpleMiddleware


@pytest.mark.asyncio
async def test_slowapi_key_func_defers_to_rg_simple_middleware(monkeypatch):
    """
    When RGSimpleMiddleware is attached to the app, the SlowAPI key
    function should return None so that ResourceGovernor is the
    primary ingress limiter and SlowAPI acts as a config carrier.
    """
    app = FastAPI()

    # Attach both RGSimpleMiddleware and SlowAPIMiddleware to mimic
    # the production stack when RG-enabled ingress is active.
    app.add_middleware(RGSimpleMiddleware)
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/test")
    async def _test_endpoint():
        return {"ok": True}

    # Build a Starlette Request via TestClient to exercise the key func.
    with TestClient(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200

        # Grab the underlying request object from the test client.
        # The SlowAPI limiter passes Starlette/FastAPI Request to key_func.
        request = resp.request
        key = get_test_aware_remote_address(request)

        # With RGSimpleMiddleware present, key must be None so SlowAPI
        # does not maintain its own IP-based counters.
        assert key is None
