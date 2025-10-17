import os
import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import MediaDBRetriever, RetrievalConfig


def build_content_and_chunks():
    # Minimal two-section document with one paragraph each
    content = (
        "# Introduction\n"
        "Intro para one.\n\n"
        "# Methods\n"
        "Methods para one.\n"
    )
    # Compute paragraph spans
    p1 = "Intro para one."
    p2 = "Methods para one."
    s1 = content.index(p1)
    e1 = s1 + len(p1)
    s2 = content.index(p2)
    e2 = s2 + len(p2)
    chunks = [
        {
            "text": content[s1:e1],
            "start_char": s1,
            "end_char": e1,
            "chunk_type": "text",
            "metadata": {"section_path": ["Introduction"]},
        },
        {
            "text": content[s2:e2],
            "start_char": s2,
            "end_char": e2,
            "chunk_type": "text",
            "metadata": {"section_path": ["Methods"]},
        },
    ]
    return content, chunks, (s1, e1), (s2, e2)


def test_structure_index_write_and_lookup(monkeypatch):
    # Enable structure index population
    monkeypatch.setenv("RAG_ENABLE_STRUCTURE_INDEX", "1")
    db = MediaDatabase(db_path=":memory:", client_id="test")

    content, chunks, p1, p2 = build_content_and_chunks()
    mid, muuid, msg = db.add_media_with_keywords(
        url="local://test-structure",
        title="Struct Doc",
        media_type="web_document",
        content=content,
        keywords=["test"],
        prompt=None,
        analysis_content=None,
        safe_metadata=None,
        transcription_model=None,
        author="unit",
        ingestion_date=None,
        overwrite=False,
        chunk_options=None,
        chunks=chunks,
    )
    assert mid is not None

    # Ensure sections present
    rows = db.execute_query(
        "SELECT COUNT(*) AS c FROM DocumentStructureIndex WHERE media_id = ? AND kind IN ('section','header')",
        (mid,),
    ).fetchone()
    assert (rows["c"] if rows else 0) >= 2

    # Ensure paragraphs present
    rows = db.execute_query(
        "SELECT COUNT(*) AS c FROM DocumentStructureIndex WHERE media_id = ? AND kind = 'paragraph'",
        (mid,),
    ).fetchone()
    assert (rows["c"] if rows else 0) >= 2

    # Lookup section by offset for first paragraph
    sec = db.lookup_section_for_offset(mid, p1[0])
    assert sec and isinstance(sec, dict) and "title" in sec and sec["title"].lower().startswith("intro")


@pytest.mark.asyncio
async def test_chunk_retrieval_enriches_section_metadata(monkeypatch):
    monkeypatch.setenv("RAG_ENABLE_STRUCTURE_INDEX", "1")
    db = MediaDatabase(db_path=":memory:", client_id="test")
    content, chunks, p1, p2 = build_content_and_chunks()
    mid, muuid, msg = db.add_media_with_keywords(
        url="local://test-retrieval",
        title="Struct Doc 2",
        media_type="web_document",
        content=content,
        keywords=["test"],
        prompt=None,
        analysis_content=None,
        safe_metadata=None,
        transcription_model=None,
        author="unit",
        ingestion_date=None,
        overwrite=False,
        chunk_options=None,
        chunks=chunks,
    )
    assert mid

    retr = MediaDBRetriever(
        db_path=None,
        config=RetrievalConfig(max_results=5, use_fts=True, fts_level='chunk'),
        media_db=db,
        user_id="unit",
    )
    # Monkeypatch db.execute_query to simulate FTS results while still using real structure lookups
    original_execute = db.execute_query

    class _CursorStub:
        def __init__(self, rows):
            self._rows = rows
        def fetchall(self):
            return self._rows
        def fetchone(self):
            return self._rows[0] if self._rows else None

    def fake_execute_query(query: str, params=None, *, commit: bool = False):
        q = (query or "").lower()
        if "from unvectorized_chunks_fts" in q and "join" in q:
            # Simulate one chunk row resulting from FTS
            rows = [{
                'chunk_uuid': 'stub-uuid-1',
                'chunk_rowid': 1,
                'media_id': mid,
                'chunk_text': chunks[0]['text'],
                'start_char': chunks[0]['start_char'],
                'end_char': chunks[0]['end_char'],
                'chunk_type': chunks[0]['chunk_type'],
                'chunk_index': 0,
                'title': 'Struct Doc 2',
                'media_type': 'web_document',
                'url': 'local://test-retrieval',
                'rank': 1.0,
            }]
            return _CursorStub(rows)
        if "select count(*) as c from unvectorized_chunks_fts" in q:
            return _CursorStub([{'c': 1}])
        return original_execute(query, params, commit=commit)

    db.execute_query = fake_execute_query  # type: ignore

    docs = await retr.retrieve(query="Intro", media_type="web_document")
    assert docs, "expected some docs from simulated chunk-FTS"
    md = docs[0].metadata or {}
    assert "section_title" in md and md["section_title"], "missing section_title enrichment"
    assert "section_start" in md and md["section_end"] is not None
