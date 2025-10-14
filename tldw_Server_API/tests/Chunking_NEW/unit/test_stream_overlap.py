import asyncio
import pytest

from tldw_Server_API.app.core.Chunking.async_chunker import AsyncChunker


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_chunk_stream_words_overlap_is_word_safe():
    text = "one two three four five six seven eight nine ten"

    async def gen():
        # Emit in two pieces to force streaming boundary
        yield text[:25]
        await asyncio.sleep(0)
        yield text[25:]

    async with AsyncChunker() as ch:
        chunks = []
        async for c in ch.chunk_stream(gen(), method="words", max_size=3, overlap=1, buffer_size=16):
            chunks.append(c)

    # Basic sanity: chunks produced and each at most 3 words
    assert chunks, "no chunks produced"
    for c in chunks:
        assert len(c.split()) <= 3

    # Adjacent chunks should overlap by 1 word when full-length
    for a, b in zip(chunks, chunks[1:]):
        wa, wb = a.split(), b.split()
        if len(wa) == 3 and len(wb) >= 1:
            assert wa[-1] == wb[0]

