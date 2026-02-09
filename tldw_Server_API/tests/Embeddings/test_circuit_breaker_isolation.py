import aiohttp
import pytest

from tldw_Server_API.app.core.Embeddings.connection_pool import ConnectionPool


@pytest.mark.asyncio
async def test_circuit_breaker_isolation_per_provider(monkeypatch):
    pool_a = ConnectionPool(provider="openai")
    pool_b = ConnectionPool(provider="huggingface")

    async def _fail_request(*args, **kwargs):
        raise aiohttp.ClientError("boom")

    async def _ok_request(*args, **kwargs):
        return {"ok": True}

    monkeypatch.setattr(pool_a, "_request_impl", _fail_request)
    monkeypatch.setattr(pool_b, "_request_impl", _ok_request)

    for _ in range(pool_a._breaker.config.failure_threshold):
        with pytest.raises(aiohttp.ClientError):
            await pool_a.request("GET", "http://example.com")

    assert pool_a._breaker.is_open
    assert pool_b._breaker.is_closed
