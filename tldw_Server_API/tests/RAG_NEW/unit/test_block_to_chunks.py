import pytest

from tldw_Server_API.app.core.RAG.block_to_chunks import block_to_chunks


@pytest.mark.unit
def test_block_to_chunks_maps_code_and_timestamps():
    blocks = [
        {
            "type": "CODE",
            "text": "print('hi')",
            "codeMetadata": {"language": "python"},
            "citationMetadata": {"start_timestamp": 1.5, "end_timestamp": 2},
        }
    ]

    chunks = block_to_chunks(blocks)
    assert len(chunks) == 1
    metadata = chunks[0]["metadata"]
    assert metadata["chunk_type"] == "code"
    assert metadata["code_language"] == "python"
    citation = metadata["citation"]
    assert citation["start_timestamp_ms"] == 1500
    assert citation["end_timestamp_ms"] == 2000


@pytest.mark.unit
def test_block_to_chunks_maps_table_cell_and_bbox():
    blocks = [
        {
            "blockType": "TABLE_CELL",
            "text": "A1",
            "tableMetadata": {"row": 2, "col": 3},
            "citation": {"bbox": [0.0, 1.0, 2.0, 3.0]},
        }
    ]

    chunks = block_to_chunks(blocks)
    assert len(chunks) == 1
    metadata = chunks[0]["metadata"]
    assert metadata["chunk_type"] == "table"
    assert metadata["table_row"] == 2
    assert metadata["table_col"] == 3
    bbox = metadata["citation"]["bbox_quad"]
    assert len(bbox) == 4
    assert bbox[0]["x"] == 0.0
    assert bbox[0]["y"] == 1.0
    assert bbox[2]["x"] == 2.0
    assert bbox[2]["y"] == 3.0


@pytest.mark.unit
def test_block_to_chunks_maps_list_style_and_heading():
    blocks = [
        {"type": "BULLET_LIST", "text": "- item", "listMetadata": {"list_style": "bullet"}},
        {"type": "HEADING", "text": "Section Title"},
    ]

    chunks = block_to_chunks(blocks)
    assert len(chunks) == 2
    assert chunks[0]["metadata"]["chunk_type"] == "list"
    assert chunks[0]["metadata"]["list_style"] == "bullet"
    assert chunks[1]["metadata"]["chunk_type"] == "heading"
