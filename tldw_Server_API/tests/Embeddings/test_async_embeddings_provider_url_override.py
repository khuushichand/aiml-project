import pytest

from tldw_Server_API.app.core.Embeddings.async_embeddings import AsyncEmbeddingService
from tldw_Server_API.app.core.Embeddings.connection_pool import get_pool_manager
from tldw_Server_API.app.core.Embeddings.simplified_config import (
    BatchingConfig,
    EmbeddingsConfig,
    ProviderConfig,
    SecurityConfig,
)


class DummyCache:
    async def get_async(self, key):  # noqa: ANN001 - simple test stub
        return None

    async def set_async(self, key, value, ttl=None):  # noqa: ANN001 - simple test stub
        return True


class TrackingCache:
    def __init__(self) -> None:
        self.get_keys = []
        self.set_keys = []

    async def get_async(self, key):  # noqa: ANN001 - simple test stub
        self.get_keys.append(key)
        return None

    async def set_async(self, key, value, ttl=None):  # noqa: ANN001 - simple test stub
        self.set_keys.append(key)
        return True


@pytest.mark.asyncio
async def test_openai_api_url_override_only_when_explicit_provider(monkeypatch):
    config = EmbeddingsConfig(
        providers=[
            ProviderConfig(
                name="openai",
                api_key="sk-test",
                api_url="https://example.test/v1",
            )
        ],
        batching=BatchingConfig(enabled=True),
        security=SecurityConfig(enable_rate_limiting=False),
        default_provider="openai",
        default_model="text-embedding-3-small",
    )

    service = AsyncEmbeddingService(config=config)
    service.cache = DummyCache()
    service.batcher.enabled = False
    service.batcher.enabled = True

    # Ensure batching is bypassed when explicit provider + api_url override is used.
    async def _fail_submit(*_args, **_kwargs):  # noqa: ANN001 - test stub
        raise AssertionError("batching should be bypassed for explicit provider overrides")

    monkeypatch.setattr(service.batcher, "submit_request", _fail_submit)

    pool = get_pool_manager().get_pool("openai")
    urls = []

    async def _fake_request(*_args, **kwargs):  # noqa: ANN001 - test stub
        urls.append(kwargs.get("url"))
        return {"data": [{"embedding": [0.1, 0.2]}]}

    monkeypatch.setattr(pool, "request", _fake_request)

    result = await service.create_embedding(
        text="hello",
        model="text-embedding-3-small",
        provider="openai",
        use_cache=False,
        use_batching=True,
    )

    assert result == [0.1, 0.2]
    assert urls[-1] == "https://example.test/v1/embeddings"


@pytest.mark.asyncio
async def test_openai_api_url_used_for_default_provider(monkeypatch):
    config = EmbeddingsConfig(
        providers=[
            ProviderConfig(
                name="openai",
                api_key="sk-test",
                api_url="https://example.test/v1",
            )
        ],
        batching=BatchingConfig(enabled=False),
        security=SecurityConfig(enable_rate_limiting=False),
        default_provider="openai",
        default_model="text-embedding-3-small",
    )

    service = AsyncEmbeddingService(config=config)
    service.cache = DummyCache()

    pool = get_pool_manager().get_pool("openai")
    urls = []

    async def _fake_request(*_args, **kwargs):  # noqa: ANN001 - test stub
        urls.append(kwargs.get("url"))
        return {"data": [{"embedding": [0.1, 0.2]}]}

    monkeypatch.setattr(pool, "request", _fake_request)

    result = await service.create_embedding(
        text="hello",
        model="text-embedding-3-small",
        provider=None,
        use_cache=False,
        use_batching=False,
    )

    assert result == [0.1, 0.2]
    assert urls[-1] == "https://example.test/v1/embeddings"


@pytest.mark.asyncio
async def test_cache_key_includes_openai_api_url_override(monkeypatch):
    config = EmbeddingsConfig(
        providers=[
            ProviderConfig(
                name="openai",
                api_key="sk-test",
                api_url="https://example.test/v1",
            )
        ],
        batching=BatchingConfig(enabled=False),
        security=SecurityConfig(enable_rate_limiting=False),
        default_provider="openai",
        default_model="text-embedding-3-small",
    )

    service = AsyncEmbeddingService(config=config)
    service.cache = TrackingCache()

    pool = get_pool_manager().get_pool("openai")

    async def _fake_request(*_args, **kwargs):  # noqa: ANN001 - test stub
        return {"data": [{"embedding": [0.1, 0.2]}]}

    monkeypatch.setattr(pool, "request", _fake_request)

    text = "hello"
    result = await service.create_embedding(
        text=text,
        model="text-embedding-3-small",
        provider="openai",
        use_cache=True,
        use_batching=False,
    )

    assert result == [0.1, 0.2]

    import hashlib

    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    expected_key = f"openai:text-embedding-3-small:{text_hash}:https://example.test/v1"
    assert service.cache.get_keys[-1] == expected_key
    assert service.cache.set_keys[-1] == expected_key
