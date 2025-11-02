import pytest

from tldw_Server_API.app.core.Chunking.async_chunker import AsyncChunker


@pytest.mark.asyncio
async def test_async_template_returns_dict_chunks():
    chunker = AsyncChunker()
    try:
        chunks = await chunker.process_with_template(
            text="Hello world. This is a test.",
            template_name="academic_paper",
        )
        assert isinstance(chunks, list)
        # We expect list of dicts with 'text' and 'metadata'
        assert len(chunks) >= 1
        assert isinstance(chunks[0], dict)
        assert 'text' in chunks[0]
    finally:
        await chunker.close()
