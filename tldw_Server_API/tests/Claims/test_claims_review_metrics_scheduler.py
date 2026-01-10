import hashlib
import json
import os
import tempfile

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.services.claims_review_metrics_scheduler import run_claims_review_metrics_once


def _seed_review_metrics_db() -> MediaDatabase:


     tmpdir = tempfile.mkdtemp(prefix="claims_review_metrics_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()
    content = "A. B."
    media_id, _, _ = db.add_media_with_keywords(title="Doc", media_type="text", content=content, keywords=None)
    chunk_hash = hashlib.sha256(content.encode()).hexdigest()
    db.upsert_claims([
        {
            "media_id": media_id,
            "chunk_index": 0,
            "span_start": None,
            "span_end": None,
            "claim_text": "A.",
            "confidence": 0.8,
            "extractor": "heuristic",
            "extractor_version": "v1",
            "chunk_hash": chunk_hash,
        },
        {
            "media_id": media_id,
            "chunk_index": 1,
            "span_start": None,
            "span_end": None,
            "claim_text": "B.",
            "confidence": 0.7,
            "extractor": "llm",
            "extractor_version": "v2",
            "chunk_hash": chunk_hash,
        },
    ])
    rows = db.execute_query(
        "SELECT id FROM Claims WHERE media_id = ? ORDER BY id ASC",
        (media_id,),
    ).fetchall()
    claim_ids = [int(r["id"]) if isinstance(r, dict) else int(r[0]) for r in rows]

    db.update_claim_review(
        claim_ids[0],
        review_status="approved",
        reviewer_id=1,
        review_notes="ok",
        review_reason_code="typo",
        corrected_text="A1.",
    )
    db.update_claim_review(
        claim_ids[1],
        review_status="rejected",
        reviewer_id=1,
        review_notes="no",
        review_reason_code="spam",
    )

    log_rows = db.execute_query(
        "SELECT id FROM claims_review_log ORDER BY id ASC"
    ).fetchall()
    for row in log_rows:
        log_id = int(row["id"]) if isinstance(row, dict) else int(row[0])
        db.execute_query(
            "UPDATE claims_review_log SET created_at = ? WHERE id = ?",
            ("2024-01-10 01:00:00", log_id),
            commit=True,
        )
    return db


@pytest.mark.asyncio
async def test_claims_review_metrics_scheduler_writes_daily() -> None:
    db = _seed_review_metrics_db()
    try:
        written = await run_claims_review_metrics_once(
            db=db,
            target_user_id="1",
            report_date="2024-01-10",
        )
        assert written == 2

        rows = db.list_claims_review_extractor_metrics_daily(
            user_id="1",
            start_date="2024-01-10",
            end_date="2024-01-10",
        )
        assert len(rows) == 2
        metrics = {(row["extractor"], row["extractor_version"]): row for row in rows}

        heuristic = metrics.get(("heuristic", "v1"))
        assert heuristic["approved_count"] == 1
        assert heuristic["edited_count"] == 1
        heuristic_reasons = json.loads(heuristic["reason_code_counts_json"])
        assert heuristic_reasons["typo"] == 1

        llm_metrics = metrics.get(("llm", "v2"))
        assert llm_metrics["rejected_count"] == 1
        llm_reasons = json.loads(llm_metrics["reason_code_counts_json"])
        assert llm_reasons["spam"] == 1

        written_again = await run_claims_review_metrics_once(
            db=db,
            target_user_id="1",
            report_date="2024-01-10",
        )
        assert written_again == 2
        rows_again = db.list_claims_review_extractor_metrics_daily(
            user_id="1",
            start_date="2024-01-10",
            end_date="2024-01-10",
        )
        assert len(rows_again) == 2
    finally:
        db.close_connection()
