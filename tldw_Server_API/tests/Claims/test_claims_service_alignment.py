from __future__ import annotations

from tldw_Server_API.app.core.Claims_Extraction import claims_service
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.config import settings


def _seed_alignment_db(tmp_path):
    db_path = str(tmp_path / "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()
    content = "state-of-the-art systems are common."
    media_id, _, _ = db.add_media_with_keywords(
        title="Doc",
        media_type="text",
        content=content,
        keywords=None,
    )
    db.process_unvectorized_chunks(
        media_id=media_id,
        chunks=[
            {
                "chunk_text": content,
                "chunk_index": 0,
                "start_char": 10,
                "end_char": 10 + len(content),
                "chunk_type": "text",
            }
        ],
    )
    return db, media_id


def test_corrected_span_uses_fuzzy_alignment_with_offset(monkeypatch, tmp_path):
    db, media_id = _seed_alignment_db(tmp_path)
    try:
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_MODE", "fuzzy")
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_THRESHOLD", 0.6)
        span = claims_service._resolve_corrected_claim_span(
            target_db=db,
            claim_row={"media_id": media_id, "chunk_index": 0},
            corrected_text="state of the art systems",
        )
        assert span == (10, 34)
    finally:
        db.close_connection()


def test_corrected_span_off_mode_disables_alignment(monkeypatch, tmp_path):
    db, media_id = _seed_alignment_db(tmp_path)
    try:
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_MODE", "off")
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_THRESHOLD", 0.6)
        span = claims_service._resolve_corrected_claim_span(
            target_db=db,
            claim_row={"media_id": media_id, "chunk_index": 0},
            corrected_text="state-of-the-art systems",
        )
        assert span == (None, None)
    finally:
        db.close_connection()
