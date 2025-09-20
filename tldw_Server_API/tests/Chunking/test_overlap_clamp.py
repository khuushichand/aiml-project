import os
import pytest

from tldw_Server_API.app.core.Chunking import Chunker


# Keep regex operations snappy and deterministic in tests
os.environ.setdefault("CHUNKING_REGEX_TIMEOUT", "0.5")
os.environ.setdefault("CHUNKING_DISABLE_MP", "1")
os.environ.setdefault("CHUNKING_REGEX_SIMPLE_ONLY", "1")


@pytest.mark.unit
@pytest.mark.timeout(5)
def test_ebook_chapters_overlap_ge_maxsize_does_not_hang():
    """Ensure ebook_chapters chunking makes forward progress when overlap >= max_size.

    This guards against infinite/negative-step loops and verifies that we return chunks.
    """
    chunker = Chunker()
    text = " ".join(["word"] * 1000)  # No chapter markers; triggers size-based split

    # overlap greater than max_size previously caused non-progressing loop
    chunks = chunker.chunk_text(text, method="ebook_chapters", max_size=50, overlap=200)

    assert isinstance(chunks, list)
    assert len(chunks) > 0
    # Ensure chunks are not degenerate
    assert all(isinstance(c, str) and c for c in chunks)


@pytest.mark.unit
@pytest.mark.timeout(5)
def test_ebook_chapters_with_metadata_overlap_ge_maxsize_does_not_hang():
    """Same safety check for the with_metadata path."""
    chunker = Chunker()
    text = " ".join(["word"] * 1000)

    results = chunker.chunk_text_with_metadata(text, method="ebook_chapters", max_size=50, overlap=200)

    assert isinstance(results, list)
    assert len(results) > 0
    # Basic shape check
    first = results[0]
    assert hasattr(first, "text") and isinstance(first.text, str)
    assert hasattr(first, "metadata") and hasattr(first.metadata, "word_count")

