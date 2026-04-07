from __future__ import annotations

import importlib
import json

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase


pytestmark = pytest.mark.unit


def _load_mutation_ops_module():
    return importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.email_message_mutation_ops"
    )


def _add_email_media(
    db: MediaDatabase,
    *,
    url: str,
    title: str,
    content: str,
) -> int:
    media_id, _media_uuid, _msg = db.add_media_with_keywords(
        url=url,
        title=title,
        media_type="email",
        content=content,
        keywords=["email"],
        author="tester@example.com",
    )
    assert media_id is not None
    return int(media_id)


def test_normalize_email_label_values_dedupes_case_insensitively() -> None:
    mutation_ops_module = _load_mutation_ops_module()

    assert mutation_ops_module._normalize_email_label_values(
        [" Inbox ", "", "inbox", "STARRED", None]
    ) == {"inbox": "Inbox", "starred": "STARRED"}


def test_resolve_email_message_row_for_source_message_returns_row_when_present() -> None:
    mutation_ops_module = _load_mutation_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-mutation-helper-row-test")
    try:
        media_id = _add_email_media(
            db,
            url="email://mutation-row-1",
            title="Mutation Row Email",
            content="Mutation row body",
        )
        upsert_result = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Mutation Row Subject",
                "email": {
                    "from": "alice@example.com",
                    "to": "bob@example.com",
                    "subject": "Mutation Row Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<mutation-row@example.com>",
                    "labels": ["INBOX"],
                },
            },
            body_text="Mutation row body",
            source_message_id="gmail-m-row",
            source_key="gmail-source-row",
            provider="gmail",
            tenant_id="user:42",
        )

        source_row = db.execute_query(
            (
                "SELECT id FROM email_sources "
                "WHERE tenant_id = ? AND provider = ? AND source_key = ? "
                "LIMIT 1"
            ),
            ("user:42", "gmail", "gmail-source-row"),
        ).fetchone()
        assert source_row is not None

        conn = db.get_connection()
        resolved = mutation_ops_module._resolve_email_message_row_for_source_message(
            db,
            conn,
            tenant_id="user:42",
            source_id=int(source_row["id"]),
            source_message_id="gmail-m-row",
        )
        missing = mutation_ops_module._resolve_email_message_row_for_source_message(
            db,
            conn,
            tenant_id="user:42",
            source_id=int(source_row["id"]),
            source_message_id="gmail-m-missing",
        )

        assert resolved is not None
        assert int(resolved["id"]) == int(upsert_result["email_message_id"])
        assert int(resolved["media_id"]) == media_id
        assert missing is None
    finally:
        db.close_connection()


def test_apply_email_label_delta_preserves_empty_and_contradictory_deltas() -> None:
    mutation_ops_module = _load_mutation_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-mutation-helper-empty-test")
    try:
        empty = mutation_ops_module.apply_email_label_delta(
            db,
            provider="gmail",
            source_key="gmail-source-empty",
            source_message_id="gmail-m-empty",
            tenant_id="user:42",
            labels_added=None,
            labels_removed=None,
        )
        assert empty["applied"] is False
        assert empty["reason"] == "empty_delta"

        media_id = _add_email_media(
            db,
            url="email://mutation-empty-overlap",
            title="Mutation Overlap Email",
            content="Mutation overlap body",
        )
        upsert_result = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Mutation Overlap Subject",
                "email": {
                    "from": "alice@example.com",
                    "to": "bob@example.com",
                    "subject": "Mutation Overlap Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<mutation-overlap@example.com>",
                    "labels": ["INBOX", "UNREAD"],
                },
            },
            body_text="Mutation overlap body",
            source_message_id="gmail-m-overlap",
            source_key="gmail-source-overlap",
            provider="gmail",
            tenant_id="user:42",
        )

        overlapped = mutation_ops_module.apply_email_label_delta(
            db,
            provider="gmail",
            source_key="gmail-source-overlap",
            source_message_id="gmail-m-overlap",
            tenant_id="user:42",
            labels_added=["STARRED"],
            labels_removed=["starred"],
        )
        detail = db.get_email_message_detail(
            email_message_id=int(upsert_result["email_message_id"]),
            tenant_id="user:42",
        )

        assert overlapped["applied"] is False
        assert overlapped["reason"] == "ok"
        assert overlapped["labels"] == ["INBOX", "UNREAD"]
        assert detail is not None
        assert detail["search_text"]["labels"] == "INBOX, UNREAD"
    finally:
        db.close_connection()


def test_apply_email_label_delta_updates_labels_metadata_and_sqlite_fts() -> None:
    mutation_ops_module = _load_mutation_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-mutation-helper-apply-test")
    try:
        media_id = _add_email_media(
            db,
            url="email://mutation-apply-1",
            title="Mutation Apply Email",
            content="Mutation apply body",
        )
        upsert_result = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Mutation Apply Subject",
                "email": {
                    "from": "alice@example.com",
                    "to": "bob@example.com",
                    "subject": "Mutation Apply Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<mutation-apply@example.com>",
                    "labels": ["INBOX", "UNREAD"],
                },
            },
            body_text="Mutation apply body",
            source_message_id="gmail-m-apply",
            source_key="gmail-source-apply",
            provider="gmail",
            tenant_id="user:42",
        )

        result = mutation_ops_module.apply_email_label_delta(
            db,
            provider="gmail",
            source_key="gmail-source-apply",
            source_message_id="gmail-m-apply",
            labels_added=["STARRED"],
            labels_removed=["UNREAD"],
            tenant_id="user:42",
        )
        message_row = db.execute_query(
            "SELECT label_text, raw_metadata_json FROM email_messages WHERE id = ?",
            (int(upsert_result["email_message_id"]),),
        ).fetchone()
        fts_row = db.execute_query(
            "SELECT label_text FROM email_fts WHERE rowid = ?",
            (int(upsert_result["email_message_id"]),),
        ).fetchone()

        assert result["applied"] is True
        assert sorted(result["labels"]) == ["INBOX", "STARRED"]
        assert message_row is not None
        assert message_row["label_text"] == "INBOX, STARRED"
        metadata = json.loads(str(message_row["raw_metadata_json"]))
        assert metadata["labels"] == ["INBOX", "STARRED"]
        assert metadata["email"]["labels"] == ["INBOX", "STARRED"]
        assert fts_row is not None
        assert fts_row["label_text"] == "INBOX, STARRED"
    finally:
        db.close_connection()


def test_apply_email_label_delta_returns_message_not_found_when_source_exists() -> None:
    mutation_ops_module = _load_mutation_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-mutation-helper-missing-test")
    try:
        db.mark_email_sync_run_started(
            provider="gmail",
            source_key="gmail-source-missing",
            tenant_id="user:42",
            cursor="cursor-1",
        )

        missing = mutation_ops_module.apply_email_label_delta(
            db,
            provider="gmail",
            source_key="gmail-source-missing",
            source_message_id="gmail-m-missing",
            labels_added=["STARRED"],
            tenant_id="user:42",
        )

        assert missing["applied"] is False
        assert missing["reason"] == "message_not_found"
    finally:
        db.close_connection()


def test_reconcile_email_message_state_preserves_noop_and_delete_outcomes() -> None:
    mutation_ops_module = _load_mutation_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-mutation-helper-reconcile-test")
    try:
        noop = mutation_ops_module.reconcile_email_message_state(
            db,
            provider="gmail",
            source_key="gmail-source-state",
            source_message_id="gmail-m-state",
            tenant_id="user:42",
            deleted=None,
        )
        missing_source = mutation_ops_module.reconcile_email_message_state(
            db,
            provider="gmail",
            source_key="gmail-source-state",
            source_message_id="gmail-m-state",
            tenant_id="user:42",
            deleted=True,
        )

        media_id = _add_email_media(
            db,
            url="email://mutation-reconcile-1",
            title="Mutation Reconcile Email",
            content="Mutation reconcile body",
        )
        upsert_result = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Mutation Reconcile Subject",
                "email": {
                    "from": "alice@example.com",
                    "to": "bob@example.com",
                    "subject": "Mutation Reconcile Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<mutation-reconcile@example.com>",
                    "labels": ["INBOX"],
                },
            },
            body_text="Mutation reconcile body",
            source_message_id="gmail-m-state",
            source_key="gmail-source-state",
            provider="gmail",
            tenant_id="user:42",
        )
        deleted = mutation_ops_module.reconcile_email_message_state(
            db,
            provider="gmail",
            source_key="gmail-source-state",
            source_message_id="gmail-m-state",
            tenant_id="user:42",
            deleted=True,
        )
        already_deleted = mutation_ops_module.reconcile_email_message_state(
            db,
            provider="gmail",
            source_key="gmail-source-state",
            source_message_id="gmail-m-state",
            tenant_id="user:42",
            deleted=True,
        )

        assert noop["applied"] is False
        assert noop["reason"] == "no_state_change"
        assert missing_source["applied"] is False
        assert missing_source["reason"] == "source_not_found"
        assert deleted["applied"] is True
        assert deleted["reason"] == "deleted"
        assert (
            db.get_email_message_detail(
                email_message_id=int(upsert_result["email_message_id"]),
                tenant_id="user:42",
            )
            is None
        )
        assert already_deleted["applied"] is False
        assert already_deleted["reason"] == "already_deleted"
    finally:
        db.close_connection()
