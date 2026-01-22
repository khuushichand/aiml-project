import hashlib

import pytest

from tldw_Server_API.app.core.Embeddings.async_embeddings import AsyncEmbeddingService
from tldw_Server_API.app.core.Embeddings.simplified_config import (
    BatchingConfig,
    EmbeddingsConfig,
    ProviderConfig,
    SecurityConfig,
)


class DummyCache:
    def __init__(self) -> None:
        self.set_calls = []
        self.get_calls = []

    async def get_async(self, key: str):
        self.get_calls.append(key)
        return None

    async def set_async(self, key: str, value, ttl=None):
        self.set_calls.append((key, value, ttl))
        return True


class FailingProvider:
    async def create_embedding(self, text, model=None, user_id=None):
        raise RuntimeError("primary provider failure")


class SuccessProvider:
    async def create_embedding(self, text, model=None, user_id=None):
        return [0.1, 0.2]


@pytest.mark.asyncio
async def test_cache_key_uses_fallback_provider_model():
    config = EmbeddingsConfig(
        providers=[
            ProviderConfig(
                name="openai",
                api_key="sk-test",
                models=["openai-model"],
                fallback_provider="huggingface",
            ),
            ProviderConfig(
                name="huggingface",
                models=["hf-model"],
                fallback_model="hf-model",
            ),
        ],
        batching=BatchingConfig(enabled=False),
        security=SecurityConfig(enable_rate_limiting=False),
        default_provider="openai",
        default_model="openai-model",
    )

    service = AsyncEmbeddingService(config=config)
    service.providers = {
        "openai": FailingProvider(),
        "huggingface": SuccessProvider(),
    }
    service.cache = DummyCache()
    service.batcher.enabled = False

    text = "hello cache"
    result = await service.create_embedding(
        text=text,
        model="openai-model",
        provider="openai",
        use_batching=False,
    )

    assert result == [0.1, 0.2]

    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    expected_key = f"huggingface:hf-model:{text_hash}"
    assert service.cache.set_calls == [(expected_key, [0.1, 0.2], None)]
