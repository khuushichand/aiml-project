import os
import pytest
from hypothesis import given, strategies as st, settings as hyp_settings

from tldw_Server_API.app.core.Chunking.chunker import Chunker
from tldw_Server_API.app.core.Chunking.base import ChunkerConfig, ChunkingMethod


@pytest.fixture(autouse=True)
def testing_env():
    os.environ['TESTING'] = 'true'
    yield
    os.environ.pop('TESTING', None)


def words_to_text(words):
    return ' '.join(words)


@hyp_settings(deadline=None)
@given(
    total_words=st.integers(min_value=10, max_value=200),
    max_size=st.integers(min_value=3, max_value=40),
    overlap=st.integers(min_value=0, max_value=10)
)
def test_words_overlap_property(total_words, max_size, overlap):
    # Constrain overlap < max_size
    if overlap >= max_size:
        overlap = max_size - 1
        if overlap < 0:
            overlap = 0

    # Build a simple word list w0 w1 ...
    words = [f"w{i}" for i in range(total_words)]
    text = words_to_text(words)

    cfg = ChunkerConfig(default_method=ChunkingMethod.WORDS, default_max_size=max_size, default_overlap=overlap, language='en')
    ck = Chunker(config=cfg)
    chunks = ck.chunk_text(text, method=ChunkingMethod.WORDS.value, max_size=max_size, overlap=overlap)

    if len(chunks) <= 1 or overlap == 0:
        # Nothing to assert about overlap
        return

    # Check that last <overlap> words of chunk i equals first <overlap> of chunk i+1
    for i in range(len(chunks)-1):
        a = chunks[i].split()
        b = chunks[i+1].split()
        if len(a) >= overlap and len(b) >= overlap:
            assert a[-overlap:] == b[:overlap]
