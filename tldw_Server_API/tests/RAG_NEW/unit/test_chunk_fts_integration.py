import pytest

from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import MediaDBRetriever, RetrievalConfig


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chunk_fts_integration_retrieves_matches():
    db = MediaDatabase(db_path=":memory:", client_id="test")

    content = "Alpha beta.\n\nGamma delta."
    s1 = content.index("Alpha")
    e1 = s1 + len("Alpha beta.")
    s2 = content.index("Gamma")
    e2 = s2 + len("Gamma delta.")

    chunks = [
        {
            "text": content[s1:e1],
            "start_char": s1,
            "end_char": e1,
            "chunk_type": "text",
            "metadata": {"section_path": "Intro"},
        },
        {
            "text": content[s2:e2],
            "start_char": s2,
            "end_char": e2,
            "chunk_type": "text",
            "metadata": {"section_path": "Methods"},
        },
    ]

    media_id, _, _ = db.add_media_with_keywords(
        url="local://chunk-fts",
        title="Chunk FTS Doc",
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
    assert media_id is not None

    db.ensure_chunk_fts()
    db.maybe_rebuild_chunk_fts_if_empty()

    retriever = MediaDBRetriever(
        db_path=None,
        config=RetrievalConfig(max_results=5, use_fts=True, fts_level="chunk"),
        media_db=db,
        user_id="unit",
    )

    docs = await retriever.retrieve(query="Gamma", media_type="web_document")
    assert docs
    assert "Gamma" in docs[0].content
    assert docs[0].metadata.get("chunk_type") == "text"
    assert docs[0].start_char == s2
