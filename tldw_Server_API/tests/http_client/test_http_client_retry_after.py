import pytest
import time


pytestmark = pytest.mark.unit


def _has_httpx():
    try:
        import httpx  # noqa: F401
        return True
    except Exception:
        return False


requires_httpx = pytest.mark.skipif(not _has_httpx(), reason="httpx not installed")


@requires_httpx
@pytest.mark.asyncio
async def test_retry_after_header_is_honored(monkeypatch):
    import httpx
    from tldw_Server_API.app.core.http_client import afetch_json, create_async_client, RetryPolicy

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            # Instruct client to delay via Retry-After
            return httpx.Response(429, request=request, text="rate limit", headers={"Retry-After": "0.05", "Content-Type": "application/json"})
        return httpx.Response(200, request=request, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = create_async_client(transport=transport)
    try:
        t0 = time.time()
        policy = RetryPolicy(attempts=2)
        data = await afetch_json(method="GET", url="http://93.184.216.34/retry-after", client=client, retry=policy, require_json_ct=False)
        elapsed = time.time() - t0
        assert data == {"ok": True}
        assert calls["n"] == 2
        assert elapsed >= 0.04  # rough guard that delay happened
    finally:
        await client.aclose()
