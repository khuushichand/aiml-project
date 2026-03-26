from __future__ import annotations

from pathlib import Path

from tldw_Server_API.app.core.Claims_Extraction import claims_service
from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.config import settings


def _seed_alignment_db(tmp_path: Path) -> tuple[MediaDatabase, int]:
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


def _seed_alignment_db_with_content(tmp_path: Path, content: str) -> tuple[MediaDatabase, int]:
    db_path = str(tmp_path / "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()
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


def test_corrected_span_handles_segmented_non_spaced_script_query(monkeypatch, tmp_path):
    db, media_id = _seed_alignment_db_with_content(tmp_path, "東京大学は有名です")
    try:
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_MODE", "fuzzy")
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_THRESHOLD", 0.6)
        span = claims_service._resolve_corrected_claim_span(
            target_db=db,
            claim_row={"media_id": media_id, "chunk_index": 0},
            corrected_text="東京 大学 は 有名 です",
        )
        assert span == (10, 19)
    finally:
        db.close_connection()


def test_corrected_span_rejects_character_level_near_match_without_token_overlap(monkeypatch, tmp_path):
    db, media_id = _seed_alignment_db_with_content(tmp_path, "alpha beta gamma")
    try:
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_MODE", "fuzzy")
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_THRESHOLD", 0.75)
        span = claims_service._resolve_corrected_claim_span(
            target_db=db,
            claim_row={"media_id": media_id, "chunk_index": 0},
            corrected_text="alphx bety gammz",
        )
        assert span == (None, None)
    finally:
        db.close_connection()


def test_corrected_span_handles_mixed_script_token_boundaries(monkeypatch, tmp_path):
    db, media_id = _seed_alignment_db_with_content(tmp_path, "AcmeБета launched today.")
    try:
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_MODE", "fuzzy")
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_THRESHOLD", 0.75)
        span = claims_service._resolve_corrected_claim_span(
            target_db=db,
            claim_row={"media_id": media_id, "chunk_index": 0},
            corrected_text="Acme Бета launched",
        )
        assert span == (10, 27)
    finally:
        db.close_connection()


def test_corrected_span_prefers_tight_partial_overlap_window(monkeypatch, tmp_path):
    content = "Findings consistent with degenerative disc disease at L5-S1."
    db, media_id = _seed_alignment_db_with_content(tmp_path, content)
    try:
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_MODE", "fuzzy")
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_THRESHOLD", 0.75)
        span = claims_service._resolve_corrected_claim_span(
            target_db=db,
            claim_row={"media_id": media_id, "chunk_index": 0},
            corrected_text="mild degenerative disc disease",
        )
        assert span == (35, 60)
    finally:
        db.close_connection()


def test_corrected_span_splits_letter_digit_boundaries(monkeypatch, tmp_path):
    content = "Findings consistent with degenerative disc disease at L5-S1."
    db, media_id = _seed_alignment_db_with_content(tmp_path, content)
    try:
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_MODE", "fuzzy")
        monkeypatch.setitem(settings, "CLAIMS_ALIGNMENT_THRESHOLD", 0.75)
        span = claims_service._resolve_corrected_claim_span(
            target_db=db,
            claim_row={"media_id": media_id, "chunk_index": 0},
            corrected_text="degenerative disc disease at L 5 S 1",
        )
        assert span == (35, 69)
    finally:
        db.close_connection()
