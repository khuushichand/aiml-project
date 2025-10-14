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

