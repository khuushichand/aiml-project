import pytest
from fastapi import FastAPI
from starlette.requests import Request

from tldw_Server_API.app.core.Resource_Governance.middleware_simple import RGSimpleMiddleware
from tldw_Server_API.app.core.Resource_Governance.policy_loader import default_policy_loader
from tldw_Server_API.app.core.config import API_V1_PREFIX

pytestmark = pytest.mark.rate_limit


def _build_request(app: FastAPI, path: str) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
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
async def test_video_lite_source_route_uses_video_lite_access_policy() -> None:
    loader = default_policy_loader()
    await loader.load_once()

    app = FastAPI()
    app.state.rg_policy_loader = loader
    middleware = RGSimpleMiddleware(app)
    request = _build_request(app, f"{API_V1_PREFIX}/media/video-lite/source")

    policy_id = middleware._derive_policy_id(request)

    assert policy_id == "media.video_lite.access"  # nosec B101
    assert loader.get_policy(policy_id) == {  # nosec B101
        "requests": {"rpm": 6000, "burst": 1.2},
        "scopes": ["user", "api_key", "ip"],
    }


@pytest.mark.asyncio
async def test_video_lite_workspace_route_uses_video_lite_access_policy() -> None:
    loader = default_policy_loader()
    await loader.load_once()

    app = FastAPI()
    app.state.rg_policy_loader = loader
    middleware = RGSimpleMiddleware(app)
    request = _build_request(app, f"{API_V1_PREFIX}/media/video-lite/workspace/youtube:abc123")
    request.scope["method"] = "GET"

    policy_id = middleware._derive_policy_id(request)

    assert policy_id == "media.video_lite.access"  # nosec B101
    assert loader.get_policy(policy_id) == {  # nosec B101
        "requests": {"rpm": 6000, "burst": 1.2},
        "scopes": ["user", "api_key", "ip"],
    }


@pytest.mark.asyncio
async def test_video_lite_summary_refresh_route_uses_video_lite_access_policy() -> None:
    loader = default_policy_loader()
    await loader.load_once()

    app = FastAPI()
    app.state.rg_policy_loader = loader
    middleware = RGSimpleMiddleware(app)
    request = _build_request(
        app,
        f"{API_V1_PREFIX}/media/video-lite/workspace/youtube:abc123/summary-refresh",
    )

    policy_id = middleware._derive_policy_id(request)

    assert policy_id == "media.video_lite.access"  # nosec B101
    assert loader.get_policy(policy_id) == {  # nosec B101
        "requests": {"rpm": 6000, "burst": 1.2},
        "scopes": ["user", "api_key", "ip"],
    }
