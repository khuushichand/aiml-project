import asyncio

import pytest

from tldw_Server_API.app.core.Embeddings import async_embeddings


@pytest.mark.unit
def test_cancelled_error_not_classified_as_noncritical():
    # Expected behavior: task cancellation should not be swallowed by generic
    # "noncritical" exception handling in periodic health checks.
    assert asyncio.CancelledError not in async_embeddings._ASYNC_EMBEDDINGS_NONCRITICAL_EXCEPTIONS


@pytest.mark.asyncio
async def test_periodic_health_check_propagates_cancellation(monkeypatch):
    class _DummyService:
        async def get_provider_status(self):
            return {}

    monkeypatch.setattr(
        async_embeddings,
        "get_async_embedding_service",
        lambda: _DummyService(),
    )

    task = asyncio.create_task(async_embeddings.periodic_health_check())
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
