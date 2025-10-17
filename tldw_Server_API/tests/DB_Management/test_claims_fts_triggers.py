import os
import tempfile

import asyncio
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import ClaimsRetriever, RetrievalConfig


def _search_claims(db_path: str, term: str):
    async def _run():
        retr = ClaimsRetriever(db_path)
        retr.config = RetrievalConfig(max_results=10)
        return await retr.retrieve(term)
    return asyncio.run(_run())


def test_claims_fts_triggers_insert_update_delete():
    temp_dir = tempfile.mkdtemp(prefix="claims_triggers_")
    db_path = os.path.join(temp_dir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="test_client")
    db.initialize_db()
    try:
        # Insert media + claim
        media_id, _, _ = db.add_media_with_keywords(title="Doc", media_type="text", content="abc", keywords=None)
        rows = [{
            "media_id": media_id,
            "chunk_index": 0,
            "claim_text": "Python is great",
            "extractor": "heuristic",
            "extractor_version": "v1",
            "chunk_hash": "h",
        }]
        db.upsert_claims(rows)

        # Search returns hit for 'Python'
        res = _search_claims(db_path, 'Python')
        assert any('Python is great' == d.content for d in res)

        # Update claim_text -> FTS no longer matches old term, but matches new
        cur = db.execute_query("SELECT id FROM Claims LIMIT 1")
        cid = int(cur.fetchone()[0])
        db.execute_query("UPDATE Claims SET claim_text = ? WHERE id = ?", ("Rust is great", cid), commit=True)
        assert not _search_claims(db_path, 'Python')
        res2 = _search_claims(db_path, 'Rust')
        assert any('Rust is great' == d.content for d in res2)

        # Soft delete -> FTS returns no results
        db.soft_delete_claims_for_media(media_id)
        assert not _search_claims(db_path, 'Rust')
    finally:
        try:
            db.close_connection()
        except Exception:
            pass
