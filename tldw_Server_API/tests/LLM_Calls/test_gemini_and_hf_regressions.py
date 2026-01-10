import json

import pytest

from tldw_Server_API.app.core.LLM_Calls import chat_calls as llm_calls
from tldw_Server_API.app.core.LLM_Calls import huggingface_api as hf_module
from tldw_Server_API.app.core.LLM_Calls.huggingface_api import HuggingFaceAPI
from tldw_Server_API.app.core.LLM_Calls.sse import sse_done


def test_google_streaming_handles_done_sentinel(monkeypatch):
    class DummyResponse:
        def __init__(self, raw_lines):
            self._raw_lines = raw_lines
            self.closed = False

        def raise_for_status(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self):
            for line in self._raw_lines:
                yield line

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

    closed = {"client": False}

    class DummyClient:
        def __init__(self, raw_lines):
            self._raw_lines = raw_lines

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            closed["client"] = True
            return False

        def stream(self, method, url, **kwargs):
            return DummyResponse(self._raw_lines)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.providers.google_adapter.http_client_factory",
        lambda *a, **k: DummyClient(raw_lines),
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
    assert closed["client"] is True


@pytest.mark.asyncio
async def test_huggingface_download_handles_head_failure(tmp_path, monkeypatch):
    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, *args, **kwargs):
            raise RuntimeError("head failed")

    def _client_factory(*args, **kwargs):
        return DummyAsyncClient()

    monkeypatch.setattr(hf_module, "create_async_client", _client_factory, raising=True)

    api = HuggingFaceAPI(token="fake-token")
    destination = tmp_path / "downloads" / "model.gguf"
    result = await api.download_file("org/model", "model.gguf", destination)

    assert result is False
    assert not destination.exists()
    assert not destination.with_suffix(".tmp").exists()
