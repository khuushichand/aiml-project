import os
import pytest
import uuid


@pytest.fixture
async def real_redis():
    """
    Provide a real Redis URL for integration tests, or skip when unavailable.

    Honors RG_REAL_REDIS_URL (preferred) or REDIS_URL. Verifies connectivity
    without falling back to the in-memory stub and sets REDIS_URL for the
    governor under test.
    """
    url = os.getenv("RG_REAL_REDIS_URL") or os.getenv("REDIS_URL")
    if not url:
        pytest.skip("No real Redis URL provided; set RG_REAL_REDIS_URL or REDIS_URL to run integration tests")
    try:
        from tldw_Server_API.app.core.Infrastructure.redis_factory import create_async_redis_client
        client = await create_async_redis_client(preferred_url=url, fallback_to_fake=False, context="rg_integration_test")
        # Ping succeeded; set REDIS_URL for code under test
        os.environ["REDIS_URL"] = url
    except Exception as exc:
        pytest.skip(f"Real Redis unreachable at {url}: {exc}")
    try:
        yield url
    finally:
        try:
            await client.close()
        except Exception:
            _ = None


@pytest.fixture
async def rg_unique_ns(real_redis):
    """Yield a unique Redis namespace for RG and clean it up after the test.

    Scans and deletes keys under the namespace to avoid cross-test interference.
    """
    ns = f"rg_it_{uuid.uuid4().hex[:8]}"
    # Ensure clean start (best-effort)
    try:
        from tldw_Server_API.app.core.Infrastructure.redis_factory import create_async_redis_client
        client = await create_async_redis_client(fallback_to_fake=False, context="rg_integration_ns_cleanup")
        # pre-clean any stray keys (unlikely for a fresh UUID ns)
        _cursor, keys = await client.scan(0, match=f"{ns}:*", count=1000)
        for k in keys or []:
            try:
                await client.delete(k)
            except Exception:
                _ = None
    except Exception:
        _ = None
    try:
        yield ns
    finally:
        try:
            client = await create_async_redis_client(fallback_to_fake=False, context="rg_integration_ns_cleanup")
            _cursor, keys = await client.scan(0, match=f"{ns}:*", count=1000)
            for k in keys or []:
                try:
                    await client.delete(k)
                except Exception:
                    _ = None
        except Exception:
            _ = None
