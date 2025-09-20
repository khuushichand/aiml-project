"""
Tests for flattening hierarchical trees into flat chunks with ancestry metadata.
"""

import pytest

from tldw_Server_API.app.core.Chunking.Chunk_Lib import Chunker


@pytest.mark.unit
def test_flatten_hierarchical_with_titles_and_kinds():
    text = (
        "# Title\n"
        "Intro text.\n\n"
        "## Section A\n"
        "A1. A2.\n\n"
        "## Section B\n"
        "B1.\n"
    )
    chunker = Chunker(options={'max_size': 2, 'overlap': 0, 'sentence_splitter': 'regex'})
    tree = chunker.chunk_text_hierarchical_deep(text, method='sentences')
    flat = chunker.flatten_hierarchical(tree)
    assert isinstance(flat, list)
    assert len(flat) > 0
    # All items have ancestry_titles list and paragraph_kind
    for item in flat:
        md = item.get('metadata', {})
        assert 'ancestry_titles' in md
        assert isinstance(md['ancestry_titles'], list)
        assert 'paragraph_kind' in md
        # start/end offsets present
        # They may be absent if originated from simple nodes, so guard fallback
        # But chunk_text_hierarchical_deep sets start/end for chunk metadata
        assert 'start_offset' in md and 'end_offset' in md

    # Ensure titles included for sections
    any_has_title = any('Title' in (t for t in item['metadata']['ancestry_titles']) for item in flat)
    assert any_has_title

