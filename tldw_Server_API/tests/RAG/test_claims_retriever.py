import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import ClaimsRetriever, RetrievalConfig


async def _retrieve_claims(db_path: str, query: str):
    retriever = ClaimsRetriever(db_path)
    retriever.config = RetrievalConfig(max_results=10)
    return await retriever.retrieve(query)


@pytest.mark.asyncio
async def test_claims_retriever_fts_search_returns_documents(tmp_path):
    db_path = tmp_path / "media.db"
    db = MediaDatabase(db_path=db_path, client_id="test_client")
    db.initialize_db()
    docs = []
    try:
        # Add media and claims
        content = "Python is a programming language. It is popular."
        media_id, _, _ = db.add_media_with_keywords(title="Py", media_type="text", content=content, keywords=None)
        rows = [
            {
                "media_id": media_id,
                "chunk_index": 0,
                "claim_text": "Python is a programming language.",
                "extractor": "heuristic",
                "extractor_version": "v1",
                "chunk_hash": "abc",
            }
        ]
        db.upsert_claims(rows)
        # Run retriever
        docs = await _retrieve_claims(str(db_path), "programming")
    finally:
        try:
            db.close_connection()
        except Exception:
            pass
    assert docs, "Claims retriever should return at least one matching document"
    assert any("programming language" in doc.content for doc in docs), "Expected retrieved content to include the claim text"
