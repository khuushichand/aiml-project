import asyncio
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tldw_Server_API.app.core.Embeddings.request_batching import (
    BatchRequest,
    RequestBatcher,
)
from tldw_Server_API.app.core.Embeddings.simplified_config import (
    BatchingConfig,
    EmbeddingsConfig,
    ProviderConfig,
    SecurityConfig,
)


@pytest.mark.asyncio
async def test_batched_requests_include_provider_credentials(monkeypatch):
    config = EmbeddingsConfig(
        providers=[
            ProviderConfig(
                name="openai",
                api_key="sk-test",
                models=["text-embedding-3-small"],
            )
        ],
        batching=BatchingConfig(
            enabled=True,
            max_batch_size=4,
            batch_timeout_ms=10,
            adaptive_batching=False,
        ),
        security=SecurityConfig(enable_rate_limiting=False),
        default_provider="openai",
        default_model="text-embedding-3-small",
    )
    batcher = RequestBatcher(config=config)

    captured = {}

    async def fake_create_embeddings_batch_async(texts, user_app_config, model_id_override=None):
        captured["config"] = user_app_config
        return [[0.1] for _ in texts]

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch_async",
        fake_create_embeddings_batch_async,
        raising=True,
    )

    loop = asyncio.get_running_loop()
    future = loop.create_future()
    request = BatchRequest(
        request_id="req-1",
        text="hello",
        model="text-embedding-3-small",
        provider="openai",
        metadata={},
        future=future,
        timestamp=time.time(),
    )

    await batcher._process_batch([request], "openai", "text-embedding-3-small")

    assert future.done()
    assert future.result() == [0.1]

    user_app_config = captured["config"]
    assert user_app_config["openai_api"]["api_key"] == "sk-test"
    model_entry = user_app_config["embedding_config"]["models"]["openai:text-embedding-3-small"]
    assert model_entry["api_key"] == "sk-test"
    assert model_entry["model_name_or_path"] == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_submit_request_enforces_rate_limits(monkeypatch):
    limiter_calls = []

    class StubLimiter:
        def __init__(self):
            self.rate_limiter = SimpleNamespace(user_tiers={"user-1": "free"})

        async def check_rate_limit_async(self, user_id, cost=1, ip_address=None):
            limiter_calls.append((user_id, cost))
            return False, 7

    stub_limiter = StubLimiter()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Embeddings.request_batching.get_async_rate_limiter",
        lambda: stub_limiter,
        raising=True,
    )

    config = EmbeddingsConfig(
        providers=[
            ProviderConfig(
                name="openai",
                api_key="sk-test",
                models=["text-embedding-3-small"],
            )
        ],
        batching=BatchingConfig(
            enabled=True,
            max_batch_size=4,
            batch_timeout_ms=10,
            adaptive_batching=False,
        ),
        security=SecurityConfig(enable_rate_limiting=True),
        default_provider="openai",
        default_model="text-embedding-3-small",
    )

    batcher = RequestBatcher(config=config)
    batcher.metrics = SimpleNamespace(
        log_rate_limit_hit=Mock(),
        log_batch_size=lambda *args, **kwargs: None,
        log_error=lambda *args, **kwargs: None,
    )

    with pytest.raises(RuntimeError, match="Retry after 7s"):
        await batcher.submit_request(
            text="hello",
            model="text-embedding-3-small",
            provider="openai",
            metadata={"user_id": "user-1"},
        )

    assert limiter_calls == [("user-1", 1)]
    batcher.metrics.log_rate_limit_hit.assert_called_once_with("user-1", "free")
