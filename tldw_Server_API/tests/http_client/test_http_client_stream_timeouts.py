import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.unit


def _has_httpx():
    try:
        import httpx  # noqa: F401
        return True
    except Exception:
        return False


requires_httpx = pytest.mark.skipif(not _has_httpx(), reason="httpx not installed")


class StreamResponse:
    def __init__(self, url: str, status_code: int = 200) -> None:
        self.status_code = status_code
        self.request = SimpleNamespace(url=url)

    def raise_for_status(self) -> None:
        return None


class AioStreamResponse:
    def __init__(self, url: str, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self.url = url
        self.headers = headers or {}

    async def read(self) -> bytes:
        return b""


@requires_httpx
@pytest.mark.asyncio
async def test_stream_bytes_retries_http_503_before_first_chunk_httpx(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc
    import httpx

    calls = {"n": 0}

    @asynccontextmanager
    async def fake_httpx_stream_io(**_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            request = httpx.Request("POST", "http://93.184.216.34/stream")
            response = httpx.Response(503, request=request)

            async def iter_bytes():
                if False:  # pragma: no cover
                    yield b""

            yield response, iter_bytes()
            return

        async def iter_bytes():
            yield b"ok"

        resp = StreamResponse("http://93.184.216.34/stream")
        yield resp, iter_bytes()

    monkeypatch.setattr(hc, "_httpx_stream_io", fake_httpx_stream_io)

    chunks = []
    async for chunk in hc.astream_bytes(
        method="POST",
        url="http://93.184.216.34/stream",
        client=object(),
        retry=hc.RetryPolicy(attempts=2, retry_on_unsafe=True),
    ):
        chunks.append(chunk)

    assert calls["n"] == 2
    assert chunks == [b"ok"]


@requires_httpx
@pytest.mark.asyncio
async def test_stream_bytes_honors_date_form_retry_after_before_first_chunk_httpx(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc
    import httpx

    calls = {"n": 0}
    delays: list[float] = []
    retry_after = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=5), usegmt=True)

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    @asynccontextmanager
    async def fake_httpx_stream_io(**_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            request = httpx.Request("POST", "http://93.184.216.34/stream")
            response = httpx.Response(
                503,
                request=request,
                headers={"Retry-After": retry_after},
            )

            async def iter_bytes():
                if False:  # pragma: no cover
                    yield b""

            yield response, iter_bytes()
            return

        async def iter_bytes():
            yield b"ok"

        resp = StreamResponse("http://93.184.216.34/stream")
        yield resp, iter_bytes()

    monkeypatch.setattr(hc, "_httpx_stream_io", fake_httpx_stream_io)
    monkeypatch.setattr(hc.asyncio, "sleep", fake_sleep)

    chunks = []
    async for chunk in hc.astream_bytes(
        method="POST",
        url="http://93.184.216.34/stream",
        client=object(),
        retry=hc.RetryPolicy(attempts=2, retry_on_unsafe=True),
    ):
        chunks.append(chunk)

    assert calls["n"] == 2
    assert chunks == [b"ok"]
    assert len(delays) == 1
    assert delays[0] >= 3.0


@pytest.mark.asyncio
async def test_stream_bytes_retries_aiohttp_transport_error_before_first_chunk(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    calls = {"n": 0}

    @asynccontextmanager
    async def fake_aiohttp_stream_io(**_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("socket reset")

        async def iter_bytes():
            yield b"ok"

        yield AioStreamResponse("http://93.184.216.34/stream"), iter_bytes()

    monkeypatch.setattr(hc, "aiohttp", object())
    monkeypatch.setattr(hc, "_aiohttp_stream_io", fake_aiohttp_stream_io)

    chunks = []
    async for chunk in hc._astream_bytes_aiohttp(
        method="POST",
        url="http://93.184.216.34/stream",
        client=object(),
        retry=hc.RetryPolicy(attempts=2, retry_on_unsafe=True),
    ):
        chunks.append(chunk)

    assert calls["n"] == 2
    assert chunks == [b"ok"]


@requires_httpx
@pytest.mark.asyncio
async def test_stream_bytes_does_not_retry_after_first_chunk_httpx(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    calls = {"n": 0}

    @asynccontextmanager
    async def fake_httpx_stream_io(**_kwargs):
        calls["n"] += 1

        async def iter_bytes():
            yield b"first"
            raise hc.NetworkError("stream dropped")

        resp = StreamResponse("http://93.184.216.34/stream")
        yield resp, iter_bytes()

    monkeypatch.setattr(hc, "_httpx_stream_io", fake_httpx_stream_io)

    chunks = []
    with pytest.raises(hc.NetworkError) as exc:
        async for chunk in hc.astream_bytes(
            method="POST",
            url="http://93.184.216.34/stream",
            client=object(),
            retry=hc.RetryPolicy(attempts=2, retry_on_unsafe=True),
        ):
            chunks.append(chunk)

    assert calls["n"] == 1
    assert chunks == [b"first"]
    assert "stream dropped" in str(exc.value)


@requires_httpx
@pytest.mark.asyncio
async def test_stream_bytes_first_byte_timeout_httpx(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    @asynccontextmanager
    async def fake_httpx_stream_io(**_kwargs):
        async def iter_bytes():
            await asyncio.sleep(0.05)
            yield b"late"

        resp = StreamResponse("http://93.184.216.34/stream")
        yield resp, iter_bytes()

    monkeypatch.setattr(hc, "_httpx_stream_io", fake_httpx_stream_io)

    timeout = SimpleNamespace(connect=0.01, read=0.1)
    with pytest.raises(hc.NetworkError) as exc:
        async for _ in hc.astream_bytes(
            method="GET",
            url="http://93.184.216.34/stream",
            client=object(),
            timeout=timeout,
        ):
            pass
    assert "StreamTimeout:first_byte" in str(exc.value)


@requires_httpx
@pytest.mark.asyncio
async def test_stream_bytes_idle_timeout_httpx(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    @asynccontextmanager
    async def fake_httpx_stream_io(**_kwargs):
        async def iter_bytes():
            yield b"first"
            await asyncio.sleep(0.05)
            yield b"second"

        resp = StreamResponse("http://93.184.216.34/stream")
        yield resp, iter_bytes()

    monkeypatch.setattr(hc, "_httpx_stream_io", fake_httpx_stream_io)

    timeout = SimpleNamespace(connect=0.01, read=0.01)
    chunks = []
    with pytest.raises(hc.NetworkError) as exc:
        async for chunk in hc.astream_bytes(
            method="GET",
            url="http://93.184.216.34/stream",
            client=object(),
            timeout=timeout,
        ):
            chunks.append(chunk)
    assert chunks == [b"first"]
    assert "StreamTimeout:idle" in str(exc.value)


@requires_httpx
@pytest.mark.asyncio
async def test_sse_retries_on_timeout_httpx(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    calls = {"n": 0}

    @asynccontextmanager
    async def fake_httpx_stream_io(**_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            async def iter_bytes():
                await asyncio.sleep(0.05)
                yield b"data: timeout\n\n"
        else:
            async def iter_bytes():
                yield b"data: ok\n\n"

        resp = StreamResponse("http://93.184.216.34/stream")
        yield resp, iter_bytes()

    monkeypatch.setattr(hc, "_httpx_stream_io", fake_httpx_stream_io)

    timeout = SimpleNamespace(connect=0.01, read=0.01)
    events = []
    async for ev in hc.astream_sse(
        url="http://93.184.216.34/stream",
        client=object(),
        retry=hc.RetryPolicy(attempts=2),
        timeout=timeout,
    ):
        events.append(ev)
        if events:
            break
    assert calls["n"] == 2
    assert events[0].data == "ok"
