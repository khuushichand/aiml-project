from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from tldw_Server_API.app.services.app_lifecycle import is_lifecycle_draining
CONTROL_PLANE_DRAIN_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/ready",
        "/health/ready",
        "/healthz",
        "/api/v1/healthz",
        "/api/v1/health/live",
    }
)
CONTROL_PLANE_DRAIN_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {(method, path) for method in ("GET", "HEAD") for path in CONTROL_PLANE_DRAIN_PATHS}
)


def _is_allowlisted_control_plane_path(request: Request) -> bool:
    method = request.method.upper()
    path = request.url.path
    return (method, path) in CONTROL_PLANE_DRAIN_ALLOWLIST


class DrainGateMiddleware(BaseHTTPMiddleware):
    """Reject non-control-plane requests while shutdown is draining."""

    def __init__(self, app: FastAPI) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if is_lifecycle_draining(request.app) and not _is_allowlisted_control_plane_path(request):
            return JSONResponse(
                {"status": "not_ready", "reason": "shutdown_in_progress"},
                status_code=503,
            )
        return await call_next(request)


__all__ = [
    "CONTROL_PLANE_DRAIN_ALLOWLIST",
    "CONTROL_PLANE_DRAIN_PATHS",
    "DrainGateMiddleware",
    "_is_allowlisted_control_plane_path",
]
