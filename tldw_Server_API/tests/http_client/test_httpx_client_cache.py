import pytest


pytestmark = pytest.mark.unit


def _has_httpx():
    try:
        import httpx  # noqa: F401
        return True
    except Exception:
        return False


requires_httpx = pytest.mark.skipif(not _has_httpx(), reason="httpx not installed")


class DummyClient:
    def __init__(self) -> None:
        self.is_closed = False

    def close(self) -> None:
        self.is_closed = True


class DummyAsyncClient:
    def __init__(self) -> None:
        self.is_closed = False

    async def aclose(self) -> None:
        self.is_closed = True


@requires_httpx
def test_httpx_sync_client_cache_reuse(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    created = []

    def fake_create_client(*_args, **_kwargs):
        client = DummyClient()
        created.append(client)
        return client

    monkeypatch.setattr(hc, "create_client", fake_create_client)

    with hc._HTTPX_CLIENT_LOCK:
        hc._HTTPX_CLIENT_CACHE.clear()

    try:
        first = hc._get_httpx_client()
        second = hc._get_httpx_client()
        assert first is second
        assert len(created) == 1

        first.is_closed = True
        third = hc._get_httpx_client()
        assert third is not first
        assert len(created) == 2
    finally:
        with hc._HTTPX_CLIENT_LOCK:
            hc._HTTPX_CLIENT_CACHE.clear()


@requires_httpx
@pytest.mark.asyncio
async def test_httpx_async_client_cache_reuse(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc

    created = []

    def fake_create_async_client(*_args, **_kwargs):
        client = DummyAsyncClient()
        created.append(client)
        return client

    monkeypatch.setattr(hc, "create_async_client", fake_create_async_client)

    with hc._HTTPX_CLIENT_LOCK:
        hc._HTTPX_ASYNC_CLIENT_CACHE.clear()

    try:
        first = hc._get_httpx_async_client()
        second = hc._get_httpx_async_client()
        assert first is second
        assert len(created) == 1

        first.is_closed = True
        third = hc._get_httpx_async_client()
        assert third is not first
        assert len(created) == 2
    finally:
        with hc._HTTPX_CLIENT_LOCK:
            hc._HTTPX_ASYNC_CLIENT_CACHE.clear()
