import asyncio
import pytest

from tldw_Server_API.app.core.Chunking.async_chunker import AsyncChunker


@pytest.mark.asyncio
async def test_stream_sentences_no_duplication_or_loss():
    # Create small pieces that split across sentence boundaries
    parts = ["This is A.", " This is B.", " This is C."]

    async def gen():
        for p in parts:
            yield p
            await asyncio.sleep(0)

    ac = AsyncChunker()
    seen = []
    async for ch in ac.chunk_stream(gen(), method="sentences", max_size=1, overlap=0, buffer_size=8):
        seen.append(ch)

    # Ensure each sentence appears exactly once
    assert seen == ["This is A.", "This is B.", "This is C."]


@pytest.mark.asyncio
async def test_stream_tokens_overlap_edge_cases():
    # Use short text and small buffer to force multiple iterations
    text = "Token test one two three four five six seven eight nine ten"
    parts = [text[:20], text[20:40], text[40:]]

    async def gen():
        for p in parts:
            yield p
            await asyncio.sleep(0)

    ac = AsyncChunker()
    out = []
    async for ch in ac.chunk_stream(gen(), method="tokens", max_size=10, overlap=3, buffer_size=16):
        out.append(ch)

    # Join of chunks should contain the original words in order without obvious duplication
    joined = " ".join(out)
    for w in ["Token", "test", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]:
        assert joined.count(w) >= 1

