from __future__ import annotations

import importlib

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase


pytestmark = pytest.mark.unit


def test_resolve_email_sync_source_row_id_creates_source_only_when_requested() -> None:
    email_state_ops_module = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.email_state_ops"
    )

    db = MediaDatabase(db_path=":memory:", client_id="email-state-helper-source-test")
    try:
        conn = db.get_connection()

        missing = email_state_ops_module._resolve_email_sync_source_row_id(
            db,
            conn,
            tenant_id="user:42",
            provider="gmail",
            source_key="gmail-source-1",
            create_if_missing=False,
        )
        created = email_state_ops_module._resolve_email_sync_source_row_id(
            db,
            conn,
            tenant_id="user:42",
            provider="gmail",
            source_key="gmail-source-1",
            create_if_missing=True,
        )

        assert missing is None
        assert isinstance(created, int)
        assert created > 0
    finally:
        db.close_connection()


def test_email_sync_state_helper_roundtrip_preserves_retry_and_cursor_semantics() -> None:
    email_state_ops_module = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.email_state_ops"
    )

    db = MediaDatabase(db_path=":memory:", client_id="email-state-helper-sync-test")
    try:
        assert (
            email_state_ops_module.get_email_sync_state(
                db,
                provider="gmail",
                source_key="gmail-source-1",
                tenant_id="user:42",
            )
            is None
        )

        started = email_state_ops_module.mark_email_sync_run_started(
            db,
            provider="gmail",
            source_key="gmail-source-1",
            tenant_id="user:42",
            cursor="cursor-1",
        )
        failed = email_state_ops_module.mark_email_sync_run_failed(
            db,
            provider="gmail",
            source_key="gmail-source-1",
            tenant_id="user:42",
            error_state="quota_limited",
        )
        succeeded = email_state_ops_module.mark_email_sync_run_succeeded(
            db,
            provider="gmail",
            source_key="gmail-source-1",
            tenant_id="user:42",
            cursor=None,
        )

        assert started["cursor"] == "cursor-1"
        assert failed["retry_backoff_count"] == 1
        assert failed["error_state"] == "quota_limited"
        assert succeeded["cursor"] == "cursor-1"
        assert succeeded["retry_backoff_count"] == 0
        assert succeeded["error_state"] is None
    finally:
        db.close_connection()


def test_update_email_backfill_progress_preserves_last_error_until_replaced() -> None:
    email_state_ops_module = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.email_state_ops"
    )

    db = MediaDatabase(db_path=":memory:", client_id="email-state-helper-backfill-test")
    try:
        email_state_ops_module._update_email_backfill_progress(
            db,
            tenant_id="user:42",
            backfill_key="legacy-test",
            last_media_id=5,
            delta_processed=1,
            delta_success=0,
            delta_skipped=0,
            delta_failed=1,
            status="running",
            last_error="first-error",
        )
        email_state_ops_module._update_email_backfill_progress(
            db,
            tenant_id="user:42",
            backfill_key="legacy-test",
            last_media_id=6,
            delta_processed=2,
            delta_success=2,
            delta_skipped=0,
            delta_failed=0,
            status="running",
            last_error=None,
        )
        preserved = email_state_ops_module.get_email_legacy_backfill_state(
            db,
            tenant_id="user:42",
            backfill_key="legacy-test",
        )

        email_state_ops_module._update_email_backfill_progress(
            db,
            tenant_id="user:42",
            backfill_key="legacy-test",
            last_media_id=7,
            delta_processed=0,
            delta_success=0,
            delta_skipped=1,
            delta_failed=0,
            status="completed",
            last_error="replacement-error",
        )
        replaced = email_state_ops_module.get_email_legacy_backfill_state(
            db,
            tenant_id="user:42",
            backfill_key="legacy-test",
        )

        assert preserved is not None
        assert preserved["processed_count"] == 3
        assert preserved["success_count"] == 2
        assert preserved["failed_count"] == 1
        assert preserved["last_error"] == "first-error"

        assert replaced is not None
        assert replaced["processed_count"] == 3
        assert replaced["skipped_count"] == 1
        assert replaced["last_error"] == "replacement-error"
        assert replaced["status"] == "completed"
    finally:
        db.close_connection()
