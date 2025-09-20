"""
Tests for multi-level chunking exactness, indices spanning, and metrics emission.
"""

import pytest

from tldw_Server_API.app.core.Chunking.Chunk_Lib import Chunker
from tldw_Server_API.app.core.Metrics import get_metrics_registry


def _join_text(chunks):
    # chunks are dicts with 'text'
    ordered = sorted(chunks, key=lambda c: c.get('metadata', {}).get('chunk_index', 0))
    return "".join(c.get('text', '') for c in ordered)


@pytest.mark.unit
def test_multilevel_words_reassembles_exactly():
    text = (
        "Title\n"
        "====\n"
        "# Header\n"
        "First paragraph line one.\n"
        "Continues here.\n\n"
        "- Bullet item one\n"
        "1. Ordered item one\n\n"
        "| a | b |\n"
        "|---|---|\n"
        "Second paragraph after table.\n\n"
        "~~~\ncode fence\n~~~\n"
        "Final line.\n"
    )
    chunker = Chunker(options={'method': 'words', 'max_size': 5, 'overlap': 2, 'multi_level': True})
    chunks = chunker.chunk_text(text)
    # All chunks must be dicts with metadata
    assert all(isinstance(c, dict) and 'metadata' in c for c in chunks)
    # Reassemble
    rebuilt = _join_text(chunks)
    assert rebuilt == text
    # Span indices
    total = chunks[0]['metadata']['total_chunks']
    indices = [c['metadata']['chunk_index'] for c in chunks]
    assert len(chunks) == total
    assert indices == list(range(total))
    # Paragraph offsets present
    assert all('paragraph_index' in c['metadata'] for c in chunks)
    assert all('paragraph_start_offset' in c['metadata'] for c in chunks)
    assert all('paragraph_end_offset' in c['metadata'] for c in chunks)
    # Multi-level marker
    assert all(c['metadata'].get('multi_level') is True for c in chunks)


@pytest.mark.unit
def test_multilevel_sentences_reassembles_exactly_and_metrics():
    text = (
        "Heading\n\n"
        "First sentence. Second sentence!\n\n"
        "<table>\n<tr><td>c1</td><td>c2</td></tr>\n</table>\n"
        "Another sentence?\n\n"
        "---\n"
        "List:\n"
        "* One\n"
        "+ Two\n"
        "3) Three.\n"
    )
    chunker = Chunker(options={'method': 'sentences', 'max_size': 2, 'overlap': 1, 'multi_level': True, 'sentence_splitter': 'regex'})
    chunks = chunker.chunk_text(text)
    assert all(isinstance(c, dict) and 'metadata' in c for c in chunks)
    rebuilt = _join_text(chunks)
    assert rebuilt == text
    # Indices span across all paragraphs
    total = chunks[0]['metadata']['total_chunks']
    indices = [c['metadata']['chunk_index'] for c in chunks]
    assert len(chunks) == total
    assert indices == list(range(total))
    # Multi-level marker
    assert all(c['metadata'].get('multi_level') is True for c in chunks)

    # Metrics emitted
    metrics_text = get_metrics_registry().export_prometheus_format()
    assert 'chunk_time_seconds' in metrics_text
    assert 'chunk_count' in metrics_text
