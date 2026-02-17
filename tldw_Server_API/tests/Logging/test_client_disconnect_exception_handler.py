import json

import pytest
from starlette.requests import ClientDisconnect, Request

from tldw_Server_API.app.main import (
    _client_disconnect_exception_handler,
    _global_unhandled_exception_handler,
)


def _build_request(method: str = "GET", path: str = "/api/v1/mcp/health") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    async def _receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, _receive)


@pytest.mark.asyncio
async def test_client_disconnect_exception_handler_returns_499():
    request = _build_request()

    response = await _client_disconnect_exception_handler(request, ClientDisconnect())

    assert response.status_code == 499
    assert json.loads(response.body.decode("utf-8")) == {"detail": "Client disconnected"}


@pytest.mark.asyncio
async def test_global_unhandled_exception_handler_treats_client_disconnect_as_499():
    request = _build_request(method="POST")

    response = await _global_unhandled_exception_handler(request, ClientDisconnect())

    assert response.status_code == 499
    assert json.loads(response.body.decode("utf-8")) == {"detail": "Client disconnected"}
