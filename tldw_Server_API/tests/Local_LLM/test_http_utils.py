import asyncio
import httpx
import pytest

from tldw_Server_API.app.core.Local_LLM.http_utils import request_json


class FakeClient:
    def __init__(self):
        self.calls = 0

    async def request(self, method, url, json=None, headers=None):
        self.calls += 1
        req = httpx.Request(method, url)
        if self.calls == 1:
            resp = httpx.Response(500, request=req, text="server error")
            # Mimic status without raising; request_json should retry on 5xx
            return resp
        return httpx.Response(200, request=req, json={"ok": True})


@pytest.mark.asyncio
async def test_request_json_retries_on_5xx():
    client = FakeClient()
    data = await request_json(client, "GET", "http://x/y", retries=1, backoff=0)
    assert data["ok"] is True
    assert client.calls == 2
