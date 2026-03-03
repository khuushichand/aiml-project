import os
import httpx

from tldw_Server_API.app.core.LLM_Calls.providers.google_adapter import GoogleAdapter


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_google_gemini_streaming_sse_passthrough(monkeypatch):
    # Force native httpx path
    monkeypatch.setenv("LLM_ADAPTERS_NATIVE_HTTP_GOOGLE", "1")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_google_gemini_streaming_sse_passthrough")

    sse_body = (
        "data: {\"delta\": \"Hello\"}\n\n"
        "data: {\"delta\": \" world\"}\n\n"
        "data: [DONE]\n\n"
    ).encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith(":streamGenerateContent")
        # Return a streaming-like response; iter_lines will parse the content into lines
        return httpx.Response(200, content=sse_body)

    def fake_create_client(*args, **kwargs) -> httpx.Client:
        return httpx.Client(transport=_mock_transport(handler))

    import tldw_Server_API.app.core.http_client as hc
    monkeypatch.setattr(hc, "create_client", fake_create_client)
    import tldw_Server_API.app.core.LLM_Calls.providers.google_adapter as gmod
    monkeypatch.setattr(gmod, "_hc_create_client", fake_create_client)
    monkeypatch.setattr(gmod, "http_client_factory", fake_create_client)

    adapter = GoogleAdapter()
    req = {
        "model": "gemini-2.5-pro",
        "api_key": "sk-test",
        "messages": [{"role": "user", "content": "hi"}],
    }
    lines = list(adapter.stream(req))
    # Lines should match our SSE body split
    assert lines[0].startswith("data: ")
    assert lines[-1].strip() == "data: [DONE]"
