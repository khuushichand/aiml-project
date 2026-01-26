import asyncio


def test_get_batcher_is_loop_scoped():
    from tldw_Server_API.app.core.Embeddings.request_batching import get_batcher

    async def _get():
        return get_batcher()

    batcher_one = asyncio.run(_get())
    batcher_two = asyncio.run(_get())

    assert batcher_one is not batcher_two


def test_get_async_embedding_service_is_loop_scoped():
    from tldw_Server_API.app.core.Embeddings.async_embeddings import get_async_embedding_service

    async def _get():
        return get_async_embedding_service()

    service_one = asyncio.run(_get())
    service_two = asyncio.run(_get())

    assert service_one is not service_two
