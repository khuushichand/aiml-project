import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.endpoints import messages as messages_endpoint


class _DummyHTTPStatusError(Exception):
    def __init__(self, response):
        super().__init__("upstream status error")
        self.response = response


class _DummyRequestError(Exception):
    pass


class _FailingResponse:
    def __init__(self, *, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        raise _DummyHTTPStatusError(self)

    def json(self):
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


class _FailingPostClient:
    def __init__(self, response: _FailingResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *_args, **_kwargs):
        return self._response


class _RaisingPostClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *_args, **_kwargs):
        raise _DummyRequestError("network down")


class _FailingStreamContext:
    def __init__(self, response: _FailingResponse):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FailingStreamClient:
    def __init__(self, response: _FailingResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, *_args, **_kwargs):
        return _FailingStreamContext(self._response)


@pytest.mark.asyncio
async def test_native_post_json_maps_http_status_error(monkeypatch):
    response = _FailingResponse(
        status_code=401,
        payload={"error": {"message": "unauthorized"}},
        text="unauthorized",
    )
    monkeypatch.setattr(messages_endpoint, "async_http_client_factory", lambda timeout=None: _FailingPostClient(response))

    with pytest.raises(HTTPException) as exc_info:
        await messages_endpoint._native_post_json(
            "https://example.invalid/v1/messages",
            {"x-api-key": "test"},
            {"model": "x"},
            timeout=30.0,
            provider="anthropic",
            operation="messages",
        )

    assert exc_info.value.status_code == 401
    detail = exc_info.value.detail
    assert detail["provider"] == "anthropic"
    assert detail["operation"] == "messages"
    assert "upstream_error" in detail


@pytest.mark.asyncio
async def test_native_post_json_maps_request_error_to_502(monkeypatch):
    monkeypatch.setattr(messages_endpoint, "async_http_client_factory", lambda timeout=None: _RaisingPostClient())

    with pytest.raises(HTTPException) as exc_info:
        await messages_endpoint._native_post_json(
            "https://example.invalid/v1/messages",
            {"x-api-key": "test"},
            {"model": "x"},
            timeout=30.0,
            provider="anthropic",
            operation="messages",
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["provider"] == "anthropic"


@pytest.mark.asyncio
async def test_prepare_native_stream_iterator_maps_preflight_status_error(monkeypatch):
    response = _FailingResponse(
        status_code=429,
        payload={"error": {"message": "rate limited"}},
        text="rate limited",
    )
    monkeypatch.setattr(messages_endpoint, "async_http_client_factory", lambda timeout=None: _FailingStreamClient(response))

    with pytest.raises(HTTPException) as exc_info:
        await messages_endpoint._prepare_native_stream_iterator(
            "https://example.invalid/v1/messages",
            {"x-api-key": "test"},
            {"model": "x"},
            timeout=30.0,
            provider="anthropic",
            operation="messages.stream",
        )

    assert exc_info.value.status_code == 429
    detail = exc_info.value.detail
    assert detail["provider"] == "anthropic"
    assert detail["operation"] == "messages.stream"
