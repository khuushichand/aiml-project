from __future__ import annotations

from typing import Any, Dict


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_obj: Dict[str, Any] | None = None):
        self.status_code = status_code
        self._json = json_obj or {"object": "chat.completion"}

    def raise_for_status(self):
        if 400 <= self.status_code:
            import httpx
            request = httpx.Request("POST", "http://example/v1/chat/completions")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        return self._json

    def close(self):
        return None


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.last_post = None

    def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any], timeout: int):
        self.last_post = {"url": url, "headers": headers, "json": json, "timeout": timeout}
        return _FakeResponse(200)

    def close(self):
        return None


def test_local_adapter_merges_extra_body_and_headers():
    from tldw_Server_API.app.core.LLM_Calls.providers.local_adapters import LocalLLMAdapter

    captured: Dict[str, Any] = {}

    def _factory(timeout: int):
        client = _FakeClient(timeout=timeout)
        captured["client"] = client
        return client

    adapter = LocalLLMAdapter()
    request = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "dummy",
        "temperature": 0.1,
        "extra_body": {"temperature": 0.9, "x_extra": "y"},
        "extra_headers": {
            "Authorization": "Bearer override",
            "content-type": "text/plain",
            "X-Test": "1",
        },
        "app_config": {
            "local_llm": {
                "api_ip": "http://example",
                "api_key": "k",
                "model": "dummy",
            }
        },
        "http_client_factory": _factory,
    }
    _ = adapter.chat(request)
    payload = captured["client"].last_post["json"]
    headers = captured["client"].last_post["headers"]
    assert payload.get("temperature") == 0.1
    assert payload.get("x_extra") == "y"
    assert headers.get("Authorization") == "Bearer k"
    assert headers.get("Content-Type") == "application/json"
    assert headers.get("X-Test") == "1"
    assert "content-type" not in headers
