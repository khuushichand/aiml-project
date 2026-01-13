import pytest

from tldw_Server_API.app.core.Embeddings.chunk_metadata_backfill import normalize_chunk_metadata


@pytest.mark.unit
def test_normalize_chunk_type_from_alias():
    updated, changed = normalize_chunk_metadata({"chunk_type": "header"})
    assert changed is True
    assert updated["chunk_type"] == "heading"


@pytest.mark.unit
def test_normalize_chunk_type_from_paragraph_kind():
    updated, changed = normalize_chunk_metadata({"paragraph_kind": "code_fence"})
    assert changed is True
    assert updated["chunk_type"] == "code"


@pytest.mark.unit
def test_fill_offsets_from_indices():
    updated, changed = normalize_chunk_metadata({"start_index": "10", "end_offset": 42})
    assert changed is True
    assert updated["start_char"] == 10
    assert updated["end_char"] == 42


@pytest.mark.unit
def test_skip_default_chunk_type_when_disabled():
    updated, changed = normalize_chunk_metadata({"foo": "bar"}, default_chunk_type=None)
    assert changed is False
    assert "chunk_type" not in updated


@pytest.mark.unit
def test_default_chunk_type_when_requested():
    updated, changed = normalize_chunk_metadata({}, default_chunk_type="text")
    assert changed is True
    assert updated["chunk_type"] == "text"
