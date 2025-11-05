from __future__ import annotations

import json
from typing import Any, Dict

import httpx
import pytest

from tldw_Server_API.app.core.LLM_Calls.providers.google_adapter import GoogleAdapter


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_GOOGLE", "1")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    monkeypatch.setenv("LOGURU_LEVEL", "ERROR")
    yield


def test_google_includes_candidate_count_when_n_set(monkeypatch):
    captured: Dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        assert request.method == "POST"
        assert request.url.path.endswith(":generateContent")
        payload = json.loads(request.content.decode("utf-8"))
        captured = payload
        data = {
            "responseId": "resp_cand",
            "candidates": [{"content": {"parts": [{"text": "hi"}]}}],
            "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 2},
        }
        return httpx.Response(200, json=data)

    def fake_create_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return httpx.Client(transport=_mock_transport(handler))

    import tldw_Server_API.app.core.http_client as hc
    monkeypatch.setattr(hc, "create_client", fake_create_client)
    import tldw_Server_API.app.core.LLM_Calls.providers.google_adapter as gmod
    monkeypatch.setattr(gmod, "_hc_create_client", fake_create_client)

    adapter = GoogleAdapter()
    req = {
        "model": "gemini-1.5-pro",
        "api_key": "sk-test",
        "n": 2,
        "messages": [{"role": "user", "content": "hi"}],
    }
    out = adapter.chat(req)
    assert out["object"] == "chat.completion"
    assert captured.get("candidateCount") == 2

