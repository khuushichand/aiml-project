import json
import os
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


def test_gemini_filedata_mapping_for_urls_and_multi_parts(monkeypatch):
    # Enable URL mapping for images/audio/video
    monkeypatch.setenv("LLM_ADAPTERS_GEMINI_IMAGE_URLS_BETA", "1")
    monkeypatch.setenv("LLM_ADAPTERS_GEMINI_AUDIO_URLS_BETA", "1")
    monkeypatch.setenv("LLM_ADAPTERS_GEMINI_VIDEO_URLS_BETA", "1")

    captured: Dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        payload = json.loads(request.content.decode("utf-8"))
        captured = payload
        return httpx.Response(200, json={"responseId": "r", "candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    def fake_create_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return httpx.Client(transport=_mock_transport(handler))

    import tldw_Server_API.app.core.http_client as hc
    monkeypatch.setattr(hc, "create_client", fake_create_client)
    import tldw_Server_API.app.core.LLM_Calls.providers.google_adapter as gmod
    monkeypatch.setattr(gmod, "_hc_create_client", fake_create_client)
    monkeypatch.setattr(gmod, "http_client_factory", fake_create_client)

    adapter = GoogleAdapter()
    request = {
        "model": "models/gemini-pro",
        "api_key": "sk-test",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
                    {"type": "audio_url", "audio_url": {"url": "https://example.com/a.mp3"}},
                    {"type": "video_url", "video_url": {"url": "https://example.com/v.mp4"}},
                ],
            }
        ],
    }
    out = adapter.chat(request)
    assert out["choices"][0]["message"]["content"] == "ok"
    parts = captured.get("contents")[0]["parts"]
    # Expect multiple parts including fileData entries
    assert any("fileData" in p and p["fileData"]["mimeType"].startswith("image/") for p in parts)
    assert any("fileData" in p and p["fileData"]["mimeType"].startswith("audio/") for p in parts)
    assert any("fileData" in p and p["fileData"]["mimeType"].startswith("video/") for p in parts)


def test_gemini_tool_calls_and_usage_mapping(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        # Return a functionCall in parts and usageMetadata
        data = {
            "responseId": "resp_x",
            "candidates": [
                {"content": {"parts": [{"functionCall": {"name": "do_it", "args": {"x": 1}}}]}}
            ],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }
        return httpx.Response(200, json=data)

    def fake_create_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return httpx.Client(transport=_mock_transport(handler))

    import tldw_Server_API.app.core.http_client as hc
    monkeypatch.setattr(hc, "create_client", fake_create_client)
    import tldw_Server_API.app.core.LLM_Calls.providers.google_adapter as gmod
    monkeypatch.setattr(gmod, "_hc_create_client", fake_create_client)
    monkeypatch.setattr(gmod, "http_client_factory", fake_create_client)

    adapter = GoogleAdapter()
    req = {"model": "models/gemini-pro", "api_key": "k", "messages": [{"role": "user", "content": "hi"}]}
    out = adapter.chat(req)
    msg = out["choices"][0]["message"]
    assert msg.get("tool_calls") and msg["tool_calls"][0]["function"]["name"] == "do_it"
    # usage mapped through
    assert isinstance(out.get("usage"), dict)
