import hashlib
import os
import tempfile

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


@pytest.fixture
def temp_media_db_path():
    d = tempfile.mkdtemp(prefix="test_claims_db_")
    try:
        yield os.path.join(d, "media.db")
    finally:
        try:
            # best-effort cleanup
            import shutil
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass


def _mk_db(path: str) -> MediaDatabase:
    db = MediaDatabase(db_path=path, client_id="test_client")
    db.initialize_db()
    return db


def test_claims_table_exists(temp_media_db_path):
    db = _mk_db(temp_media_db_path)
    conn = db.get_connection()
    cur = conn.execute("PRAGMA table_info(Claims)")
    cols = [r[1] for r in cur.fetchall()]
    assert "claim_text" in cols and "media_id" in cols

    cur2 = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='claims_fts'")
    assert cur2.fetchone() is not None


def test_insert_and_fetch_claims(temp_media_db_path):
    db = _mk_db(temp_media_db_path)

    # Create a minimal media record via helper
    content = "Hello world content for claims"
    media_id, media_uuid, msg = db.add_media_with_keywords(
        url=None,
        title="Doc",
        media_type="text",
        content=content,
        keywords=None,
    )
    assert media_id is not None

    # Insert a claim
    chunk_hash = hashlib.sha256(content.encode()).hexdigest()
    inserted = db.upsert_claims([
        {
            "media_id": media_id,
            "chunk_index": 0,
            "span_start": 0,
            "span_end": 5,
            "claim_text": "Hello world is present",
            "confidence": 0.9,
            "extractor": "heuristic",
            "extractor_version": "v1",
            "chunk_hash": chunk_hash,
            "client_id": "test_client",
        }
    ])
    assert inserted == 1

    claims = db.get_claims_by_media(media_id)
    assert len(claims) == 1
    assert claims[0]["claim_text"].startswith("Hello world")
