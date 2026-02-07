import pytest

from tldw_Server_API.app.core.Embeddings import connection_pool as connection_pool_module
from tldw_Server_API.app.core.Embeddings.async_embeddings import AsyncEmbeddingService
from tldw_Server_API.app.core.Embeddings.simplified_config import (
    BatchingConfig,
    EmbeddingsConfig,
    ProviderConfig,
    SecurityConfig,
)


@pytest.mark.unit
def test_async_embedding_service_initializes_provider_pool_config(monkeypatch):
    # Ensure we don't inherit pooled state from prior tests/processes.
    monkeypatch.setattr(connection_pool_module, "_pool_manager", None, raising=False)

    config = EmbeddingsConfig(
        providers=[
            ProviderConfig(
                name="openai",
                enabled=True,
                api_key="sk-test",
                max_connections=7,
                timeout_seconds=11,
            )
        ],
        batching=BatchingConfig(enabled=False),
        security=SecurityConfig(enable_rate_limiting=False),
        default_provider="openai",
        default_model="text-embedding-3-small",
    )

    service = AsyncEmbeddingService(config=config)

    # Expected behavior: service exposes a pool manager and initializes provider pool.
    assert hasattr(service, "pool_manager")
    assert "openai" in service.pool_manager.pools
    pool = service.pool_manager.pools["openai"]
    assert pool.max_connections == 7
    assert pool.timeout_seconds == 11
