import pytest

from tldw_Server_API.app.core.Chunking.chunker import Chunker


@pytest.mark.unit
def test_structure_aware_section_level_grouping_elements_per_chunk():
    text = (
        "# H1\n"
        "Para 1 line.\n\n"
        "Para 2 line.\n\n"
        "Para 3 line.\n\n"
        "# H2\n"
        "Para 4 line.\n\n"
        "Para 5 line.\n"
    )

    ck = Chunker()

    tree = ck.chunk_text_hierarchical_tree(
        text=text,
        method="structure_aware",
        max_size=2,  # elements per chunk
        overlap=1,
        language="en",
    )

    flat = ck.flatten_hierarchical(tree)

    # Expect 2 windows for H1 (3 elements -> [1,2], [2,3]) and 1 window for H2 (2 elements -> [4,5])
    assert len(flat) == 3

    # Validate section paths and grouped elements
    assert flat[0]["metadata"].get("section_path") == "H1"
    assert flat[1]["metadata"].get("section_path") == "H1"
    assert flat[2]["metadata"].get("section_path") == "H2"

    assert flat[0]["metadata"].get("grouped_elements") == 2
    assert flat[1]["metadata"].get("grouped_elements") == 2
    assert flat[2]["metadata"].get("grouped_elements") == 2

    # Basic text content sanity: windows contain expected paragraph snippets
    assert "Para 1" in flat[0]["text"] and "Para 2" in flat[0]["text"]
    assert "Para 2" in flat[1]["text"] and "Para 3" in flat[1]["text"]
    assert "Para 4" in flat[2]["text"] and "Para 5" in flat[2]["text"]
    # Ensure regrouped text preserves spacing between elements
    assert "Para 1 line.Para 2 line." not in flat[0]["text"]
    assert "Para 2 line.Para 3 line." not in flat[1]["text"]
    assert "Para 4 line.Para 5 line." not in flat[2]["text"]


@pytest.mark.unit
def test_structure_aware_single_element_section():
    text = (
        "# Intro\n"
        "Only one paragraph here.\n"
    )

    ck = Chunker()
    tree = ck.chunk_text_hierarchical_tree(
        text=text,
        method="structure_aware",
        max_size=3,
        overlap=1,
        language="en",
    )
    flat = ck.flatten_hierarchical(tree)

    # Expect a single chunk with one grouped element
    assert len(flat) == 1
    assert flat[0]["metadata"].get("section_path") == "Intro"
    assert flat[0]["metadata"].get("grouped_elements") == 1
    assert "Only one paragraph" in flat[0]["text"]


@pytest.mark.unit
def test_structure_aware_overlap_ge_maxsize_clamped_behavior():
    # 5 elements under one section, max_size=2, overlap=5 (>= max_size)
    # Should behave like overlap = max_size - 1 => step = 1: 4 windows
    text = (
        "# Sec\n"
        "A1.\n\n"
        "A2.\n\n"
        "A3.\n\n"
        "A4.\n\n"
        "A5.\n\n"
    )

    ck = Chunker()
    tree = ck.chunk_text_hierarchical_tree(
        text=text,
        method="structure_aware",
        max_size=2,
        overlap=5,  # pathological, should clamp effectively
        language="en",
    )
    flat = ck.flatten_hierarchical(tree)

    assert len(flat) == 4  # [A1,A2], [A2,A3], [A3,A4], [A4,A5]
    for item in flat:
        assert item["metadata"].get("grouped_elements") == 2
        assert item["metadata"].get("section_path") == "Sec"


@pytest.mark.unit
def test_structure_aware_nested_headers_preserve_section_path():
    text = (
        "# H1\n"
        "Top level paragraph.\n\n"
        "## H1.1\n"
        "Nested paragraph.\n"
    )

    ck = Chunker()
    tree = ck.chunk_text_hierarchical_tree(
        text=text,
        method="structure_aware",
        max_size=3,
        overlap=0,
        language="en",
    )
    flat = ck.flatten_hierarchical(tree)

    nested_paths = [
        item["metadata"].get("section_path")
        for item in flat
        if item["metadata"].get("section_path")
    ]

    assert "H1 > H1.1" in nested_paths


@pytest.mark.unit
def test_structure_aware_header_paragraph_spacing():
    text = (
        "# Heading\n"
        "Paragraph text follows.\n"
    )

    ck = Chunker()
    flat = ck.chunk_text_hierarchical_flat(
        text=text,
        method="structure_aware",
        max_size=4,
        overlap=0,
        language="en",
    )

    assert len(flat) == 1
    content = flat[0]["text"]
    assert "# Heading" in content
    assert "Paragraph text follows." in content
    # There should be visible separation between heading and paragraph text
    assert "HeadingParagraph" not in content.replace("\n", "")
