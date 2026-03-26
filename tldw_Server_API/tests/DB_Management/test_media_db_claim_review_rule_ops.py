from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_review_rule_ops import (
    create_claim_review_rule as helper_create_claim_review_rule,
    delete_claim_review_rule as helper_delete_claim_review_rule,
    get_claim_review_rule as helper_get_claim_review_rule,
    list_claim_review_rules as helper_list_claim_review_rules,
    update_claim_review_rule as helper_update_claim_review_rule,
)


pytestmark = pytest.mark.unit


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-review-rule-helper")
    db.initialize_db()
    return db


def test_create_claim_review_rule_returns_stored_row_and_rebinds_canonical_method(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claim-review-rule-create.db")
    try:
        assert db.create_claim_review_rule.__func__ is helper_create_claim_review_rule
        assert db.get_claim_review_rule.__func__ is helper_get_claim_review_rule

        row = db.create_claim_review_rule(
            user_id="1",
            priority=10,
            predicate_json='{"source_domain":"example.com"}',
            reviewer_id=42,
            review_group=None,
            active=True,
        )

        assert int(row["id"]) > 0
        assert row["user_id"] == "1"
        assert row["priority"] == 10
        assert row["predicate_json"] == '{"source_domain":"example.com"}'
        assert row["reviewer_id"] == 42
        assert row["review_group"] is None
        assert bool(row["active"]) is True
        assert row["created_at"]
        assert row["updated_at"]
    finally:
        db.close_connection()


def test_list_claim_review_rules_honors_active_only_and_priority_order(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claim-review-rule-list.db")
    try:
        assert db.list_claim_review_rules.__func__ is helper_list_claim_review_rules

        lower = db.create_claim_review_rule(
            user_id="1",
            priority=5,
            predicate_json='{"tag":"low"}',
            reviewer_id=5,
            active=True,
        )
        first_high = db.create_claim_review_rule(
            user_id="1",
            priority=10,
            predicate_json='{"tag":"high-a"}',
            reviewer_id=10,
            active=True,
        )
        second_high = db.create_claim_review_rule(
            user_id="1",
            priority=10,
            predicate_json='{"tag":"high-b"}',
            reviewer_id=11,
            active=False,
        )

        all_rules = db.list_claim_review_rules("1", active_only=False)
        active_rules = db.list_claim_review_rules("1", active_only=True)

        assert [int(row["id"]) for row in all_rules] == [
            int(second_high["id"]),
            int(first_high["id"]),
            int(lower["id"]),
        ]
        assert [int(row["id"]) for row in active_rules] == [
            int(first_high["id"]),
            int(lower["id"]),
        ]
    finally:
        db.close_connection()


def test_get_missing_rule_and_update_rule_preserve_expected_behavior(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claim-review-rule-update.db")
    try:
        assert db.get_claim_review_rule.__func__ is helper_get_claim_review_rule
        assert db.update_claim_review_rule.__func__ is helper_update_claim_review_rule

        created = db.create_claim_review_rule(
            user_id="1",
            priority=10,
            predicate_json='{"source_domain":"example.com"}',
            reviewer_id=42,
            active=True,
        )

        assert db.get_claim_review_rule(999999) == {}

        unchanged = db.update_claim_review_rule(int(created["id"]))
        updated = db.update_claim_review_rule(
            int(created["id"]),
            priority=12,
            predicate_json='{"source_domain":"example.org"}',
            reviewer_id=84,
            review_group="moderators",
            active=False,
        )

        assert int(unchanged["id"]) == int(created["id"])
        assert unchanged["priority"] == 10
        assert updated["priority"] == 12
        assert updated["predicate_json"] == '{"source_domain":"example.org"}'
        assert updated["reviewer_id"] == 84
        assert updated["review_group"] == "moderators"
        assert bool(updated["active"]) is False
    finally:
        db.close_connection()


def test_delete_claim_review_rule_removes_row(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claim-review-rule-delete.db")
    try:
        assert db.delete_claim_review_rule.__func__ is helper_delete_claim_review_rule

        created = db.create_claim_review_rule(
            user_id="1",
            priority=10,
            predicate_json='{"source_domain":"example.com"}',
            reviewer_id=42,
            active=True,
        )

        result = db.delete_claim_review_rule(int(created["id"]))

        assert result is None
        assert db.get_claim_review_rule(int(created["id"])) == {}
    finally:
        db.close_connection()
