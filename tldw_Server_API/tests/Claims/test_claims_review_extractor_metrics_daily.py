import json
import os
import tempfile

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def test_claims_review_extractor_metrics_daily_upsert_and_list() -> None:


     tmpdir = tempfile.mkdtemp(prefix="claims_review_metrics_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()

    initial = db.upsert_claims_review_extractor_metrics_daily(
        user_id="1",
        report_date="2024-01-10",
        extractor="heuristic",
        extractor_version="v1",
        total_reviewed=10,
        approved_count=7,
        rejected_count=2,
        flagged_count=1,
        reassigned_count=0,
        edited_count=1,
        reason_code_counts_json=json.dumps({"spam": 2}),
    )
    assert initial["total_reviewed"] == 10
    assert initial["approved_count"] == 7
    assert initial["rejected_count"] == 2
    assert initial["flagged_count"] == 1
    assert initial["edited_count"] == 1

    updated = db.upsert_claims_review_extractor_metrics_daily(
        user_id="1",
        report_date="2024-01-10",
        extractor="heuristic",
        extractor_version="v1",
        total_reviewed=12,
        approved_count=8,
        rejected_count=2,
        flagged_count=1,
        reassigned_count=1,
        edited_count=2,
        reason_code_counts_json=json.dumps({"spam": 3}),
    )
    assert updated["id"] == initial["id"]
    assert updated["total_reviewed"] == 12
    assert updated["reassigned_count"] == 1
    assert updated["edited_count"] == 2
    assert updated["reason_code_counts_json"] == json.dumps({"spam": 3})

    db.upsert_claims_review_extractor_metrics_daily(
        user_id="1",
        report_date="2024-01-11",
        extractor="heuristic",
        extractor_version=None,
        total_reviewed=4,
        approved_count=4,
        rejected_count=0,
        flagged_count=0,
        reassigned_count=0,
        edited_count=0,
        reason_code_counts_json=json.dumps({"none": 4}),
    )

    rows = db.list_claims_review_extractor_metrics_daily(
        user_id="1",
        start_date="2024-01-10",
        end_date="2024-01-10",
    )
    assert len(rows) == 1
    assert rows[0]["report_date"] == "2024-01-10"

    empty_version_rows = db.list_claims_review_extractor_metrics_daily(
        user_id="1",
        extractor_version="",
    )
    assert empty_version_rows
    assert all(row["extractor_version"] == "" for row in empty_version_rows)
    assert any(row["report_date"] == "2024-01-11" for row in empty_version_rows)

    db.close_connection()
