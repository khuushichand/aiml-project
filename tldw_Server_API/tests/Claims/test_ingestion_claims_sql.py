import os
import tempfile

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.ingestion_claims import (
    extract_claims_for_chunks,
    store_claims,
)
from tldw_Server_API.app.core.Chunking import chunk_for_embedding


def test_ingestion_time_claims_extract_and_store_sql():
    # Setup temp DB
    temp_dir = tempfile.mkdtemp(prefix="claims_sql_")
    db_path = os.path.join(temp_dir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="test_client")
    db.initialize_db()
    try:
        # Create media row
        content = "Hello world. This is a test document. It contains a few sentences."
        media_id, media_uuid, _ = db.add_media_with_keywords(
            title="Doc",
            media_type="text",
            content=content,
            keywords=None,
        )
        assert media_id is not None

        # Chunk and extract
        chunks = chunk_for_embedding(content, file_name="doc.txt", max_size=50)
        claims = extract_claims_for_chunks(chunks, extractor_mode="heuristic", max_per_chunk=2)
        assert claims, "No claims extracted"

        # Build chunk_index->text map
        chunk_text_map = {int(ch.get("metadata", {}).get("chunk_index", 0)): ch.get("text", "") for ch in chunks}
        inserted = store_claims(db, media_id=media_id, chunk_texts_by_index=chunk_text_map, claims=claims)
        assert inserted == len(claims)

        # Verify fetch
        rows = db.get_claims_by_media(media_id)
        assert len(rows) == inserted
        assert any("Hello world" in r["claim_text"] or "test document" in r["claim_text"] for r in rows)
    finally:
        try:
            db.close_connection()
        except Exception:
            pass
