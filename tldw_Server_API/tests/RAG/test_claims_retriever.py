import os
import tempfile
import asyncio

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import ClaimsRetriever, RetrievalConfig


async def _retrieve_claims(db_path: str, query: str):
    retriever = ClaimsRetriever(db_path)
    retriever.config = RetrievalConfig(max_results=10)
    return await retriever.retrieve(query)


def test_claims_retriever_fts_search_returns_documents():
    temp_dir = tempfile.mkdtemp(prefix="claims_rag_")
    db_path = os.path.join(temp_dir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="test_client")
    db.initialize_db()
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
        docs = asyncio.get_event_loop().run_until_complete(_retrieve_claims(db_path, "programming"))
        assert docs and any("programming language" in d.content for d in docs)
    finally:
        try:
            db.close_connection()
        except Exception:
            pass

