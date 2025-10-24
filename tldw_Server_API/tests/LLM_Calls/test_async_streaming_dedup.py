import asyncio
import httpx
import pytest
import requests
from unittest.mock import Mock
from typing import Iterable

from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import (
    get_openai_embeddings,
    get_openai_embeddings_batch,
    chat_with_openai,
    chat_with_openai_async,
    chat_with_groq_async,
    chat_with_openrouter_async,
    chat_with_anthropic_async,
)
from tldw_Server_API.app.core.LLM_Calls.sse import sse_done
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError, ChatProviderError


class _DummyStream:
    """Minimal async stream stub that emits predefined lines."""

    def __init__(self, lines: Iterable[str]):
        self._lines = list(lines)
        self.status_code = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    def aiter_lines(self):
        async def _gen():
            for line in self._lines:
                yield line

        return _gen()


class _DummyAsyncClient:
    """AsyncClient drop-in used to intercept streaming calls."""

    def __init__(self, stream: _DummyStream):
        self._stream = stream

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, *args, **kwargs):
        return self._stream

    async def post(self, *args, **kwargs):
        raise AssertionError("Non-streaming POST should not be invoked in these tests.")


def _mock_session_with_response(vector):
    session = Mock()
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"data": vector}
    response.raise_for_status = Mock()
    session.post.return_value = response
    session.close = Mock()
    return session


def test_get_openai_embeddings_uses_timeout_and_closes(monkeypatch):
    session = _mock_session_with_response([{"embedding": [0.1, 0.2]}])

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries",
        lambda **kwargs: session,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {
            "openai_api": {
                "api_key": "test-key",
                "api_timeout": 12,
                "api_retries": 2,
                "api_retry_delay": 0.5,
            }
        },
    )

    result = get_openai_embeddings("hello", "text-embedding-3-small")

    session.post.assert_called_once()
    assert session.post.call_args[1]["timeout"] == 12
    session.close.assert_called_once()
    assert result == [0.1, 0.2]


def test_get_openai_embeddings_batch_uses_timeout_and_closes(monkeypatch):
    session = _mock_session_with_response(
        [
            {"embedding": [0.1, 0.2]},
            {"embedding": [0.3, 0.4]},
        ]
    )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries",
        lambda **kwargs: session,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {
            "openai_api": {
                "api_key": "test-key",
                "api_timeout": 30,
                "api_retries": 1,
                "api_retry_delay": 0.1,
            }
        },
    )

    result = get_openai_embeddings_batch(["a", "b"], "text-embedding-3-small")

    session.post.assert_called_once()
    assert session.post.call_args[1]["timeout"] == 30
    session.close.assert_called_once()
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_get_openai_embeddings_respects_api_base(monkeypatch):
    session = _mock_session_with_response([{"embedding": [0.5, 0.6]}])

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries",
        lambda **kwargs: session,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {
            "openai_api": {
                "api_key": "test-key",
                "api_base_url": "https://custom.openai.local/v1",
            }
        },
    )

    get_openai_embeddings("hello", "text-embedding-3-small")

    session.post.assert_called_once()
    called_url = session.post.call_args[0][0]
    assert called_url == "https://custom.openai.local/v1/embeddings"


def test_get_openai_embeddings_batch_respects_api_base(monkeypatch):
    session = _mock_session_with_response(
        [
            {"embedding": [0.1]},
            {"embedding": [0.2]},
        ]
    )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries",
        lambda **kwargs: session,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {
            "openai_api": {
                "api_key": "test-key",
                "api_base_url": "https://custom.openai.local/api/v1",
            }
        },
    )

    get_openai_embeddings_batch(["a", "b"], "text-embedding-3-small")

    session.post.assert_called_once()
    called_url = session.post.call_args[0][0]
    assert called_url == "https://custom.openai.local/api/v1/embeddings"


def test_chat_with_openai_logs_payload_metadata(monkeypatch):
    captured = []

    def fake_debug(message, *args, **kwargs):
        captured.append(str(message))

    class DummyResponse:
        status_code = 400
        text = "bad request"

        def raise_for_status(self):
            raise requests.exceptions.HTTPError(response=self)

        def json(self):
            return {}

    class DummySession:
        def post(self, *args, **kwargs):
            return DummyResponse()

        def close(self):
            return None

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.logging.debug",
        fake_debug,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries",
        lambda **kwargs: DummySession(),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {"openai_api": {"api_key": "key"}},
    )

    with pytest.raises(ChatBadRequestError):
        chat_with_openai(
            [{"role": "user", "content": "hi"}],
            api_key="key",
            streaming=False,
        )

    payload_logs = [msg for msg in captured if "OpenAI Request Payload (excluding messages)" in msg]
    assert payload_logs, "Expected payload metadata log to be recorded."
    assert "'stream': False" in payload_logs[-1]


def _patch_async_client(monkeypatch, lines):
    stream = _DummyStream(lines)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.httpx.AsyncClient",
        lambda *args, **kwargs: _DummyAsyncClient(stream),
    )


@pytest.mark.asyncio
async def test_chat_with_openai_async_no_duplicate_done(monkeypatch):
    _patch_async_client(
        monkeypatch,
        [
            'data: {"choices":[{"delta":{"content":"hi"}}]}',
            "data: [DONE]",
        ],
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {"openai_api": {"api_key": "key", "api_timeout": 15}},
    )

    stream = await chat_with_openai_async(
        [{"role": "user", "content": "hi"}], api_key="key", streaming=True
    )
    chunks = [chunk async for chunk in stream]

    assert chunks.count(sse_done()) == 1
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_chat_with_groq_async_no_duplicate_done(monkeypatch):
    _patch_async_client(
        monkeypatch,
        [
            'data: {"choices":[{"delta":{"content":"hi"}}]}',
            "data: [DONE]",
        ],
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {"groq_api": {"api_key": "key", "api_timeout": 15}},
    )

    stream = await chat_with_groq_async(
        [{"role": "user", "content": "hi"}], api_key="key", streaming=True
    )
    chunks = [chunk async for chunk in stream]

    assert chunks.count(sse_done()) == 1
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_chat_with_openrouter_async_no_duplicate_done(monkeypatch):
    _patch_async_client(
        monkeypatch,
        [
            'data: {"choices":[{"delta":{"content":"hi"}}]}',
            "data: [DONE]",
        ],
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {
            "openrouter_api": {
                "api_key": "key",
                "api_timeout": 15,
                "site_url": "http://localhost",
                "site_name": "pytest",
            }
        },
    )

    stream = await chat_with_openrouter_async(
        [{"role": "user", "content": "hi"}], api_key="key", streaming=True
    )
    chunks = [chunk async for chunk in stream]

    assert chunks.count(sse_done()) == 1
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_chat_with_openai_async_retries_request_error(monkeypatch):
    request = httpx.Request("POST", "https://retry.test")
    attempts = [
        httpx.RequestError("boom", request=request),
        _DummyStream(
            [
                'data: {"choices":[{"delta":{"content":"hi"}}]}',
                "data: [DONE]",
            ]
        ),
    ]

    class FlakyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, *args, **kwargs):
            action = attempts.pop(0)
            if isinstance(action, Exception):
                raise action
            return action

        async def post(self, *args, **kwargs):
            raise AssertionError("Non-streaming POST should not be invoked in this test.")

    sleep_calls = []

    async def fake_sleep(duration):
        sleep_calls.append(duration)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.asyncio.sleep",
        fake_sleep,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.httpx.AsyncClient",
        lambda *args, **kwargs: FlakyAsyncClient(),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {
            "openai_api": {
                "api_key": "key",
                "api_timeout": 15,
                "api_retries": 1,
                "api_retry_delay": 0.25,
            }
        },
    )

    stream = await chat_with_openai_async(
        [{"role": "user", "content": "hi"}],
        api_key="key",
        streaming=True,
    )
    chunks = [chunk async for chunk in stream]

    assert chunks.count(sse_done()) == 1
    assert len(chunks) == 2
    assert sleep_calls == [0.25]
    assert attempts == []


@pytest.mark.asyncio
async def test_chat_with_openai_async_non_streaming_exhausts_retries(monkeypatch):
    request = httpx.Request("POST", "https://retry.test")
    attempts = [
        httpx.RequestError("boom-1", request=request),
        httpx.RequestError("boom-2", request=request),
    ]

    class AlwaysFailAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise attempts.pop(0)

        def stream(self, *args, **kwargs):
            raise AssertionError("Stream should not be used in this test.")

    sleep_calls = []

    async def fake_sleep(duration):
        sleep_calls.append(duration)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.asyncio.sleep",
        fake_sleep,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.httpx.AsyncClient",
        lambda *args, **kwargs: AlwaysFailAsyncClient(),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {
            "openai_api": {
                "api_key": "key",
                "api_timeout": 15,
                "api_retries": 1,
                "api_retry_delay": 0.1,
            }
        },
    )

    with pytest.raises(ChatProviderError):
        await chat_with_openai_async(
            [{"role": "user", "content": "hi"}],
            api_key="key",
            streaming=False,
        )

    assert sleep_calls == [0.1]
    assert attempts == []


@pytest.mark.asyncio
async def test_chat_with_anthropic_async_stream_tool_calls(monkeypatch):
    _patch_async_client(
        monkeypatch,
        [
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"tool_1","name":"lookup","input":{}}}',
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"city\\":\\"Paris\\"}"}}',
            'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}',
        ],
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
        lambda: {"anthropic_api": {"api_key": "key", "api_timeout": 15}},
    )

    stream = await chat_with_anthropic_async(
        [{"role": "user", "content": "Hi"}], api_key="key", streaming=True
    )
    chunks = [chunk async for chunk in stream]

    assert any('"tool_calls"' in chunk for chunk in chunks)
    assert chunks.count(sse_done()) == 1
