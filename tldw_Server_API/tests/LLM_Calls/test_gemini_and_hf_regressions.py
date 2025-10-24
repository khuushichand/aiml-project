import json

import pytest

from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as llm_calls
from tldw_Server_API.app.core.LLM_Calls import huggingface_api as hf_module
from tldw_Server_API.app.core.LLM_Calls.huggingface_api import HuggingFaceAPI
from tldw_Server_API.app.core.LLM_Calls.sse import sse_done


def test_google_streaming_handles_done_sentinel(monkeypatch):
    pytest.importorskip("requests")

    def fake_config():
        return {
            "google_api": {
                "api_key": "test-key",
                "model": "gemini-pro-test",
            }
        }

    monkeypatch.setattr(llm_calls, "load_and_log_configs", fake_config)

    class DummyResponse:
        def __init__(self, raw_lines):
            self._raw_lines = raw_lines

        def raise_for_status(self):
            return None

        def iter_lines(self):
            for line in self._raw_lines:
                yield line

        def close(self):
            return None

    class DummySession:
        def __init__(self, raw_lines):
            self._raw_lines = raw_lines
            self.closed = False

        def post(self, *args, **kwargs):
            return DummyResponse(self._raw_lines)

        def close(self):
            self.closed = True

    text_chunk = json.dumps(
        {
            "candidates": [
                {
                    "content": {"parts": [{"text": "hello"}]},
                    "finishReason": "STOP",
                }
            ]
        }
    )
    raw_lines = [
        f"data: {text_chunk}".encode("utf-8"),
        b"data: [DONE]",
    ]

    dummy_session = DummySession(raw_lines)
    monkeypatch.setattr(
        llm_calls, "create_session_with_retries", lambda **_: dummy_session
    )

    generator = llm_calls.chat_with_google(
        input_data=[{"role": "user", "content": "Ping?"}],
        streaming=True,
        api_key="test-key",
        model="gemini-pro-test",
    )
    chunks = list(generator)

    first_payload = json.loads(chunks[0][len("data: ") :])
    assert first_payload["choices"][0]["delta"]["content"] == "hello"
    assert sse_done() in chunks
    assert dummy_session.closed is True


@pytest.mark.asyncio
async def test_huggingface_download_handles_head_failure(tmp_path, monkeypatch):
    httpx_mod = pytest.importorskip("httpx")

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, *args, **kwargs):
            raise httpx_mod.HTTPError("head failed")

    monkeypatch.setattr(hf_module.httpx, "AsyncClient", DummyAsyncClient, raising=True)

    api = HuggingFaceAPI(token="fake-token")
    destination = tmp_path / "downloads" / "model.gguf"
    result = await api.download_file("org/model", "model.gguf", destination)

    assert result is False
    assert not destination.exists()
    assert not destination.with_suffix(".tmp").exists()
