from __future__ import annotations

import httpx
import pytest

from tldw_Server_API.tests.e2e.fixtures import APIClient


@pytest.mark.unit
def test_e2e_apiclient_stream_passthrough():
    seen: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, text="ok")

    underlying = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://testserver",
    )
    client = APIClient(client=underlying, auto_auth=False)
    try:
        with client.stream("GET", "/api/v1/health") as response:
            assert response.status_code == 200
            assert response.text == "ok"
    finally:
        client.close()

    assert seen == {"method": "GET", "path": "/api/v1/health"}
