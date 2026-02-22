from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import InputError, MediaDatabase


def _add_email_media(
    db: MediaDatabase,
    *,
    url: str,
    title: str,
    content: str,
    safe_metadata: dict | None = None,
) -> int:
    media_id, _media_uuid, _msg = db.add_media_with_keywords(
        url=url,
        title=title,
        media_type="email",
        content=content,
        keywords=["email"],
        author="tester@example.com",
        safe_metadata=json.dumps(safe_metadata) if isinstance(safe_metadata, dict) else None,
    )
    assert media_id is not None
    return int(media_id)


@pytest.mark.unit
def test_email_native_schema_bootstrap_sqlite() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-schema-test")
    try:
        table_rows = db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {str(row["name"]) for row in table_rows}
        expected_tables = {
            "email_sources",
            "email_messages",
            "email_participants",
            "email_message_participants",
            "email_labels",
            "email_message_labels",
            "email_attachments",
            "email_sync_state",
            "email_fts",
        }
        assert expected_tables.issubset(table_names)

        idx_rows = db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='email_messages'"
        ).fetchall()
        index_names = {str(row["name"]) for row in idx_rows}
        assert "idx_email_messages_tenant_source_message" in index_names
        assert "idx_email_messages_tenant_message_id" in index_names
    finally:
        db.close_connection()


@pytest.mark.unit
def test_upsert_email_message_graph_updates_existing_by_source_message_id() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-upsert-test")
    try:
        media_id = _add_email_media(
            db,
            url="email://message-1",
            title="Message 1",
            content="Initial body text",
        )
        metadata_v1 = {
            "title": "Monthly Invoice",
            "email": {
                "from": "Alice <alice@example.com>",
                "to": "Bob <bob@example.com>",
                "cc": "Team <team@example.com>",
                "subject": "Monthly Invoice",
                "date": "Mon, 13 Jan 2025 09:30:00 -0500",
                "message_id": "<msg-1@example.com>",
                "attachments": [
                    {
                        "name": "invoice.pdf",
                        "content_type": "application/pdf",
                        "size": 12345,
                        "content_id": "<cid-1>",
                    }
                ],
                "labels": ["Inbox", "Finance"],
            },
        }
        first = db.upsert_email_message_graph(
            media_id=media_id,
            metadata=metadata_v1,
            body_text="Initial body text",
            source_message_id="provider-msg-1",
            source_key="upload:test-message-1",
        )

        metadata_v2 = {
            "title": "Monthly Invoice Updated",
            "email": {
                "from": "Alice <alice@example.com>",
                "to": "Bob <bob@example.com>",
                "subject": "Monthly Invoice (Updated)",
                "date": "Mon, 13 Jan 2025 10:30:00 -0500",
                "message_id": "<msg-1-updated@example.com>",
                "attachments": [],
                "labels": ["Inbox"],
            },
        }
        second = db.upsert_email_message_graph(
            media_id=media_id,
            metadata=metadata_v2,
            body_text="Updated body text",
            source_message_id="provider-msg-1",
            source_key="upload:test-message-1",
        )

        assert int(first["email_message_id"]) == int(second["email_message_id"])
        assert second["match_strategy"] == "source_message_id"

        row = db.execute_query(
            "SELECT subject, message_id, has_attachments FROM email_messages WHERE id = ?",
            (int(second["email_message_id"]),),
        ).fetchone()
        assert row is not None
        assert row["subject"] == "Monthly Invoice (Updated)"
        assert row["message_id"] == "<msg-1-updated@example.com>"
        assert int(row["has_attachments"]) == 0

        participant_count_row = db.execute_query(
            "SELECT COUNT(*) AS total FROM email_message_participants WHERE email_message_id = ?",
            (int(second["email_message_id"]),),
        ).fetchone()
        assert int(participant_count_row["total"]) >= 2
    finally:
        db.close_connection()


@pytest.mark.unit
def test_email_sync_state_roundtrip_and_retry_reset() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-sync-state-test")
    try:
        assert (
            db.get_email_sync_state(
                provider="gmail",
                source_key="gmail-source-1",
                tenant_id="user:42",
            )
            is None
        )

        started = db.mark_email_sync_run_started(
            provider="gmail",
            source_key="gmail-source-1",
            tenant_id="user:42",
        )
        assert started["provider"] == "gmail"
        assert started["source_key"] == "gmail-source-1"
        assert started["cursor"] is None
        assert started["retry_backoff_count"] == 0
        assert started["last_run_at"] is not None

        failed = db.mark_email_sync_run_failed(
            provider="gmail",
            source_key="gmail-source-1",
            tenant_id="user:42",
            error_state="quota_limited",
        )
        assert failed["error_state"] == "quota_limited"
        assert failed["retry_backoff_count"] == 1
        assert failed["last_success_at"] is None

        succeeded = db.mark_email_sync_run_succeeded(
            provider="gmail",
            source_key="gmail-source-1",
            tenant_id="user:42",
            cursor="123456",
        )
        assert succeeded["cursor"] == "123456"
        assert succeeded["error_state"] is None
        assert succeeded["retry_backoff_count"] == 0
        assert succeeded["last_success_at"] is not None

        loaded = db.get_email_sync_state(
            provider="gmail",
            source_key="gmail-source-1",
            tenant_id="user:42",
        )
        assert loaded is not None
        assert loaded["source_id"] == succeeded["source_id"]
        assert loaded["cursor"] == "123456"
        assert loaded["error_state"] is None
    finally:
        db.close_connection()


@pytest.mark.unit
def test_apply_email_label_delta_updates_label_mappings() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-label-delta-test")
    try:
        media_id = _add_email_media(
            db,
            url="email://label-delta-1",
            title="Label Delta Email",
            content="Label delta body",
        )
        upsert_result = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Label Delta Subject",
                "email": {
                    "from": "alice@example.com",
                    "to": "bob@example.com",
                    "subject": "Label Delta Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<label-delta@example.com>",
                    "labels": ["INBOX", "UNREAD"],
                },
            },
            body_text="Label delta body",
            source_message_id="gmail-m1",
            source_key="gmail-source-1",
            provider="gmail",
            tenant_id="user:42",
        )

        result = db.apply_email_label_delta(
            provider="gmail",
            source_key="gmail-source-1",
            source_message_id="gmail-m1",
            labels_added=["STARRED"],
            labels_removed=["UNREAD"],
            tenant_id="user:42",
        )
        assert result["applied"] is True
        assert sorted(result["labels"]) == ["INBOX", "STARRED"]

        detail = db.get_email_message_detail(
            email_message_id=int(upsert_result["email_message_id"]),
            tenant_id="user:42",
        )
        assert detail is not None
        label_names = [str(item["label_name"]) for item in detail["labels"]]
        assert label_names == ["INBOX", "STARRED"]
        assert detail["search_text"]["labels"] == "INBOX, STARRED"
    finally:
        db.close_connection()


@pytest.mark.unit
def test_reconcile_email_message_state_deletes_message_media() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-state-reconcile-test")
    try:
        media_id = _add_email_media(
            db,
            url="email://state-reconcile-1",
            title="State Reconcile Email",
            content="State reconcile body",
        )
        upsert_result = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "State Reconcile Subject",
                "email": {
                    "from": "alice@example.com",
                    "to": "bob@example.com",
                    "subject": "State Reconcile Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<state-reconcile@example.com>",
                    "labels": ["INBOX"],
                },
            },
            body_text="State reconcile body",
            source_message_id="gmail-m-delete",
            source_key="gmail-source-2",
            provider="gmail",
            tenant_id="user:42",
        )
        email_message_id = int(upsert_result["email_message_id"])

        result = db.reconcile_email_message_state(
            provider="gmail",
            source_key="gmail-source-2",
            source_message_id="gmail-m-delete",
            tenant_id="user:42",
            deleted=True,
        )
        assert result["applied"] is True
        assert result["reason"] == "deleted"

        # Default detail path should hide soft-deleted media-backed messages.
        assert db.get_email_message_detail(
            email_message_id=email_message_id,
            tenant_id="user:42",
        ) is None

        detail_including_deleted = db.get_email_message_detail(
            email_message_id=email_message_id,
            tenant_id="user:42",
            include_deleted=True,
        )
        assert detail_including_deleted is not None

        # Re-applying delete state is idempotent.
        second = db.reconcile_email_message_state(
            provider="gmail",
            source_key="gmail-source-2",
            source_message_id="gmail-m-delete",
            tenant_id="user:42",
            deleted=True,
        )
        assert second["applied"] is False
        assert second["reason"] == "already_deleted"
    finally:
        db.close_connection()


@pytest.mark.unit
def test_enforce_email_retention_policy_soft_delete_scoped_to_tenant() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-retention-soft-test")
    try:
        now_utc = datetime.now(timezone.utc)
        old_date = format_datetime(now_utc - timedelta(days=120))
        recent_date = format_datetime(now_utc - timedelta(days=5))

        media_id_tenant_a_old = _add_email_media(
            db,
            url="email://retention-soft-a-old",
            title="Tenant A Old",
            content="Old message for tenant A",
        )
        upsert_a_old = db.upsert_email_message_graph(
            media_id=media_id_tenant_a_old,
            metadata={
                "title": "Tenant A Old",
                "email": {
                    "from": "old-a@example.com",
                    "to": "ops-a@example.com",
                    "subject": "Tenant A Old",
                    "date": old_date,
                    "message_id": "<tenant-a-old@example.com>",
                    "labels": ["RETENTION-A-OLD"],
                },
            },
            body_text="Old message for tenant A",
            source_message_id="tenant-a-old-src",
            source_key="gmail-tenant-a",
            provider="gmail",
            tenant_id="user:42",
        )

        media_id_tenant_a_recent = _add_email_media(
            db,
            url="email://retention-soft-a-recent",
            title="Tenant A Recent",
            content="Recent message for tenant A",
        )
        db.upsert_email_message_graph(
            media_id=media_id_tenant_a_recent,
            metadata={
                "title": "Tenant A Recent",
                "email": {
                    "from": "recent-a@example.com",
                    "to": "ops-a@example.com",
                    "subject": "Tenant A Recent",
                    "date": recent_date,
                    "message_id": "<tenant-a-recent@example.com>",
                    "labels": ["RETENTION-A-RECENT"],
                },
            },
            body_text="Recent message for tenant A",
            source_message_id="tenant-a-recent-src",
            source_key="gmail-tenant-a",
            provider="gmail",
            tenant_id="user:42",
        )

        media_id_tenant_b_old = _add_email_media(
            db,
            url="email://retention-soft-b-old",
            title="Tenant B Old",
            content="Old message for tenant B",
        )
        db.upsert_email_message_graph(
            media_id=media_id_tenant_b_old,
            metadata={
                "title": "Tenant B Old",
                "email": {
                    "from": "old-b@example.com",
                    "to": "ops-b@example.com",
                    "subject": "Tenant B Old",
                    "date": old_date,
                    "message_id": "<tenant-b-old@example.com>",
                    "labels": ["RETENTION-B-OLD"],
                },
            },
            body_text="Old message for tenant B",
            source_message_id="tenant-b-old-src",
            source_key="gmail-tenant-b",
            provider="gmail",
            tenant_id="user:84",
        )

        outcome = db.enforce_email_retention_policy(
            retention_days=30,
            tenant_id="user:42",
            hard_delete=False,
        )
        assert outcome["tenant_id"] == "user:42"
        assert outcome["retention_days"] == 30
        assert outcome["hard_delete"] is False
        assert outcome["applied_count"] == 1
        assert outcome["failed_media_ids"] == []
        assert media_id_tenant_a_old in outcome["applied_media_ids"]

        media_deleted_row = db.execute_query(
            "SELECT deleted FROM Media WHERE id = ?",
            (media_id_tenant_a_old,),
        ).fetchone()
        assert media_deleted_row is not None
        assert int(media_deleted_row["deleted"]) == 1

        media_recent_row = db.execute_query(
            "SELECT deleted FROM Media WHERE id = ?",
            (media_id_tenant_a_recent,),
        ).fetchone()
        assert media_recent_row is not None
        assert int(media_recent_row["deleted"]) == 0

        media_other_tenant_row = db.execute_query(
            "SELECT deleted FROM Media WHERE id = ?",
            (media_id_tenant_b_old,),
        ).fetchone()
        assert media_other_tenant_row is not None
        assert int(media_other_tenant_row["deleted"]) == 0

        # Default detail path hides soft-deleted message.
        assert db.get_email_message_detail(
            email_message_id=int(upsert_a_old["email_message_id"]),
            tenant_id="user:42",
        ) is None
        # Include-deleted path still surfaces the record.
        assert db.get_email_message_detail(
            email_message_id=int(upsert_a_old["email_message_id"]),
            tenant_id="user:42",
            include_deleted=True,
        ) is not None
    finally:
        db.close_connection()


@pytest.mark.unit
def test_enforce_email_retention_policy_hard_delete_removes_orphans() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-retention-hard-test")
    try:
        now_utc = datetime.now(timezone.utc)
        old_date = format_datetime(now_utc - timedelta(days=160))
        recent_date = format_datetime(now_utc - timedelta(days=2))

        media_id_old = _add_email_media(
            db,
            url="email://retention-hard-old",
            title="Retention Hard Old",
            content="Hard-delete old message",
        )
        db.upsert_email_message_graph(
            media_id=media_id_old,
            metadata={
                "title": "Retention Hard Old",
                "email": {
                    "from": "hard-old@example.com",
                    "to": "hard-old-dest@example.com",
                    "subject": "Retention Hard Old",
                    "date": old_date,
                    "message_id": "<retention-hard-old@example.com>",
                    "labels": ["RETENTION-HARD-OLD"],
                },
            },
            body_text="Hard-delete old message",
            source_message_id="retention-hard-old-src",
            source_key="gmail-tenant-hard",
            provider="gmail",
            tenant_id="user:42",
        )

        media_id_recent = _add_email_media(
            db,
            url="email://retention-hard-recent",
            title="Retention Hard Recent",
            content="Keep recent message",
        )
        db.upsert_email_message_graph(
            media_id=media_id_recent,
            metadata={
                "title": "Retention Hard Recent",
                "email": {
                    "from": "hard-recent@example.com",
                    "to": "hard-recent-dest@example.com",
                    "subject": "Retention Hard Recent",
                    "date": recent_date,
                    "message_id": "<retention-hard-recent@example.com>",
                    "labels": ["RETENTION-HARD-RECENT"],
                },
            },
            body_text="Keep recent message",
            source_message_id="retention-hard-recent-src",
            source_key="gmail-tenant-hard",
            provider="gmail",
            tenant_id="user:42",
        )

        outcome = db.enforce_email_retention_policy(
            retention_days=30,
            tenant_id="user:42",
            hard_delete=True,
        )
        assert outcome["applied_count"] == 1
        assert outcome["failed_media_ids"] == []
        assert media_id_old in outcome["applied_media_ids"]

        # Hard-delete removes both Media and normalized message row.
        old_media_row = db.execute_query(
            "SELECT id FROM Media WHERE id = ?",
            (media_id_old,),
        ).fetchone()
        assert old_media_row is None
        old_message_row = db.execute_query(
            "SELECT id FROM email_messages WHERE media_id = ?",
            (media_id_old,),
        ).fetchone()
        assert old_message_row is None

        # Recent record remains.
        recent_media_row = db.execute_query(
            "SELECT id FROM Media WHERE id = ?",
            (media_id_recent,),
        ).fetchone()
        assert recent_media_row is not None
        recent_message_row = db.execute_query(
            "SELECT id FROM email_messages WHERE media_id = ?",
            (media_id_recent,),
        ).fetchone()
        assert recent_message_row is not None

        # Old unique label/participants are orphaned and removed by cleanup.
        orphan_label_row = db.execute_query(
            "SELECT id FROM email_labels WHERE tenant_id = ? AND label_key = ?",
            ("user:42", "retention-hard-old"),
        ).fetchone()
        assert orphan_label_row is None
        orphan_participant_row = db.execute_query(
            "SELECT id FROM email_participants WHERE tenant_id = ? AND email_normalized = ?",
            ("user:42", "hard-old@example.com"),
        ).fetchone()
        assert orphan_participant_row is None
    finally:
        db.close_connection()


@pytest.mark.unit
def test_hard_delete_email_tenant_data_scoped_to_target_tenant() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-hard-delete-tenant-test")
    try:
        base_date = format_datetime(datetime.now(timezone.utc) - timedelta(days=45))

        media_id_tenant_a = _add_email_media(
            db,
            url="email://tenant-hard-delete-a",
            title="Tenant A Message",
            content="Tenant A message body",
        )
        db.upsert_email_message_graph(
            media_id=media_id_tenant_a,
            metadata={
                "title": "Tenant A Message",
                "email": {
                    "from": "tenant-a@example.com",
                    "to": "ops-a@example.com",
                    "subject": "Tenant A Message",
                    "date": base_date,
                    "message_id": "<tenant-a-hard-delete@example.com>",
                    "labels": ["TENANT-A-LABEL"],
                },
            },
            body_text="Tenant A message body",
            source_message_id="tenant-a-hard-delete-src",
            source_key="gmail-tenant-a-hard-delete",
            provider="gmail",
            tenant_id="user:42",
        )

        media_id_tenant_b = _add_email_media(
            db,
            url="email://tenant-hard-delete-b",
            title="Tenant B Message",
            content="Tenant B message body",
        )
        db.upsert_email_message_graph(
            media_id=media_id_tenant_b,
            metadata={
                "title": "Tenant B Message",
                "email": {
                    "from": "tenant-b@example.com",
                    "to": "ops-b@example.com",
                    "subject": "Tenant B Message",
                    "date": base_date,
                    "message_id": "<tenant-b-hard-delete@example.com>",
                    "labels": ["TENANT-B-LABEL"],
                },
            },
            body_text="Tenant B message body",
            source_message_id="tenant-b-hard-delete-src",
            source_key="gmail-tenant-b-hard-delete",
            provider="gmail",
            tenant_id="user:84",
        )

        db.mark_email_sync_run_started(
            provider="gmail",
            source_key="gmail-tenant-a-hard-delete",
            tenant_id="user:42",
        )
        db.mark_email_sync_run_started(
            provider="gmail",
            source_key="gmail-tenant-b-hard-delete",
            tenant_id="user:84",
        )
        db.execute_query(
            (
                "INSERT INTO email_backfill_state "
                "(tenant_id, backfill_key, status) "
                "VALUES (?, ?, ?)"
            ),
            ("user:42", "default", "idle"),
            commit=True,
        )
        db.execute_query(
            (
                "INSERT INTO email_backfill_state "
                "(tenant_id, backfill_key, status) "
                "VALUES (?, ?, ?)"
            ),
            ("user:84", "default", "idle"),
            commit=True,
        )

        outcome = db.hard_delete_email_tenant_data(tenant_id="user:42")
        assert outcome["tenant_id"] == "user:42"
        assert outcome["candidate_media_count"] == 1
        assert outcome["deleted_media_count"] == 1
        assert outcome["failed_media_ids"] == []
        assert media_id_tenant_a in outcome["deleted_media_ids"]

        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_messages WHERE tenant_id = ?",
            ("user:42",),
        ).fetchone()["total"] == 0
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_sources WHERE tenant_id = ?",
            ("user:42",),
        ).fetchone()["total"] == 0
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_sync_state WHERE tenant_id = ?",
            ("user:42",),
        ).fetchone()["total"] == 0
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_backfill_state WHERE tenant_id = ?",
            ("user:42",),
        ).fetchone()["total"] == 0
        assert db.execute_query(
            "SELECT id FROM Media WHERE id = ?",
            (media_id_tenant_a,),
        ).fetchone() is None

        # Other tenant remains untouched.
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_messages WHERE tenant_id = ?",
            ("user:84",),
        ).fetchone()["total"] == 1
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_sources WHERE tenant_id = ?",
            ("user:84",),
        ).fetchone()["total"] >= 1
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_sync_state WHERE tenant_id = ?",
            ("user:84",),
        ).fetchone()["total"] == 1
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_backfill_state WHERE tenant_id = ?",
            ("user:84",),
        ).fetchone()["total"] == 1
        assert db.execute_query(
            "SELECT id FROM Media WHERE id = ?",
            (media_id_tenant_b,),
        ).fetchone() is not None
    finally:
        db.close_connection()


@pytest.mark.unit
def test_enforce_email_retention_policy_rejects_negative_days() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-retention-invalid-test")
    try:
        with pytest.raises(InputError):
            db.enforce_email_retention_policy(retention_days=-1, tenant_id="user:42")
    finally:
        db.close_connection()


@pytest.mark.unit
def test_search_email_messages_operator_filters() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-search-test")
    try:
        media_id_1 = _add_email_media(
            db,
            url="email://search-1",
            title="Search Email 1",
            content="Budget planning thread for Q1",
        )
        db.upsert_email_message_graph(
            media_id=media_id_1,
            metadata={
                "title": "Budget Q1",
                "email": {
                    "from": "alice@example.com",
                    "to": "finance@example.com",
                    "subject": "Budget Q1",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<budget-q1@example.com>",
                    "attachments": [{"name": "budget.xlsx", "size": 1000}],
                    "labels": ["Inbox", "Finance"],
                },
            },
            body_text="Budget planning thread for Q1",
            source_message_id="src-search-1",
            source_key="upload:search-1",
        )

        media_id_2 = _add_email_media(
            db,
            url="email://search-2",
            title="Search Email 2",
            content="Team meeting notes",
        )
        db.upsert_email_message_graph(
            media_id=media_id_2,
            metadata={
                "title": "Team Meeting",
                "email": {
                    "from": "carol@example.com",
                    "to": "team@example.com",
                    "subject": "Team Meeting",
                    "date": "Mon, 10 Feb 2025 12:00:00 +0000",
                    "message_id": "<team-meeting@example.com>",
                    "attachments": [],
                    "labels": ["Work"],
                },
            },
            body_text="Team meeting notes",
            source_message_id="src-search-2",
            source_key="upload:search-2",
        )

        rows, total = db.search_email_messages(
            query="from:alice@example.com label:finance has:attachment"
        )
        assert total == 1
        assert len(rows) == 1
        assert rows[0]["media_id"] == media_id_1

        rows_after, total_after = db.search_email_messages(query="after:2025-02-01")
        assert total_after == 1
        assert rows_after[0]["media_id"] == media_id_2

        rows_or, total_or = db.search_email_messages(query="budget OR meeting")
        assert total_or == 2
        assert len(rows_or) == 2

        rows_neg, total_neg = db.search_email_messages(query="-label:work")
        assert total_neg == 1
        assert rows_neg[0]["media_id"] == media_id_1

        with pytest.raises(InputError):
            db.search_email_messages(query="(budget)")
    finally:
        db.close_connection()


@pytest.mark.unit
def test_search_email_messages_unknown_operator_like_token_does_not_raise() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-search-unknown-operator-test")
    try:
        media_id = _add_email_media(
            db,
            url="email://search-unknown-operator",
            title="Unknown Operator Email",
            content="Contains foo:bar token",
        )
        db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "foo:bar token in subject",
                "email": {
                    "from": "alice@example.com",
                    "to": "team@example.com",
                    "subject": "foo:bar token in subject",
                    "date": "Tue, 11 Feb 2025 12:00:00 +0000",
                    "message_id": "<unknown-op@example.com>",
                    "labels": ["Inbox"],
                },
            },
            body_text="Contains foo:bar token in body",
            source_message_id="src-unknown-op",
            source_key="upload:unknown-op",
        )

        rows, total = db.search_email_messages(query="foo:bar")
        assert total == 1
        assert len(rows) == 1
        assert int(rows[0]["media_id"]) == media_id
    finally:
        db.close_connection()


@pytest.mark.unit
def test_email_search_m3_indexes_exist_on_sqlite() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-m3-indexes-test")
    try:
        rows = db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = {str(row["name"]) for row in rows}
        assert "idx_email_messages_tenant_date_id" in index_names
        assert "idx_email_messages_tenant_has_attachments_date" in index_names
        assert "idx_email_message_participants_message_role" in index_names
    finally:
        db.close_connection()


@pytest.mark.unit
def test_get_email_message_detail_returns_normalized_graph() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-detail-test")
    try:
        media_id = _add_email_media(
            db,
            url="email://detail-1",
            title="Detail Email",
            content="Detailed message body",
        )
        upsert_result = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Detail Subject",
                "email": {
                    "from": "Alice <alice@example.com>",
                    "to": "Bob <bob@example.com>",
                    "cc": "Carol <carol@example.com>",
                    "subject": "Detail Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<detail@example.com>",
                    "attachments": [
                        {
                            "name": "detail.pdf",
                            "content_type": "application/pdf",
                            "size": 2000,
                            "content_id": "<cid-detail>",
                            "disposition": "attachment",
                        }
                    ],
                    "labels": ["Inbox", "Finance"],
                },
            },
            body_text="Detailed message body",
            source_message_id="detail-src-1",
            source_key="upload:detail-1",
        )

        detail = db.get_email_message_detail(
            email_message_id=int(upsert_result["email_message_id"])
        )

        assert detail is not None
        assert detail["media"]["id"] == media_id
        assert detail["subject"] == "Detail Subject"
        assert detail["participants"]["from"][0]["email"] == "alice@example.com"
        assert detail["participants"]["to"][0]["email"] == "bob@example.com"
        assert len(detail["labels"]) == 2
        assert detail["attachments"][0]["filename"] == "detail.pdf"
    finally:
        db.close_connection()


@pytest.mark.unit
def test_search_email_messages_excludes_deleted_and_trashed_media_by_default() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-search-deleted-media-test")
    try:
        media_id_live = _add_email_media(
            db,
            url="email://search-visible",
            title="Visible Email",
            content="Visible body",
        )
        db.upsert_email_message_graph(
            media_id=media_id_live,
            metadata={
                "title": "Visible Subject",
                "email": {
                    "from": "visible@example.com",
                    "to": "team@example.com",
                    "subject": "Visibility Check",
                    "date": "Mon, 10 Feb 2025 12:00:00 +0000",
                    "message_id": "<visible@example.com>",
                    "labels": ["Inbox"],
                },
            },
            body_text="Visible body",
            source_message_id="src-visible",
            source_key="upload:visible",
        )

        media_id_deleted = _add_email_media(
            db,
            url="email://search-deleted",
            title="Deleted Email",
            content="Deleted body",
        )
        db.upsert_email_message_graph(
            media_id=media_id_deleted,
            metadata={
                "title": "Deleted Subject",
                "email": {
                    "from": "deleted@example.com",
                    "to": "team@example.com",
                    "subject": "Visibility Check",
                    "date": "Tue, 11 Feb 2025 12:00:00 +0000",
                    "message_id": "<deleted@example.com>",
                    "labels": ["Inbox"],
                },
            },
            body_text="Deleted body",
            source_message_id="src-deleted",
            source_key="upload:deleted",
        )
        assert db.soft_delete_media(media_id_deleted, cascade=True) is True

        media_id_trashed = _add_email_media(
            db,
            url="email://search-trashed",
            title="Trashed Email",
            content="Trashed body",
        )
        db.upsert_email_message_graph(
            media_id=media_id_trashed,
            metadata={
                "title": "Trashed Subject",
                "email": {
                    "from": "trashed@example.com",
                    "to": "team@example.com",
                    "subject": "Visibility Check",
                    "date": "Wed, 12 Feb 2025 12:00:00 +0000",
                    "message_id": "<trashed@example.com>",
                    "labels": ["Inbox"],
                },
            },
            body_text="Trashed body",
            source_message_id="src-trashed",
            source_key="upload:trashed",
        )
        assert db.mark_as_trash(media_id_trashed) is True

        rows, total = db.search_email_messages(query="subject:visibility")
        row_media_ids = {int(row["media_id"]) for row in rows}
        assert total == 1
        assert row_media_ids == {media_id_live}

        rows_all, total_all = db.search_email_messages(
            query="subject:visibility",
            include_deleted=True,
        )
        row_media_ids_all = {int(row["media_id"]) for row in rows_all}
        assert total_all == 3
        assert row_media_ids_all == {media_id_live, media_id_deleted, media_id_trashed}
    finally:
        db.close_connection()


@pytest.mark.unit
def test_ensure_sqlite_email_schema_rebuilds_only_when_fts_is_created() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-fts-rebuild-gating-test")
    try:
        conn = db.get_connection()
        conn.execute("DROP TABLE IF EXISTS email_fts")
        conn.commit()

        statements: list[str] = []
        conn.set_trace_callback(statements.append)
        db._ensure_sqlite_email_schema(conn)
        db._ensure_sqlite_email_schema(conn)
        conn.set_trace_callback(None)

        rebuild_statements = [
            stmt
            for stmt in statements
            if "insert into email_fts(email_fts) values ('rebuild')" in stmt.lower()
        ]
        assert len(rebuild_statements) == 1
    finally:
        db.close_connection()


@pytest.mark.unit
def test_get_email_message_detail_returns_none_for_soft_deleted_media_by_default() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-detail-deleted-media-test")
    try:
        media_id = _add_email_media(
            db,
            url="email://detail-deleted",
            title="Deleted Detail Email",
            content="Detailed message body",
        )
        upsert_result = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Deleted Detail Subject",
                "email": {
                    "from": "alice@example.com",
                    "to": "bob@example.com",
                    "subject": "Deleted Detail Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<detail-deleted@example.com>",
                    "labels": ["Inbox"],
                },
            },
            body_text="Detailed message body",
            source_message_id="detail-deleted-src-1",
            source_key="upload:detail-deleted",
        )
        email_message_id = int(upsert_result["email_message_id"])

        assert db.soft_delete_media(media_id, cascade=True) is True

        assert db.get_email_message_detail(email_message_id=email_message_id) is None

        detail_including_deleted = db.get_email_message_detail(
            email_message_id=email_message_id,
            include_deleted=True,
        )
        assert detail_including_deleted is not None
        assert int(detail_including_deleted["media"]["id"]) == media_id
    finally:
        db.close_connection()


@pytest.mark.unit
def test_email_legacy_backfill_batch_is_resumable_and_idempotent() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-backfill-resume-test")
    try:
        for idx in range(1, 6):
            _add_email_media(
                db,
                url=f"email://legacy-backfill-{idx}",
                title=f"Legacy Subject {idx}",
                content=f"Legacy body {idx}",
                safe_metadata={
                    "email": {
                        "from": "legacy.sender@example.com",
                        "to": "legacy.receiver@example.com",
                        "subject": f"Legacy Subject {idx}",
                        "source_message_id": f"legacy-msg-{idx}",
                        "labels": ["Legacy", "Inbox"],
                    },
                    "source_key": "legacy-archive",
                    "provider": "upload",
                },
            )

        first = db.run_email_legacy_backfill_batch(batch_size=2, backfill_key="legacy-test")
        assert first["completed"] is False
        assert first["scanned"] == 2
        assert first["ingested"] == 2
        assert first["failed"] == 0
        assert int(first["state"]["last_media_id"]) > 0
        assert first["state"]["status"] == "running"

        second = db.run_email_legacy_backfill_batch(batch_size=2, backfill_key="legacy-test")
        assert second["completed"] is False
        assert second["scanned"] == 2
        assert second["ingested"] == 2
        assert second["failed"] == 0

        third = db.run_email_legacy_backfill_batch(batch_size=2, backfill_key="legacy-test")
        assert third["completed"] is True
        assert third["scanned"] == 1
        assert third["ingested"] == 1
        assert third["failed"] == 0
        assert third["status"] == "completed"

        total_messages_row = db.execute_query(
            "SELECT COUNT(*) AS total FROM email_messages"
        ).fetchone()
        assert int(total_messages_row["total"]) == 5

        # Idempotence: rerun after completion should not duplicate.
        rerun = db.run_email_legacy_backfill_batch(batch_size=10, backfill_key="legacy-test")
        assert rerun["completed"] is True
        assert rerun["scanned"] == 0
        assert rerun["ingested"] == 0
        assert rerun["status"] == "completed"

        state = db.get_email_legacy_backfill_state(backfill_key="legacy-test")
        assert state is not None
        assert int(state["processed_count"]) == 5
        assert int(state["success_count"]) == 5
        assert int(state["skipped_count"]) == 0
        assert int(state["failed_count"]) == 0

        total_messages_after = db.execute_query(
            "SELECT COUNT(*) AS total FROM email_messages"
        ).fetchone()
        assert int(total_messages_after["total"]) == 5
    finally:
        db.close_connection()


@pytest.mark.unit
def test_email_legacy_backfill_worker_handles_preexisting_rows_and_completes() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-backfill-worker-test")
    try:
        preexisting_media_id = _add_email_media(
            db,
            url="email://legacy-preexisting",
            title="Preexisting Subject",
            content="Preexisting body",
            safe_metadata={
                "email": {
                    "from": "alice@example.com",
                    "to": "bob@example.com",
                    "subject": "Preexisting Subject",
                    "source_message_id": "legacy-preexisting-msg",
                },
                "source_key": "legacy-import",
            },
        )
        db.upsert_email_message_graph(
            media_id=preexisting_media_id,
            metadata={
                "email": {
                    "from": "alice@example.com",
                    "to": "bob@example.com",
                    "subject": "Preexisting Subject",
                    "source_message_id": "legacy-preexisting-msg",
                    "labels": ["Inbox"],
                }
            },
            body_text="Preexisting body",
            source_key="legacy-import",
            source_message_id="legacy-preexisting-msg",
        )

        for idx in range(1, 4):
            _add_email_media(
                db,
                url=f"email://legacy-worker-{idx}",
                title=f"Worker Subject {idx}",
                content=f"Worker body {idx}",
                safe_metadata={
                    "email": {
                        "from": "worker.sender@example.com",
                        "to": "worker.receiver@example.com",
                        "subject": f"Worker Subject {idx}",
                        "source_message_id": f"legacy-worker-msg-{idx}",
                    },
                    "source_key": "legacy-import",
                },
            )

        result = db.run_email_legacy_backfill_worker(
            batch_size=2,
            backfill_key="legacy-worker",
            max_batches=5,
        )
        assert result["completed"] is True
        assert result["stop_reason"] == "completed"
        assert int(result["batches_run"]) >= 2
        assert int(result["ingested"]) == 3
        assert int(result["skipped"]) == 1
        assert int(result["failed"]) == 0

        final_state = result.get("state") or {}
        assert int(final_state.get("processed_count") or 0) == 4
        assert int(final_state.get("success_count") or 0) == 3
        assert int(final_state.get("skipped_count") or 0) == 1
        assert int(final_state.get("failed_count") or 0) == 0
        assert final_state.get("status") == "completed"

        total_messages_row = db.execute_query(
            "SELECT COUNT(*) AS total FROM email_messages"
        ).fetchone()
        assert int(total_messages_row["total"]) == 4
    finally:
        db.close_connection()
