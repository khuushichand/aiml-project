from __future__ import annotations

import json
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_notification_ops import (
    get_claim_notification as helper_get_claim_notification,
    get_claim_notifications_by_ids as helper_get_claim_notifications_by_ids,
    get_latest_claim_notification as helper_get_latest_claim_notification,
    insert_claim_notification as helper_insert_claim_notification,
    list_claim_notifications as helper_list_claim_notifications,
    mark_claim_notifications_delivered as helper_mark_claim_notifications_delivered,
)


pytestmark = pytest.mark.unit


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-notification-helper")
    db.initialize_db()
    return db


def test_insert_claim_notification_returns_fresh_row_and_rebinds_canonical_method(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claim-notification-insert.db")
    try:
        assert db.insert_claim_notification.__func__ is helper_insert_claim_notification
        assert db.get_claim_notification.__func__ is helper_get_claim_notification

        row = db.insert_claim_notification(
            user_id="1",
            kind="review_update",
            target_user_id="2",
            target_review_group="moderators",
            resource_type="claim",
            resource_id="9",
            payload_json=json.dumps({"claim_id": 9}),
        )

        assert int(row["id"]) > 0
        assert row["user_id"] == "1"
        assert row["kind"] == "review_update"
        assert row["target_user_id"] == "2"
        assert row["target_review_group"] == "moderators"
        assert row["resource_type"] == "claim"
        assert row["resource_id"] == "9"
        assert row["payload_json"] == json.dumps({"claim_id": 9})
        assert row["delivered_at"] is None
    finally:
        db.close_connection()


def test_get_latest_claim_notification_honors_resource_filters(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claim-notification-latest.db")
    try:
        assert db.get_latest_claim_notification.__func__ is helper_get_latest_claim_notification

        db.insert_claim_notification(
            user_id="1",
            kind="watchlist_cluster_update",
            resource_type="cluster",
            resource_id="1",
            payload_json=json.dumps({"member_count": 1}),
        )
        db.insert_claim_notification(
            user_id="1",
            kind="watchlist_cluster_update",
            resource_type="cluster",
            resource_id="2",
            payload_json=json.dumps({"member_count": 2}),
        )
        db.insert_claim_notification(
            user_id="1",
            kind="watchlist_cluster_update",
            resource_type="cluster",
            resource_id="1",
            payload_json=json.dumps({"member_count": 3}),
        )

        latest = db.get_latest_claim_notification(
            user_id="1",
            kind="watchlist_cluster_update",
            resource_type="cluster",
            resource_id="1",
        )

        assert latest is not None
        assert latest["resource_id"] == "1"
        assert json.loads(latest["payload_json"])["member_count"] == 3
    finally:
        db.close_connection()


def test_list_claim_notifications_respects_delivered_filter_and_tolerant_paging(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claim-notification-list.db")
    try:
        assert db.list_claim_notifications.__func__ is helper_list_claim_notifications
        assert db.mark_claim_notifications_delivered.__func__ is helper_mark_claim_notifications_delivered

        first = db.insert_claim_notification(
            user_id="1",
            kind="review_assignment",
            payload_json="{}",
        )
        second = db.insert_claim_notification(
            user_id="1",
            kind="review_assignment",
            payload_json="{}",
        )
        db.mark_claim_notifications_delivered([int(first["id"])])

        undelivered = db.list_claim_notifications(
            user_id="1",
            kind="review_assignment",
            delivered=False,
            limit="bad",  # type: ignore[arg-type]
            offset="also-bad",  # type: ignore[arg-type]
        )
        delivered = db.list_claim_notifications(
            user_id="1",
            kind="review_assignment",
            delivered=True,
        )

        assert [int(row["id"]) for row in undelivered] == [int(second["id"])]
        assert [int(row["id"]) for row in delivered] == [int(first["id"])]
    finally:
        db.close_connection()


def test_get_claim_notifications_by_ids_and_mark_delivered_handle_empty_ids(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claim-notification-ids.db")
    try:
        assert db.get_claim_notifications_by_ids.__func__ is helper_get_claim_notifications_by_ids

        created = db.insert_claim_notification(
            user_id="1",
            kind="review_update",
            payload_json=json.dumps({"claim_id": 4}),
        )

        assert db.get_claim_notifications_by_ids([]) == []
        assert db.mark_claim_notifications_delivered([]) == 0

        updated = db.mark_claim_notifications_delivered([int(created["id"])])
        rows = db.get_claim_notifications_by_ids([int(created["id"])])

        assert updated == 1
        assert len(rows) == 1
        assert rows[0]["delivered_at"] is not None
    finally:
        db.close_connection()
