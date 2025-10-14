import pytest


@pytest.mark.asyncio
async def test_async_chunker_forwards_kwargs(monkeypatch):
    from tldw_Server_API.app.core.Chunking.async_chunker import AsyncChunker

    calls = {}

    def fake_chunk_text(text, method, max_size, overlap, **options):
        calls['args'] = (text, method, max_size, overlap)
        calls['options'] = options
        return ["ok"]

    ch = AsyncChunker()
    # Patch the underlying chunker method on this instance
    monkeypatch.setattr(ch._chunker, 'chunk_text', fake_chunk_text)

    res = await ch.chunk_text(
        "Hello world",
        method='words',
        max_size=3,
        overlap=1,
        preserve_sentences=True,
        min_chunk_size=2,
    )

    assert res == ["ok"]
    assert calls.get('args') == ("Hello world", 'words', 3, 1)
    # Ensure kwargs were forwarded, not passed positionally
    assert calls.get('options', {}).get('preserve_sentences') is True
    assert calls.get('options', {}).get('min_chunk_size') == 2

