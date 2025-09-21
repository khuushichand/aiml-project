from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from loguru import logger
import os

from tldw_Server_API.app.core.Metrics import get_metrics_registry


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.registry = get_metrics_registry()

    async def dispatch(self, request: Request, call_next: Callable):
        response: Response = await call_next(request)
        if self.enabled:
            # Best-effort security headers; HSTS assumes TLS at proxy
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=()")
            # HSTS only if forwarded proto is https (basic heuristic)
            if request.headers.get("x-forwarded-proto", "").lower() == "https":
                response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
            self.registry.increment("security_headers_responses_total", 1)
        return response
