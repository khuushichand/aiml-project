from __future__ import annotations

import re
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


SAFE_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
MAX_REQUEST_ID_LENGTH = 128


def _generate_request_id() -> str:
    return str(uuid.uuid4())


def _clean_request_id(value: str | None) -> str:
    if not value:
        return _generate_request_id()

    candidate = value.strip()
    if not candidate:
        return _generate_request_id()

    if len(candidate) > MAX_REQUEST_ID_LENGTH or not SAFE_REQUEST_ID_PATTERN.fullmatch(candidate):
        return _generate_request_id()

    return candidate


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds/propagates a sanitized X-Request-ID header and stores it in request.state.request_id.

    Also propagates request_id and optional session_id into OpenTelemetry baggage for log/trace correlation.
    Optional header for session: X-Session-ID (sanitized similarly to request id).
    """

    def __init__(self, app, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = _clean_request_id(request.headers.get(self.header_name))
        session_id_hdr = request.headers.get("X-Session-ID")
        session_id = _clean_request_id(session_id_hdr) if session_id_hdr else None
        request.state.request_id = request_id
        if session_id:
            request.state.session_id = session_id

        # Inject into OTEL baggage for downstream spans/logs
        try:
            from tldw_Server_API.app.core.Metrics.traces import get_tracing_manager
            tm = get_tracing_manager()
            tm.set_baggage("request_id", request_id)
            if session_id:
                tm.set_baggage("session_id", session_id)
        except Exception:
            pass

        response: Response = await call_next(request)
        response.headers.setdefault(self.header_name, request_id)
        return response
