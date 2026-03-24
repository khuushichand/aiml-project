import json
import os
import tempfile

from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.Claims_Extraction.ingestion_claims import store_claims


def _seed_db(url: str) -> tuple[MediaDatabase, int, str]:
    tmpdir = tempfile.mkdtemp(prefix="claims_review_rules_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()
    content = "Alpha beta gamma."
    media_id, _, _ = db.add_media_with_keywords(
        title="Doc",
        media_type="text",
        content=content,
        keywords=None,
        url=url,
    )
    return db, media_id, content


def test_claim_review_rule_assignment_applies():


    db, media_id, content = _seed_db("https://example.com/article")
    try:
        db.create_claim_review_rule(
            user_id="1",
            priority=10,
            predicate_json=json.dumps({"source_domain": "example.com"}),
            reviewer_id=42,
            review_group=None,
            active=True,
        )
        store_claims(
            db,
            media_id=media_id,
            chunk_texts_by_index={0: content},
            claims=[{"chunk_index": 0, "claim_text": "Alpha beta gamma."}],
            extractor="heuristic",
            extractor_version="v1",
        )
        row = db.execute_query(
            "SELECT reviewer_id FROM Claims WHERE media_id = ? AND deleted = 0",
            (media_id,),
        ).fetchone()
        reviewer_id = row["reviewer_id"] if isinstance(row, dict) else row[0]
        assert int(reviewer_id) == 42
        notifications = db.list_claim_notifications(user_id="1", kind="review_assignment", delivered=False)
        assert any(int(n.get("target_user_id") or 0) == 42 for n in notifications)
    finally:
        db.close_connection()


def test_claim_review_rule_assignment_skips_mismatch():


    db, media_id, content = _seed_db("https://example.com/article")
    try:
        db.create_claim_review_rule(
            user_id="1",
            priority=10,
            predicate_json=json.dumps({"source_domain": "other.example.com"}),
            reviewer_id=42,
            review_group=None,
            active=True,
        )
        store_claims(
            db,
            media_id=media_id,
            chunk_texts_by_index={0: content},
            claims=[{"chunk_index": 0, "claim_text": "Alpha beta gamma."}],
            extractor="heuristic",
            extractor_version="v1",
        )
        row = db.execute_query(
            "SELECT reviewer_id FROM Claims WHERE media_id = ? AND deleted = 0",
            (media_id,),
        ).fetchone()
        reviewer_id = row["reviewer_id"] if isinstance(row, dict) else row[0]
        assert reviewer_id is None
    finally:
        db.close_connection()
