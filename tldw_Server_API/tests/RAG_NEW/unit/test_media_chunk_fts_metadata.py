import sqlite3

import pytest

from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import MediaDBRetriever, RetrievalConfig
from tldw_Server_API.app.core.RAG.rag_service.types import Document


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeMediaDB:
    def __init__(self, rows):
        self._rows = rows

    def execute_query(self, sql, params):
        return _FakeCursor(self._rows)

    def lookup_section_for_offset(self, media_id, start_char):
        return {
            "title": "Intro",
            "start_char": start_char - 5,
            "end_char": start_char + 5,
        }


@pytest.mark.unit
def test_chunk_level_fts_preserves_metadata(monkeypatch):
    monkeypatch.setattr(MediaDBRetriever, "_initialize_vector_store", lambda self: None)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            'chunk-uuid' AS chunk_uuid,
            1 AS chunk_rowid,
            123 AS media_id,
            'alpha beta' AS chunk_text,
            10 AS start_char,
            20 AS end_char,
            'text' AS chunk_type,
            3 AS chunk_index,
            'Doc Title' AS title,
            'article' AS media_type,
            'https://example.com' AS url,
            0.75 AS rank
        """
    )
    row = cur.fetchone()
    conn.close()

    fake_db = _FakeMediaDB([row])
    config = RetrievalConfig(max_results=5, use_fts=True, use_vector=False)
    setattr(config, "fts_level", "chunk")

    retriever = MediaDBRetriever(db_path=None, config=config, user_id="tester", media_db=fake_db)
    docs = retriever._retrieve_chunk_fts("alpha", media_type=None)

    assert docs, "Expected chunk-level FTS to return at least one document"
    doc = docs[0]
    assert doc.metadata["media_id"] == "123"
    assert doc.metadata["chunk_index"] == 3
    assert doc.metadata["start_char"] == 10
    assert doc.metadata["end_char"] == 20
    assert doc.metadata["section_title"] == "Intro"
    assert doc.chunk_index == 3


@pytest.mark.unit
def test_document_location_string_uses_one_based_index():
    doc = Document(
        id="doc-1",
        content="",
        metadata={},
        chunk_index=1,
        total_chunks=3,
        section_title="Preface",
    )
    location = doc.get_location_string()
    assert "Chunk 1/3" in location
    assert "Section: Preface" in location
