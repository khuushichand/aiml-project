from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase


pytestmark = pytest.mark.unit


def _load_retention_ops_module():
    return importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.email_retention_ops"
    )


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


def test_parse_email_retention_datetime_accepts_iso_and_rfc2822() -> None:
    retention_ops_module = _load_retention_ops_module()

    iso_value = retention_ops_module._parse_email_retention_datetime("2025-01-10T09:00:00Z")
    rfc_value = retention_ops_module._parse_email_retention_datetime(
        "Fri, 10 Jan 2025 09:00:00 +0000"
    )

    assert iso_value == datetime(2025, 1, 10, 9, 0, tzinfo=timezone.utc)
    assert rfc_value == datetime(2025, 1, 10, 9, 0, tzinfo=timezone.utc)


def test_cleanup_email_orphans_for_tenant_deletes_orphans_and_optional_empty_sources() -> None:
    retention_ops_module = _load_retention_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-retention-helper-cleanup-test")
    try:
        target_media_id = _add_email_media(
            db,
            url="email://cleanup-target",
            title="Cleanup Target",
            content="Cleanup target body",
        )
        target_upsert = db.upsert_email_message_graph(
            media_id=target_media_id,
            metadata={
                "title": "Cleanup Target",
                "email": {
                    "from": "cleanup-target@example.com",
                    "to": "cleanup-target-dest@example.com",
                    "subject": "Cleanup Target",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<cleanup-target@example.com>",
                    "labels": ["TARGET-LABEL"],
                },
            },
            body_text="Cleanup target body",
            source_message_id="cleanup-target-src",
            source_key="cleanup-target-source",
            provider="gmail",
            tenant_id="user:42",
        )

        other_media_id = _add_email_media(
            db,
            url="email://cleanup-other",
            title="Cleanup Other",
            content="Cleanup other body",
        )
        db.upsert_email_message_graph(
            media_id=other_media_id,
            metadata={
                "title": "Cleanup Other",
                "email": {
                    "from": "cleanup-other@example.com",
                    "to": "cleanup-other-dest@example.com",
                    "subject": "Cleanup Other",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<cleanup-other@example.com>",
                    "labels": ["OTHER-LABEL"],
                },
            },
            body_text="Cleanup other body",
            source_message_id="cleanup-other-src",
            source_key="cleanup-other-source",
            provider="gmail",
            tenant_id="user:84",
        )

        email_message_id = int(target_upsert["email_message_id"])
        db.execute_query(
            "DELETE FROM email_message_labels WHERE email_message_id = ?",
            (email_message_id,),
            commit=True,
        )
        db.execute_query(
            "DELETE FROM email_message_participants WHERE email_message_id = ?",
            (email_message_id,),
            commit=True,
        )
        db.execute_query(
            "DELETE FROM email_messages WHERE id = ?",
            (email_message_id,),
            commit=True,
        )

        conn = db.get_connection()
        result = retention_ops_module._cleanup_email_orphans_for_tenant(
            db,
            conn,
            tenant_id="user:42",
            delete_empty_sources=True,
        )

        assert result["labels_deleted"] >= 1
        assert result["participants_deleted"] >= 2
        assert result["sources_deleted"] == 1
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_labels WHERE tenant_id = ?",
            ("user:42",),
        ).fetchone()["total"] == 0
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_participants WHERE tenant_id = ?",
            ("user:42",),
        ).fetchone()["total"] == 0
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_sources WHERE tenant_id = ?",
            ("user:42",),
        ).fetchone()["total"] == 0
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_labels WHERE tenant_id = ?",
            ("user:84",),
        ).fetchone()["total"] == 1
    finally:
        db.close_connection()


def test_enforce_email_retention_policy_respects_limit_and_include_missing_internal_date() -> None:
    retention_ops_module = _load_retention_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-retention-helper-limit-test")
    try:
        now_utc = datetime.now(timezone.utc)
        old_date = format_datetime(now_utc - timedelta(days=160))
        recent_date = format_datetime(now_utc - timedelta(days=2))

        media_id_old = _add_email_media(
            db,
            url="email://retention-limit-old",
            title="Retention Limit Old",
            content="Old target body",
        )
        db.upsert_email_message_graph(
            media_id=media_id_old,
            metadata={
                "title": "Retention Limit Old",
                "email": {
                    "from": "old@example.com",
                    "to": "old-dest@example.com",
                    "subject": "Retention Limit Old",
                    "date": old_date,
                    "message_id": "<retention-limit-old@example.com>",
                    "labels": ["OLD-LABEL"],
                },
            },
            body_text="Old target body",
            source_message_id="retention-limit-old-src",
            source_key="retention-limit-source",
            provider="gmail",
            tenant_id="user:42",
        )

        media_id_missing = _add_email_media(
            db,
            url="email://retention-limit-missing",
            title="Retention Limit Missing",
            content="Missing date body",
        )
        db.upsert_email_message_graph(
            media_id=media_id_missing,
            metadata={
                "title": "Retention Limit Missing",
                "email": {
                    "from": "missing@example.com",
                    "to": "missing-dest@example.com",
                    "subject": "Retention Limit Missing",
                    "message_id": "<retention-limit-missing@example.com>",
                    "labels": ["MISSING-LABEL"],
                },
            },
            body_text="Missing date body",
            source_message_id="retention-limit-missing-src",
            source_key="retention-limit-source",
            provider="gmail",
            tenant_id="user:42",
        )

        media_id_recent = _add_email_media(
            db,
            url="email://retention-limit-recent",
            title="Retention Limit Recent",
            content="Recent body",
        )
        db.upsert_email_message_graph(
            media_id=media_id_recent,
            metadata={
                "title": "Retention Limit Recent",
                "email": {
                    "from": "recent@example.com",
                    "to": "recent-dest@example.com",
                    "subject": "Retention Limit Recent",
                    "date": recent_date,
                    "message_id": "<retention-limit-recent@example.com>",
                    "labels": ["RECENT-LABEL"],
                },
            },
            body_text="Recent body",
            source_message_id="retention-limit-recent-src",
            source_key="retention-limit-source",
            provider="gmail",
            tenant_id="user:42",
        )

        result = retention_ops_module.enforce_email_retention_policy(
            db,
            retention_days=30,
            tenant_id="user:42",
            hard_delete=False,
            include_missing_internal_date=True,
            limit=1,
        )

        assert result["candidate_media_count"] == 2
        assert result["candidate_media_count_after_limit"] == 1
        assert result["applied_count"] == 1
        deleted_count = sum(
            int(
                db.execute_query(
                    "SELECT deleted FROM Media WHERE id = ?",
                    (media_id,),
                ).fetchone()["deleted"]
            )
            for media_id in (media_id_old, media_id_missing)
        )
        assert deleted_count == 1
        assert int(
            db.execute_query(
                "SELECT deleted FROM Media WHERE id = ?",
                (media_id_recent,),
            ).fetchone()["deleted"]
        ) == 0
    finally:
        db.close_connection()


def test_hard_delete_email_tenant_data_preserves_tenant_scope_via_helper() -> None:
    retention_ops_module = _load_retention_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-retention-helper-hard-delete-test")
    try:
        base_date = format_datetime(datetime.now(timezone.utc) - timedelta(days=45))

        media_id_target = _add_email_media(
            db,
            url="email://retention-helper-hard-target",
            title="Hard Target",
            content="Hard target body",
        )
        db.upsert_email_message_graph(
            media_id=media_id_target,
            metadata={
                "title": "Hard Target",
                "email": {
                    "from": "hard-target@example.com",
                    "to": "hard-target-dest@example.com",
                    "subject": "Hard Target",
                    "date": base_date,
                    "message_id": "<hard-target@example.com>",
                    "labels": ["HARD-TARGET"],
                },
            },
            body_text="Hard target body",
            source_message_id="hard-target-src",
            source_key="hard-target-source",
            provider="gmail",
            tenant_id="user:42",
        )

        media_id_other = _add_email_media(
            db,
            url="email://retention-helper-hard-other",
            title="Hard Other",
            content="Hard other body",
        )
        db.upsert_email_message_graph(
            media_id=media_id_other,
            metadata={
                "title": "Hard Other",
                "email": {
                    "from": "hard-other@example.com",
                    "to": "hard-other-dest@example.com",
                    "subject": "Hard Other",
                    "date": base_date,
                    "message_id": "<hard-other@example.com>",
                    "labels": ["HARD-OTHER"],
                },
            },
            body_text="Hard other body",
            source_message_id="hard-other-src",
            source_key="hard-other-source",
            provider="gmail",
            tenant_id="user:84",
        )

        db.mark_email_sync_run_started(
            provider="gmail",
            source_key="hard-target-source",
            tenant_id="user:42",
        )
        db.mark_email_sync_run_started(
            provider="gmail",
            source_key="hard-other-source",
            tenant_id="user:84",
        )
        db.execute_query(
            "INSERT INTO email_backfill_state (tenant_id, backfill_key, status) VALUES (?, ?, ?)",
            ("user:42", "default", "idle"),
            commit=True,
        )
        db.execute_query(
            "INSERT INTO email_backfill_state (tenant_id, backfill_key, status) VALUES (?, ?, ?)",
            ("user:84", "default", "idle"),
            commit=True,
        )

        result = retention_ops_module.hard_delete_email_tenant_data(
            db,
            tenant_id="user:42",
        )

        assert result["tenant_id"] == "user:42"
        assert result["candidate_media_count"] == 1
        assert result["deleted_media_count"] == 1
        assert media_id_target in result["deleted_media_ids"]
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_messages WHERE tenant_id = ?",
            ("user:42",),
        ).fetchone()["total"] == 0
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_messages WHERE tenant_id = ?",
            ("user:84",),
        ).fetchone()["total"] == 1
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_sync_state WHERE tenant_id = ?",
            ("user:42",),
        ).fetchone()["total"] == 0
        assert db.execute_query(
            "SELECT COUNT(*) AS total FROM email_backfill_state WHERE tenant_id = ?",
            ("user:42",),
        ).fetchone()["total"] == 0
    finally:
        db.close_connection()
