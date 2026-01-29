import pytest
from contextlib import asynccontextmanager
from types import SimpleNamespace


pytestmark = pytest.mark.unit


class DummySyncResponse:
    status_code = 200
    headers = {"content-type": "application/json"}
    url = "http://example.com"
    text = '{"ok": true}'

    def json(self):
        return {"ok": True}

    def raise_for_status(self) -> None:
        return None

    def close(self) -> None:
        return None


class DummyAsyncResponse:
    status_code = 200
    headers = {"content-type": "application/json"}
    url = "http://example.com"
    text = '{"ok": true}'

    def json(self):
        return {"ok": True}

    def raise_for_status(self) -> None:
        return None

    async def aclose(self) -> None:
        return None


def test_httpx_adapter_request_passes_through(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    calls = {}

    def fake_httpx_request_io(**kwargs):
        calls["kwargs"] = kwargs
        return DummySyncResponse()

    monkeypatch.setattr(hc, "_httpx_request_io", fake_httpx_request_io)

    adapter = hc.HttpxAdapter()
    resp = adapter.request(method="GET", url="http://example.com", headers={"x": "y"}, client=object())

    assert isinstance(resp, DummySyncResponse)
    assert calls["kwargs"]["method"] == "GET"
    assert calls["kwargs"]["url"] == "http://example.com"
    assert calls["kwargs"]["headers"] == {"x": "y"}


@pytest.mark.asyncio
async def test_httpx_adapter_arequest_passes_through(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    calls = {}

    async def fake_httpx_arequest_io(**kwargs):
        calls["kwargs"] = kwargs
        return DummyAsyncResponse()

    monkeypatch.setattr(hc, "_httpx_arequest_io", fake_httpx_arequest_io)

    adapter = hc.HttpxAdapter()
    resp = await adapter.arequest(method="POST", url="http://example.com", json={"k": "v"}, client=object())

    assert isinstance(resp, DummyAsyncResponse)
    assert calls["kwargs"]["method"] == "POST"
    assert calls["kwargs"]["url"] == "http://example.com"
    assert calls["kwargs"]["json"] == {"k": "v"}


@pytest.mark.asyncio
async def test_httpx_adapter_stream_bytes_passes_through(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    @asynccontextmanager
    async def fake_httpx_stream_io(**_kwargs):
        async def iter_bytes():
            yield b"one"
            yield b"two"

        resp = SimpleNamespace(status_code=200, request=SimpleNamespace(url="http://example.com"))
        yield resp, iter_bytes()

    monkeypatch.setattr(hc, "_httpx_stream_io", fake_httpx_stream_io)

    adapter = hc.HttpxAdapter()
    chunks = [chunk async for chunk in adapter.stream_bytes(method="GET", url="http://example.com", client=object())]

    assert chunks == [b"one", b"two"]


@pytest.mark.asyncio
async def test_httpx_adapter_stream_sse_passes_through(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    @asynccontextmanager
    async def fake_httpx_stream_io(**_kwargs):
        async def iter_bytes():
            yield b"data: hello\n\n"

        resp = SimpleNamespace(status_code=200, request=SimpleNamespace(url="http://example.com"))
        yield resp, iter_bytes()

    monkeypatch.setattr(hc, "_httpx_stream_io", fake_httpx_stream_io)

    adapter = hc.HttpxAdapter()
    events = [ev async for ev in adapter.stream_sse(url="http://example.com/stream", client=object())]

    assert len(events) == 1
    assert events[0].data == "hello"


def test_aiohttp_adapter_request_not_supported():
    from tldw_Server_API.app.core import http_client as hc

    adapter = hc.AiohttpAdapter()
    with pytest.raises(NotImplementedError):
        adapter.request(method="GET", url="http://example.com")


@pytest.mark.asyncio
async def test_aiohttp_adapter_arequest_passes_through(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    calls = {}

    async def fake_aiohttp_request_io(**kwargs):
        calls["kwargs"] = kwargs
        return DummyAsyncResponse()

    monkeypatch.setattr(hc, "_aiohttp_request_io", fake_aiohttp_request_io)

    adapter = hc.AiohttpAdapter()
    resp = await adapter.arequest(method="GET", url="http://example.com", client=object())

    assert isinstance(resp, DummyAsyncResponse)
    assert calls["kwargs"]["url"] == "http://example.com"


@pytest.mark.asyncio
async def test_aiohttp_adapter_stream_bytes_passes_through(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    @asynccontextmanager
    async def fake_aiohttp_stream_io(**_kwargs):
        async def iter_bytes():
            yield b"alpha"

        resp = SimpleNamespace(status=200, url="http://example.com")
        yield resp, iter_bytes()

    monkeypatch.setattr(hc, "_aiohttp_stream_io", fake_aiohttp_stream_io)

    adapter = hc.AiohttpAdapter()
    chunks = [chunk async for chunk in adapter.stream_bytes(method="GET", url="http://example.com", client=object())]

    assert chunks == [b"alpha"]


@pytest.mark.asyncio
async def test_aiohttp_adapter_stream_sse_passes_through(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    @asynccontextmanager
    async def fake_aiohttp_stream_io(**_kwargs):
        async def iter_bytes():
            yield b"data: world\n\n"

        resp = SimpleNamespace(status=200, url="http://example.com")
        yield resp, iter_bytes()

    monkeypatch.setattr(hc, "_aiohttp_stream_io", fake_aiohttp_stream_io)

    adapter = hc.AiohttpAdapter()
    events = [ev async for ev in adapter.stream_sse(url="http://example.com/stream", client=object())]

    assert len(events) == 1
    assert events[0].data == "world"
