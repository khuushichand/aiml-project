import re

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.requests import Request

from tldw_Server_API.app.api.v1.endpoints.auth import router as auth_router
from tldw_Server_API.app.core.Resource_Governance.middleware_simple import RGSimpleMiddleware
from tldw_Server_API.app.core.Resource_Governance.policy_loader import default_policy_loader
from tldw_Server_API.app.core.config import API_V1_PREFIX

pytestmark = pytest.mark.rate_limit


def _build_request(app: FastAPI, path: str) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "app": app,
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_all_auth_routes_resolve_to_authnz_policy_via_rg_route_map():
    loader = default_policy_loader()
    await loader.load_once()

    app = FastAPI()
    app.state.rg_policy_loader = loader
    mw = RGSimpleMiddleware(app)

    auth_paths = []
    for route in auth_router.routes:
        if not isinstance(route, APIRoute):
            continue
        normalized = re.sub(r"\{[^}]+\}", "sample", str(route.path))
        auth_paths.append(f"{API_V1_PREFIX}{normalized}")

    assert auth_paths, "Expected at least one Auth router path"

    mismatches: list[tuple[str, str | None]] = []
    for path in sorted(set(auth_paths)):
        req = _build_request(app, path)
        policy_id = mw._derive_policy_id(req)
        if not (isinstance(policy_id, str) and policy_id.startswith("authnz.")):
            mismatches.append((path, policy_id))

    assert not mismatches, f"Auth route-map mismatches: {mismatches}"
