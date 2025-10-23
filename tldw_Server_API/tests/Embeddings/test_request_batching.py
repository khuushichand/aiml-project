import asyncio
import time
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

from tldw_Server_API.app.core.Embeddings.request_batching import (
    BatchRequest,
    RequestBatcher,
    create_embeddings_batch_async,
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

    await batcher.shutdown()


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

    await batcher.shutdown()


@pytest.mark.asyncio
async def test_submit_request_respects_rate_limit_when_batching_disabled(monkeypatch):
    calls = []

    class StubLimiter:
        def __init__(self):
            self.rate_limiter = SimpleNamespace(user_tiers={"user-1": "free"})

        async def check_rate_limit_async(self, user_id, cost=1, ip_address=None):
            calls.append(user_id)
            if len(calls) == 1:
                return True, None
            return False, 42

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Embeddings.request_batching.get_async_rate_limiter",
        lambda: StubLimiter(),
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
    batcher.enabled = False
    batcher.metrics = SimpleNamespace(
        log_rate_limit_hit=Mock(),
    )

    async def fake_process_single(self, text, model, provider, metadata=None):
        return [0.5]

    batcher._process_single = MethodType(fake_process_single, batcher)

    result = await batcher.submit_request(
        text="hello",
        model="text-embedding-3-small",
        provider="openai",
        metadata={"user_id": "user-1"},
    )
    assert result == [0.5]

    with pytest.raises(RuntimeError, match="Retry after 42s"):
        await batcher.submit_request(
            text="world",
            model="text-embedding-3-small",
            provider="openai",
            metadata={"user_id": "user-1"},
        )

    assert calls == ["user-1", "user-1"]
    batcher.metrics.log_rate_limit_hit.assert_called_once_with("user-1", "free")

    await batcher.shutdown()


@pytest.mark.asyncio
async def test_global_batch_helper_passes_metadata(monkeypatch):
    captured = {}

    class StubBatcher:
        enabled = True

        async def submit_request(self, text, model, provider, metadata=None):
            captured["metadata"] = metadata
            return [0.42]

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Embeddings.request_batching.get_batcher",
        lambda: StubBatcher(),
        raising=True,
    )

    result = await create_embeddings_batch_async(
        texts=["hello"],
        config={},
        model_id_override="openai:text-embedding-3-small",
        metadata={"user_id": "user-xyz"},
    )

    assert result == [[0.42]]
    assert captured["metadata"] == {"user_id": "user-xyz"}


@pytest.mark.asyncio
async def test_shutdown_cancels_processing_tasks(monkeypatch):
    async def fake_create_embeddings_batch_async(texts, user_app_config, model_id_override=None):
        await asyncio.sleep(0)
        return [[0.1] for _ in texts]

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch_async",
        fake_create_embeddings_batch_async,
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
        security=SecurityConfig(enable_rate_limiting=False),
        default_provider="openai",
        default_model="text-embedding-3-small",
    )

    batcher = RequestBatcher(config=config)

    result = await batcher.submit_request(
        text="hello",
        model="text-embedding-3-small",
        provider="openai",
    )
    assert result == [0.1]

    await asyncio.wait_for(batcher.shutdown(), timeout=1.0)
    assert all(task.cancelled() or task.done() for task in batcher.processing_tasks.values())


def test_build_user_app_config_normalizes_local_provider():
    config = EmbeddingsConfig(
        providers=[
            ProviderConfig(
                name="local",
                api_key="dummy",
                api_url="http://localhost:8080/v1/embeddings",
                models=["mini"],
            )
        ],
        batching=BatchingConfig(
            enabled=True,
            adaptive_batching=False,
            max_batch_size=2,
            batch_timeout_ms=10,
        ),
        security=SecurityConfig(enable_rate_limiting=False),
        default_provider="local",
        default_model="mini",
    )

    batcher = RequestBatcher(config=config)
    app_config = batcher._build_user_app_config("local", "mini")

    model_entry = app_config["embedding_config"]["models"]["local:mini"]
    assert model_entry["provider"] == "local_api"
    assert app_config["local_api"]["api_url"] == "http://localhost:8080/v1/embeddings"
