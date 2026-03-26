"""Package-owned email sync-state and backfill-state helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db.errors import (
    DatabaseError,
    InputError,
)


def _resolve_email_sync_source_row_id(
    self,
    conn,
    *,
    tenant_id: str,
    provider: str,
    source_key: str,
    create_if_missing: bool,
) -> int | None:
    if create_if_missing:
        self._execute_with_connection(
            conn,
            (
                "INSERT INTO email_sources "
                "(tenant_id, provider, source_key, display_name, status) "
                "VALUES (?, ?, ?, ?, 'active') "
                "ON CONFLICT(tenant_id, provider, source_key) "
                "DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
            ),
            (tenant_id, provider, source_key, source_key),
        )

    source_row = self._fetchone_with_connection(
        conn,
        (
            "SELECT id FROM email_sources "
            "WHERE tenant_id = ? AND provider = ? AND source_key = ? "
            "LIMIT 1"
        ),
        (tenant_id, provider, source_key),
    )
    if not source_row:
        return None
    return int(source_row["id"])


def _fetch_email_sync_state_row(
    self,
    conn,
    *,
    tenant_id: str,
    source_id: int,
    provider: str,
    source_key: str,
) -> dict[str, Any] | None:
    state_row = self._fetchone_with_connection(
        conn,
        (
            "SELECT id, cursor, last_run_at, last_success_at, error_state, "
            "retry_backoff_count, updated_at "
            "FROM email_sync_state "
            "WHERE tenant_id = ? AND source_id = ? "
            "LIMIT 1"
        ),
        (tenant_id, int(source_id)),
    )
    if not state_row:
        return None
    return {
        "id": int(state_row["id"]),
        "tenant_id": tenant_id,
        "source_id": int(source_id),
        "provider": provider,
        "source_key": source_key,
        "cursor": state_row.get("cursor"),
        "last_run_at": state_row.get("last_run_at"),
        "last_success_at": state_row.get("last_success_at"),
        "error_state": state_row.get("error_state"),
        "retry_backoff_count": int(state_row.get("retry_backoff_count") or 0),
        "updated_at": state_row.get("updated_at"),
    }


def get_email_sync_state(
    self,
    *,
    provider: str,
    source_key: str,
    tenant_id: str | None = None,
) -> dict[str, Any] | None:
    resolved_tenant = self._resolve_email_tenant_id(tenant_id)
    resolved_provider = str(provider or "").strip().lower() or "upload"
    resolved_source_key = str(source_key or "").strip()
    if not resolved_source_key:
        raise InputError("source_key is required for email sync state.")  # noqa: TRY003

    with self.transaction() as conn:
        source_row_id = self._resolve_email_sync_source_row_id(
            conn,
            tenant_id=resolved_tenant,
            provider=resolved_provider,
            source_key=resolved_source_key,
            create_if_missing=False,
        )
        if source_row_id is None:
            return None
        return self._fetch_email_sync_state_row(
            conn,
            tenant_id=resolved_tenant,
            source_id=source_row_id,
            provider=resolved_provider,
            source_key=resolved_source_key,
        )


def mark_email_sync_run_started(
    self,
    *,
    provider: str,
    source_key: str,
    tenant_id: str | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    resolved_tenant = self._resolve_email_tenant_id(tenant_id)
    resolved_provider = str(provider or "").strip().lower() or "upload"
    resolved_source_key = str(source_key or "").strip()
    if not resolved_source_key:
        raise InputError("source_key is required for email sync state.")  # noqa: TRY003

    started_at = datetime.now(timezone.utc).isoformat()
    normalized_cursor = self._normalize_email_sync_cursor(cursor)

    with self.transaction() as conn:
        source_row_id = self._resolve_email_sync_source_row_id(
            conn,
            tenant_id=resolved_tenant,
            provider=resolved_provider,
            source_key=resolved_source_key,
            create_if_missing=True,
        )
        if source_row_id is None:
            raise DatabaseError("Failed to resolve email source for sync state.")  # noqa: TRY003

        existing_row = self._fetch_email_sync_state_row(
            conn,
            tenant_id=resolved_tenant,
            source_id=source_row_id,
            provider=resolved_provider,
            source_key=resolved_source_key,
        )
        next_cursor = (
            normalized_cursor if normalized_cursor is not None else (existing_row or {}).get("cursor")
        )

        if existing_row:
            self._execute_with_connection(
                conn,
                (
                    "UPDATE email_sync_state SET "
                    "cursor = ?, "
                    "last_run_at = ?, "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?"
                ),
                (next_cursor, started_at, int(existing_row["id"])),
            )
        else:
            self._execute_with_connection(
                conn,
                (
                    "INSERT INTO email_sync_state "
                    "(tenant_id, source_id, cursor, last_run_at, last_success_at, error_state, retry_backoff_count, updated_at) "
                    "VALUES (?, ?, ?, ?, NULL, NULL, 0, CURRENT_TIMESTAMP)"
                ),
                (
                    resolved_tenant,
                    source_row_id,
                    next_cursor,
                    started_at,
                ),
            )

        state = self._fetch_email_sync_state_row(
            conn,
            tenant_id=resolved_tenant,
            source_id=source_row_id,
            provider=resolved_provider,
            source_key=resolved_source_key,
        )
        if not state:
            raise DatabaseError("Failed to persist email sync start state.")  # noqa: TRY003
        return state


def mark_email_sync_run_succeeded(
    self,
    *,
    provider: str,
    source_key: str,
    cursor: str | None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    resolved_tenant = self._resolve_email_tenant_id(tenant_id)
    resolved_provider = str(provider or "").strip().lower() or "upload"
    resolved_source_key = str(source_key or "").strip()
    if not resolved_source_key:
        raise InputError("source_key is required for email sync state.")  # noqa: TRY003

    succeeded_at = datetime.now(timezone.utc).isoformat()
    normalized_cursor = self._normalize_email_sync_cursor(cursor)

    with self.transaction() as conn:
        source_row_id = self._resolve_email_sync_source_row_id(
            conn,
            tenant_id=resolved_tenant,
            provider=resolved_provider,
            source_key=resolved_source_key,
            create_if_missing=True,
        )
        if source_row_id is None:
            raise DatabaseError("Failed to resolve email source for sync state.")  # noqa: TRY003

        existing_row = self._fetch_email_sync_state_row(
            conn,
            tenant_id=resolved_tenant,
            source_id=source_row_id,
            provider=resolved_provider,
            source_key=resolved_source_key,
        )
        next_cursor = (
            normalized_cursor if normalized_cursor is not None else (existing_row or {}).get("cursor")
        )

        if existing_row:
            self._execute_with_connection(
                conn,
                (
                    "UPDATE email_sync_state SET "
                    "cursor = ?, "
                    "last_run_at = ?, "
                    "last_success_at = ?, "
                    "error_state = NULL, "
                    "retry_backoff_count = 0, "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?"
                ),
                (
                    next_cursor,
                    succeeded_at,
                    succeeded_at,
                    int(existing_row["id"]),
                ),
            )
        else:
            self._execute_with_connection(
                conn,
                (
                    "INSERT INTO email_sync_state "
                    "(tenant_id, source_id, cursor, last_run_at, last_success_at, error_state, retry_backoff_count, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, NULL, 0, CURRENT_TIMESTAMP)"
                ),
                (
                    resolved_tenant,
                    source_row_id,
                    next_cursor,
                    succeeded_at,
                    succeeded_at,
                ),
            )

        state = self._fetch_email_sync_state_row(
            conn,
            tenant_id=resolved_tenant,
            source_id=source_row_id,
            provider=resolved_provider,
            source_key=resolved_source_key,
        )
        if not state:
            raise DatabaseError("Failed to persist email sync success state.")  # noqa: TRY003
        return state


def mark_email_sync_run_failed(
    self,
    *,
    provider: str,
    source_key: str,
    error_state: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    resolved_tenant = self._resolve_email_tenant_id(tenant_id)
    resolved_provider = str(provider or "").strip().lower() or "upload"
    resolved_source_key = str(source_key or "").strip()
    if not resolved_source_key:
        raise InputError("source_key is required for email sync state.")  # noqa: TRY003

    failed_at = datetime.now(timezone.utc).isoformat()
    normalized_error = str(error_state or "sync_failed").strip()[:1024] or "sync_failed"

    with self.transaction() as conn:
        source_row_id = self._resolve_email_sync_source_row_id(
            conn,
            tenant_id=resolved_tenant,
            provider=resolved_provider,
            source_key=resolved_source_key,
            create_if_missing=True,
        )
        if source_row_id is None:
            raise DatabaseError("Failed to resolve email source for sync state.")  # noqa: TRY003

        existing_row = self._fetch_email_sync_state_row(
            conn,
            tenant_id=resolved_tenant,
            source_id=source_row_id,
            provider=resolved_provider,
            source_key=resolved_source_key,
        )
        if existing_row:
            retry_count = int(existing_row.get("retry_backoff_count") or 0) + 1
            self._execute_with_connection(
                conn,
                (
                    "UPDATE email_sync_state SET "
                    "last_run_at = ?, "
                    "error_state = ?, "
                    "retry_backoff_count = ?, "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?"
                ),
                (
                    failed_at,
                    normalized_error,
                    retry_count,
                    int(existing_row["id"]),
                ),
            )
        else:
            self._execute_with_connection(
                conn,
                (
                    "INSERT INTO email_sync_state "
                    "(tenant_id, source_id, cursor, last_run_at, last_success_at, error_state, retry_backoff_count, updated_at) "
                    "VALUES (?, ?, NULL, ?, NULL, ?, 1, CURRENT_TIMESTAMP)"
                ),
                (
                    resolved_tenant,
                    source_row_id,
                    failed_at,
                    normalized_error,
                ),
            )

        state = self._fetch_email_sync_state_row(
            conn,
            tenant_id=resolved_tenant,
            source_id=source_row_id,
            provider=resolved_provider,
            source_key=resolved_source_key,
        )
        if not state:
            raise DatabaseError("Failed to persist email sync failure state.")  # noqa: TRY003
        return state


def _fetch_email_backfill_state_row(
    self,
    conn,
    *,
    tenant_id: str,
    backfill_key: str,
) -> dict[str, Any] | None:
    row = self._fetchone_with_connection(
        conn,
        (
            "SELECT id, last_media_id, processed_count, success_count, skipped_count, "
            "failed_count, status, last_error, started_at, completed_at, updated_at "
            "FROM email_backfill_state "
            "WHERE tenant_id = ? AND backfill_key = ? "
            "LIMIT 1"
        ),
        (tenant_id, backfill_key),
    )
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "tenant_id": tenant_id,
        "backfill_key": backfill_key,
        "last_media_id": int(row.get("last_media_id") or 0),
        "processed_count": int(row.get("processed_count") or 0),
        "success_count": int(row.get("success_count") or 0),
        "skipped_count": int(row.get("skipped_count") or 0),
        "failed_count": int(row.get("failed_count") or 0),
        "status": str(row.get("status") or "idle"),
        "last_error": row.get("last_error"),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "updated_at": row.get("updated_at"),
    }


def _ensure_email_backfill_state_row(
    self,
    conn,
    *,
    tenant_id: str,
    backfill_key: str,
) -> None:
    self._execute_with_connection(
        conn,
        (
            "INSERT INTO email_backfill_state "
            "(tenant_id, backfill_key, last_media_id, processed_count, success_count, "
            "skipped_count, failed_count, status, updated_at) "
            "VALUES (?, ?, 0, 0, 0, 0, 0, 'idle', CURRENT_TIMESTAMP) "
            "ON CONFLICT(tenant_id, backfill_key) DO NOTHING"
        ),
        (tenant_id, backfill_key),
    )


def get_email_legacy_backfill_state(
    self,
    *,
    tenant_id: str | None = None,
    backfill_key: str = "legacy_media_email",
) -> dict[str, Any] | None:
    resolved_tenant = self._resolve_email_tenant_id(tenant_id)
    resolved_key = self._normalize_email_backfill_key(backfill_key)
    with self.transaction() as conn:
        return self._fetch_email_backfill_state_row(
            conn,
            tenant_id=resolved_tenant,
            backfill_key=resolved_key,
        )


def _update_email_backfill_progress(
    self,
    *,
    tenant_id: str,
    backfill_key: str,
    last_media_id: int,
    delta_processed: int,
    delta_success: int,
    delta_skipped: int,
    delta_failed: int,
    status: str,
    last_error: str | None = None,
) -> None:
    error_text = str(last_error or "").strip()
    normalized_error = error_text[:1024] if error_text else None
    with self.transaction() as conn:
        self._ensure_email_backfill_state_row(
            conn,
            tenant_id=tenant_id,
            backfill_key=backfill_key,
        )
        self._execute_with_connection(
            conn,
            (
                "UPDATE email_backfill_state SET "
                "last_media_id = ?, "
                "processed_count = processed_count + ?, "
                "success_count = success_count + ?, "
                "skipped_count = skipped_count + ?, "
                "failed_count = failed_count + ?, "
                "status = ?, "
                "last_error = CASE WHEN ? = 1 THEN ? ELSE last_error END, "
                "updated_at = CURRENT_TIMESTAMP "
                "WHERE tenant_id = ? AND backfill_key = ?"
            ),
            (
                int(last_media_id),
                int(delta_processed),
                int(delta_success),
                int(delta_skipped),
                int(delta_failed),
                str(status or "running"),
                1 if normalized_error else 0,
                normalized_error,
                tenant_id,
                backfill_key,
            ),
        )


__all__ = [
    "_ensure_email_backfill_state_row",
    "_fetch_email_backfill_state_row",
    "_fetch_email_sync_state_row",
    "_resolve_email_sync_source_row_id",
    "_update_email_backfill_progress",
    "get_email_legacy_backfill_state",
    "get_email_sync_state",
    "mark_email_sync_run_failed",
    "mark_email_sync_run_started",
    "mark_email_sync_run_succeeded",
]
