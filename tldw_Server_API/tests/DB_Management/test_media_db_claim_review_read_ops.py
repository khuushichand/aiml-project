from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_review_read_ops import (
    list_claim_review_history as helper_list_claim_review_history,
    list_review_queue as helper_list_review_queue,
)


pytestmark = pytest.mark.unit


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-review-read-helper")
    db.initialize_db()
    return db


def _seed_review_claim(
    db: MediaDatabase,
    *,
    title: str,
    content: str,
    owner_user_id: int,
    visibility: str = "personal",
    team_id: int | None = None,
    org_id: int | None = None,
    review_status: str = "pending",
    reviewer_id: int | None = None,
    review_group: str | None = None,
    extractor: str = "heuristic",
    deleted: int = 0,
    reviewed_at: str | None = None,
) -> tuple[int, int]:
    now = db._get_current_utc_timestamp_str()
    media_id, _, _ = db.add_media_with_keywords(
        title=title,
        media_type="text",
        content=content,
        keywords=None,
    )
    db.execute_query(
        (
            "UPDATE Media SET owner_user_id = ?, visibility = ?, team_id = ?, org_id = ?, "
            "last_modified = ?, version = version + 1 WHERE id = ?"
        ),
        (owner_user_id, visibility, team_id, org_id, now, int(media_id)),
        commit=True,
    )
    chunk_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    db.upsert_claims(
        [
            {
                "media_id": media_id,
                "chunk_index": 0,
                "span_start": None,
                "span_end": None,
                "claim_text": f"{title} claim",
                "confidence": 0.8,
                "extractor": extractor,
                "extractor_version": "v1",
                "chunk_hash": chunk_hash,
            }
        ]
    )
    row = db.execute_query(
        "SELECT id FROM Claims WHERE media_id = ? ORDER BY id DESC LIMIT 1",
        (int(media_id),),
    ).fetchone()
    claim_id = int(row["id"])
    db.execute_query(
        (
            "UPDATE Claims SET review_status = ?, reviewer_id = ?, review_group = ?, "
            "extractor = ?, deleted = ?, reviewed_at = ?, last_modified = ?, version = version + 1 "
            "WHERE id = ?"
        ),
        (
            review_status,
            reviewer_id,
            review_group,
            extractor,
            int(deleted),
            reviewed_at,
            now,
            claim_id,
        ),
        commit=True,
    )
    return int(media_id), claim_id


def test_list_claim_review_history_returns_created_at_ascending_rows(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claim-review-history.db")
    try:
        assert db.list_claim_review_history.__func__ is helper_list_claim_review_history

        _media_id, claim_id = _seed_review_claim(
            db,
            title="History",
            content="History content",
            owner_user_id=1,
            review_status="approved",
            reviewer_id=7,
            reviewed_at="2026-03-21T00:00:30Z",
        )
        db.execute_query(
            (
                "INSERT INTO claims_review_log "
                "(claim_id, old_status, new_status, old_text, new_text, reviewer_id, notes, reason_code, "
                "action_ip, action_user_agent, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                claim_id,
                "pending",
                "flagged",
                "old-1",
                "new-1",
                7,
                "first",
                "reason-1",
                None,
                None,
                "2026-03-21T00:00:01Z",
            ),
            commit=True,
        )
        db.execute_query(
            (
                "INSERT INTO claims_review_log "
                "(claim_id, old_status, new_status, old_text, new_text, reviewer_id, notes, reason_code, "
                "action_ip, action_user_agent, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                claim_id,
                "flagged",
                "approved",
                "old-2",
                "new-2",
                8,
                "second",
                "reason-2",
                None,
                None,
                "2026-03-21T00:00:02Z",
            ),
            commit=True,
        )

        rows = db.list_claim_review_history(claim_id)

        assert [(row["notes"], row["created_at"]) for row in rows] == [
            ("first", "2026-03-21T00:00:01Z"),
            ("second", "2026-03-21T00:00:02Z"),
        ]
    finally:
        db.close_connection()


def test_list_review_queue_preserves_filters_order_and_paging_normalization(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claim-review-queue-filters.db")
    try:
        assert db.list_review_queue.__func__ is helper_list_review_queue

        matching_media_id, first_claim_id = _seed_review_claim(
            db,
            title="Queue first",
            content="Queue content one",
            owner_user_id=1,
            review_status="approved",
            reviewer_id=7,
            review_group="reviewers",
            extractor="heuristic",
            reviewed_at="2026-03-21T00:00:01Z",
        )
        _same_media_id, second_claim_id = _seed_review_claim(
            db,
            title="Queue second",
            content="Queue content two",
            owner_user_id=1,
            review_status="approved",
            reviewer_id=7,
            review_group="reviewers",
            extractor="heuristic",
            reviewed_at="2026-03-21T00:00:03Z",
        )
        _deleted_media_id, deleted_claim_id = _seed_review_claim(
            db,
            title="Queue deleted",
            content="Queue content deleted",
            owner_user_id=1,
            review_status="approved",
            reviewer_id=7,
            review_group="reviewers",
            extractor="heuristic",
            deleted=1,
            reviewed_at="2026-03-21T00:00:04Z",
        )
        _mismatch_media_id, _mismatch_claim_id = _seed_review_claim(
            db,
            title="Queue mismatch",
            content="Queue content mismatch",
            owner_user_id=2,
            review_status="pending",
            reviewer_id=8,
            review_group="other",
            extractor="other-extractor",
            reviewed_at="2026-03-21T00:00:05Z",
        )

        clamped_rows = db.list_review_queue(
            status="approved",
            reviewer_id=7,
            review_group="reviewers",
            extractor="heuristic",
            owner_user_id=1,
            limit=0,
            offset=-3,
            include_deleted=False,
        )
        filtered_rows = db.list_review_queue(
            status="approved",
            reviewer_id=7,
            review_group="reviewers",
            media_id=matching_media_id,
            extractor="heuristic",
            owner_user_id=1,
            limit=100,
            offset=0,
            include_deleted=False,
        )
        defaulted_rows = db.list_review_queue(
            status="approved",
            reviewer_id=7,
            review_group="reviewers",
            extractor="heuristic",
            owner_user_id=1,
            limit="oops",
            offset="oops",
            include_deleted=False,
        )
        deleted_rows = db.list_review_queue(
            status="approved",
            reviewer_id=7,
            review_group="reviewers",
            extractor="heuristic",
            owner_user_id=1,
            limit=100,
            offset=0,
            include_deleted=True,
        )

        assert [int(row["id"]) for row in clamped_rows] == [int(second_claim_id)]
        assert [int(row["id"]) for row in filtered_rows] == [int(first_claim_id)]
        assert [int(row["id"]) for row in defaulted_rows] == [
            int(second_claim_id),
            int(first_claim_id),
        ]
        assert [int(row["id"]) for row in deleted_rows] == [
            int(deleted_claim_id),
            int(second_claim_id),
            int(first_claim_id),
        ]
    finally:
        db.close_connection()


def test_list_review_queue_respects_scope_visibility_filters(monkeypatch, tmp_path: Path) -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        claims_review_read_ops as claims_review_read_ops_module,
    )

    db = _make_db(tmp_path, "claim-review-queue-scope.db")
    try:
        _seed_review_claim(
            db,
            title="Personal visible",
            content="Visible personal",
            owner_user_id=1,
            visibility="personal",
            review_status="pending",
            reviewer_id=7,
        )
        _seed_review_claim(
            db,
            title="Team visible",
            content="Visible team",
            owner_user_id=9,
            visibility="team",
            team_id=11,
            review_status="pending",
            reviewer_id=7,
        )
        _seed_review_claim(
            db,
            title="Org visible",
            content="Visible org",
            owner_user_id=9,
            visibility="org",
            org_id=21,
            review_status="pending",
            reviewer_id=7,
        )
        _seed_review_claim(
            db,
            title="Hidden personal",
            content="Hidden personal",
            owner_user_id=2,
            visibility="personal",
            review_status="pending",
            reviewer_id=7,
        )

        monkeypatch.setattr(
            claims_review_read_ops_module,
            "get_scope",
            lambda: SimpleNamespace(is_admin=False, user_id=1, team_ids=[11], org_ids=[21]),
        )
        visible_rows = db.list_review_queue(status="pending", reviewer_id=7)

        monkeypatch.setattr(
            claims_review_read_ops_module,
            "get_scope",
            lambda: SimpleNamespace(is_admin=False, user_id=None, team_ids=[], org_ids=[]),
        )
        hidden_rows = db.list_review_queue(status="pending", reviewer_id=7)

        assert {row["media_title"] for row in visible_rows} == {
            "Personal visible",
            "Team visible",
            "Org visible",
        }
        assert hidden_rows == []
    finally:
        db.close_connection()
