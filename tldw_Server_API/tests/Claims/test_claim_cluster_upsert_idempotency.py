import hashlib
import os
import shutil
import tempfile

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def _seed_cluster_db() -> tuple[MediaDatabase, str, int, int, int]:
    tmpdir = tempfile.mkdtemp(prefix="claims_cluster_upsert_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()

    content = "Alpha claim. Beta claim."
    media_id, _, _ = db.add_media_with_keywords(
        title="Doc",
        media_type="text",
        content=content,
        keywords=None,
    )
    chunk_hash = hashlib.sha256(content.encode()).hexdigest()
    db.upsert_claims(
        [
            {
                "media_id": media_id,
                "chunk_index": 0,
                "span_start": None,
                "span_end": None,
                "claim_text": "Alpha claim",
                "confidence": 0.8,
                "extractor": "heuristic",
                "extractor_version": "v1",
                "chunk_hash": chunk_hash,
            },
            {
                "media_id": media_id,
                "chunk_index": 0,
                "span_start": None,
                "span_end": None,
                "claim_text": "Beta claim",
                "confidence": 0.8,
                "extractor": "heuristic",
                "extractor_version": "v1",
                "chunk_hash": chunk_hash,
            },
        ]
    )

    rows = db.execute_query(
        "SELECT id, claim_text FROM Claims WHERE media_id = ? AND deleted = 0",
        (media_id,),
    ).fetchall()
    claim_ids = {row["claim_text"]: int(row["id"]) for row in rows}

    cluster_a = db.create_claim_cluster(
        user_id="1",
        canonical_claim_text="Alpha claim",
        representative_claim_id=claim_ids["Alpha claim"],
    )
    cluster_b = db.create_claim_cluster(
        user_id="1",
        canonical_claim_text="Beta claim",
        representative_claim_id=claim_ids["Beta claim"],
    )

    return (
        db,
        tmpdir,
        int(cluster_a["id"]),
        int(cluster_b["id"]),
        int(claim_ids["Alpha claim"]),
    )


def test_add_claim_to_cluster_duplicate_insert_is_idempotent():
    db, tmpdir, cluster_a_id, _cluster_b_id, claim_id = _seed_cluster_db()
    try:
        db.add_claim_to_cluster(
            cluster_id=cluster_a_id,
            claim_id=claim_id,
            similarity_score=1.0,
        )
        db.add_claim_to_cluster(
            cluster_id=cluster_a_id,
            claim_id=claim_id,
            similarity_score=1.0,
        )

        row = db.execute_query(
            (
                "SELECT COUNT(*) AS total "
                "FROM claim_cluster_membership "
                "WHERE cluster_id = ? AND claim_id = ?"
            ),
            (cluster_a_id, claim_id),
        ).fetchone()
        assert int(row["total"]) == 1
    finally:
        try:
            db.close_connection()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


def test_create_claim_cluster_link_duplicate_insert_is_idempotent():
    db, tmpdir, cluster_a_id, cluster_b_id, _claim_id = _seed_cluster_db()
    try:
        db.create_claim_cluster_link(
            parent_cluster_id=cluster_a_id,
            child_cluster_id=cluster_b_id,
            relation_type="related",
        )
        db.create_claim_cluster_link(
            parent_cluster_id=cluster_a_id,
            child_cluster_id=cluster_b_id,
            relation_type="related",
        )

        row = db.execute_query(
            (
                "SELECT COUNT(*) AS total "
                "FROM claim_cluster_links "
                "WHERE parent_cluster_id = ? AND child_cluster_id = ?"
            ),
            (cluster_a_id, cluster_b_id),
        ).fetchone()
        assert int(row["total"]) == 1
    finally:
        try:
            db.close_connection()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
