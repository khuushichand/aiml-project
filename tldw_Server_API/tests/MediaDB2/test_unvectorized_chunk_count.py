from __future__ import annotations

import pytest


pytestmark = pytest.mark.unit


def test_get_unvectorized_chunk_count_invalid_media_id_returns_none(memory_db_factory) -> None:
    db = memory_db_factory("chunk_count_invalid")
    assert db.get_unvectorized_chunk_count("not-an-int") is None


def test_get_unvectorized_chunk_count_returns_zero_for_media_without_chunks(memory_db_factory) -> None:
    db = memory_db_factory("chunk_count_zero")
    media_id, _uuid, _msg = db.add_media_with_keywords(
        url="https://example.com/no-chunks",
        title="No chunks",
        media_type="document",
        content="plain text",
        chunks=None,
    )
    assert media_id is not None
    assert db.get_unvectorized_chunk_count(media_id) == 0


def test_get_unvectorized_chunk_count_returns_active_chunk_rows(memory_db_factory) -> None:
    db = memory_db_factory("chunk_count_positive")
    chunks = [
        {"text": "chunk one", "start_char": 0, "end_char": 9, "chunk_type": "text"},
        {"text": "chunk two", "start_char": 10, "end_char": 19, "chunk_type": "text"},
    ]
    media_id, _uuid, _msg = db.add_media_with_keywords(
        url="https://example.com/chunks",
        title="Has chunks",
        media_type="document",
        content="chunk one chunk two",
        overwrite=True,
        chunks=chunks,
    )
    assert media_id is not None
    assert db.get_unvectorized_chunk_count(media_id) == 2
