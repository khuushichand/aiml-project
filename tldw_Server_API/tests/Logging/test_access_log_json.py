import io
import json
import os

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from tldw_Server_API.app.core.Security.request_id_middleware import RequestIDMiddleware
from tldw_Server_API.app.core.Logging.access_log_middleware import AccessLogMiddleware
from loguru import logger


def _make_app() -> FastAPI:
    app = FastAPI()

    # Minimal route for access log emission
    @app.get("/ping")
    async def ping():  # pragma: no cover - simple passthrough
        # Emit a direct loguru line to validate sink capture
        logger.bind(test_marker=True).info("route ping")
        return JSONResponse({"ok": True}, status_code=200)

    # Middlewares needed for request_id propagation and access logging
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(AccessLogMiddleware)
    return app


@pytest.mark.asyncio
async def test_access_log_emits_json_with_core_fields(monkeypatch):
    # Ensure JSON logging style is conceptually enabled (for documentation parity)
    monkeypatch.setenv("LOG_JSON", "true")

    # Prepare AccessLogMiddleware instance (standalone)
    alm = AccessLogMiddleware(object())

    # Monkeypatch the module-level logger used by AccessLogMiddleware to capture fields
    from tldw_Server_API.app.core.Logging import access_log_middleware as alm_mod

    captured = []

    class _StubLogger:
        def __init__(self, extra=None):
            self._extra = extra or {}

        def bind(self, **kwargs):
            new_extra = dict(self._extra)
            new_extra.update(kwargs)
            return _StubLogger(new_extra)

        def log(self, level, message):
            captured.append({"level": level, "message": message, "extra": dict(self._extra)})

    monkeypatch.setattr(alm_mod, "logger", _StubLogger(), raising=True)

    # Build a minimal Starlette Request with X-Request-ID
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/ping",
        "raw_path": b"/ping",
        "headers": [(b"x-request-id", b"test-request-id"), (b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    req = Request(scope)

    async def _call_next(_req: Request) -> Response:
        return Response(content=b"{}", media_type="application/json", status_code=200)

    # Invoke middleware directly
    resp = await alm.dispatch(req, _call_next)
    assert resp.status_code == 200

    # Validate captured access-log record
    assert captured, "no access-log record captured"
    rec = captured[-1]
    extra = rec.get("extra") or {}
    assert extra.get("request_id")  # synthesized or header value
    assert extra.get("method") == "GET"
    status_val = extra.get("status")
    assert status_val == 200 or status_val == "200"
    assert extra.get("path") == "/ping"
    assert isinstance(extra.get("duration_ms"), int)
