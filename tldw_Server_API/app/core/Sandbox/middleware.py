from __future__ import annotations

from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SandboxArtifactTraversalGuardMiddleware(BaseHTTPMiddleware):
    """Reject path traversal attempts for Sandbox artifact routes before routing.

    Specifically targets raw `..` segments under `/api/v1/sandbox/runs/{id}/artifacts/...`.
    Returns HTTP 400 on detection.
    """

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            path = request.url.path or ""
            raw_path_b = request.scope.get("raw_path") or b""
            raw_path = raw_path_b.decode("latin-1", errors="ignore") if isinstance(raw_path_b, (bytes, bytearray)) else str(raw_path_b or "")

            def _has_traversal(p: str) -> bool:
                return "/../" in p or p.endswith("/..") or p.startswith("../")

            def _is_sandbox_runs(p: str) -> bool:
                return p.startswith("/api/v1/sandbox/runs/")

            # Prefer raw_path for detection when available, fallback to normalized path
            # Reject traversal anywhere under sandbox runs (defense in depth)
            for p in (raw_path, path):
                if p and _is_sandbox_runs(p) and _has_traversal(p):
                    return JSONResponse({"detail": "Path traversal detected"}, status_code=400)
        except Exception as guard_error:
            # Never fail a request due to guard errors
            _ = guard_error
        return await call_next(request)
