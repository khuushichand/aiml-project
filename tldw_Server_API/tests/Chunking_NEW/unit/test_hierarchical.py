"""
Unit tests for deep hierarchical chunking.
"""

import pytest

from tldw_Server_API.app.core.Chunking.Chunk_Lib import Chunker


def _collect_text(node):
    # Traverse tree to reassemble text from blocks
    if not isinstance(node, dict):
        return ""
    if node.get('kind') in ('paragraph', 'blank', 'header_line', 'hr', 'list_unordered', 'list_ordered', 'table_md', 'table_html', 'table_part_html', 'html_block'):
        return node.get('text', '')
    out = ""
    for child in node.get('children', []) or []:
        out += _collect_text(child)
    return out


@pytest.mark.unit
def test_hierarchical_sections_and_reassembly():
    text = (
        "# Title\n"
        "Intro para.\n\n"
        "## Sub 1\n"
        "Text under sub1.\n\n"
        "## Sub 2\n"
        "- item A\n"
        "- item B\n\n"
        "<h3>Sub 2.1</h3>\n"
        "Table:\n"
        "| c1 | c2 |\n"
        "|----|----|\n"
        "val1 | val2\n"
    )
    chunker = Chunker(options={'max_size': 5, 'overlap': 1, 'sentence_splitter': 'regex'})
    tree = chunker.chunk_text_hierarchical_deep(text, method='sentences')
    assert tree['type'] == 'hierarchical'
    assert 'root' in tree
    root = tree['root']
    # Expect a top-level section for Title
    children = root.get('children') or []
    sects = [n for n in children if n.get('kind') == 'section']
    assert len(sects) >= 1
    # Validate nesting: section with level 1 contains sub-sections level 2, and then level 3
    sec1 = sects[0]
    assert sec1.get('level') == 1
    sec1_kids = [n for n in sec1.get('children') or [] if n.get('kind') == 'section']
    # There should be at least one h2 section under h1
    assert any(s.get('level') == 2 for s in sec1_kids)
    # Collect text from tree must equal original text
    rebuilt = _collect_text(root)
    assert rebuilt == text
    # Check that blocks have child chunks
    para_blocks = [n for n in sec1.get('children') or [] if n.get('kind') == 'paragraph']
    if para_blocks:
        assert isinstance(para_blocks[0].get('chunks'), list)

