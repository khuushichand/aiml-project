"""Package-owned email retention and tenant hard-delete helpers."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError
from tldw_Server_API.app.core.DB_Management.media_db.legacy_maintenance import (
    permanently_delete_item,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)


_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def _parse_email_retention_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
        parsed = parsedate_to_datetime(text)
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
    return None


def _cleanup_email_orphans_for_tenant(
    self,
    conn,
    *,
    tenant_id: str,
    delete_empty_sources: bool = False,
) -> dict[str, int]:
    labels_cursor = self._execute_with_connection(
        conn,
        (
            "DELETE FROM email_labels "
            "WHERE tenant_id = ? "
            "AND NOT EXISTS ("
            "SELECT 1 FROM email_message_labels eml "
            "WHERE eml.label_id = email_labels.id"
            ")"
        ),
        (tenant_id,),
    )
    participants_cursor = self._execute_with_connection(
        conn,
        (
            "DELETE FROM email_participants "
            "WHERE tenant_id = ? "
            "AND NOT EXISTS ("
            "SELECT 1 FROM email_message_participants emp "
            "WHERE emp.participant_id = email_participants.id"
            ")"
        ),
        (tenant_id,),
    )

    sources_deleted = 0
    if delete_empty_sources:
        sources_cursor = self._execute_with_connection(
            conn,
            (
                "DELETE FROM email_sources "
                "WHERE tenant_id = ? "
                "AND NOT EXISTS ("
                "SELECT 1 FROM email_messages em "
                "WHERE em.source_id = email_sources.id"
                ")"
            ),
            (tenant_id,),
        )
        sources_deleted = int(getattr(sources_cursor, "rowcount", 0) or 0)

    return {
        "labels_deleted": int(getattr(labels_cursor, "rowcount", 0) or 0),
        "participants_deleted": int(getattr(participants_cursor, "rowcount", 0) or 0),
        "sources_deleted": int(sources_deleted),
    }


def enforce_email_retention_policy(
    self,
    *,
    retention_days: int,
    tenant_id: str | None = None,
    hard_delete: bool = False,
    include_missing_internal_date: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Apply tenant-scoped retention policy to normalized email rows."""

    try:
        retention_days_int = int(retention_days)
    except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
        raise InputError("retention_days must be an integer.") from exc  # noqa: TRY003
    if retention_days_int < 0:
        raise InputError("retention_days must be greater than or equal to zero.")  # noqa: TRY003

    limit_int = None
    if limit is not None:
        try:
            limit_int = int(limit)
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            raise InputError("limit must be an integer when provided.") from exc  # noqa: TRY003
        if limit_int <= 0:
            raise InputError("limit must be greater than zero when provided.")  # noqa: TRY003

    resolved_tenant = self._resolve_email_tenant_id(tenant_id)
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=retention_days_int)

    with self.transaction() as conn:
        candidate_rows = self._fetchall_with_connection(
            conn,
            (
                "SELECT "
                "em.id AS email_message_id, "
                "em.media_id AS media_id, "
                "em.internal_date AS internal_date, "
                "m.deleted AS media_deleted "
                "FROM email_messages em "
                "JOIN Media m ON m.id = em.media_id "
                "WHERE em.tenant_id = ? "
                "ORDER BY em.internal_date ASC, em.id ASC"
            ),
            (resolved_tenant,),
        )

    skipped_missing_date = 0
    skipped_already_deleted = 0
    eligible_message_ids: list[int] = []
    candidate_media_ids: list[int] = []
    seen_media_ids: set[int] = set()
    for row in candidate_rows:
        parsed_dt = _parse_email_retention_datetime(row.get("internal_date"))
        if parsed_dt is None and not include_missing_internal_date:
            skipped_missing_date += 1
            continue
        if parsed_dt is not None and parsed_dt > cutoff_dt:
            continue

        media_id = int(row["media_id"])
        media_deleted = bool(row.get("media_deleted"))
        if not hard_delete and media_deleted:
            skipped_already_deleted += 1
            continue

        eligible_message_ids.append(int(row["email_message_id"]))
        if media_id in seen_media_ids:
            continue
        seen_media_ids.add(media_id)
        candidate_media_ids.append(media_id)

    total_candidate_media = len(candidate_media_ids)
    if limit_int is not None:
        candidate_media_ids = candidate_media_ids[:limit_int]

    failed_media_ids: list[int] = []
    applied_media_ids: list[int] = []
    for media_id in candidate_media_ids:
        try:
            removed = (
                permanently_delete_item(self, media_id)
                if hard_delete
                else self.soft_delete_media(media_id, cascade=True)
            )
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            logger.warning(
                "Email retention delete failed for tenant={} media_id={}: {}",
                resolved_tenant,
                media_id,
                exc,
            )
            failed_media_ids.append(int(media_id))
            continue
        if removed:
            applied_media_ids.append(int(media_id))
        else:
            failed_media_ids.append(int(media_id))

    with self.transaction() as conn:
        cleanup_counts = _cleanup_email_orphans_for_tenant(
            self,
            conn,
            tenant_id=resolved_tenant,
            delete_empty_sources=False,
        )

    return {
        "tenant_id": resolved_tenant,
        "retention_days": int(retention_days_int),
        "hard_delete": bool(hard_delete),
        "cutoff_internal_date": cutoff_dt.isoformat(),
        "eligible_message_count": int(len(eligible_message_ids)),
        "candidate_media_count": int(total_candidate_media),
        "candidate_media_count_after_limit": int(len(candidate_media_ids)),
        "applied_count": int(len(applied_media_ids)),
        "applied_media_ids": applied_media_ids,
        "failed_media_ids": failed_media_ids,
        "skipped_missing_internal_date_count": int(skipped_missing_date),
        "skipped_already_deleted_count": int(skipped_already_deleted),
        "orphan_labels_deleted": int(cleanup_counts["labels_deleted"]),
        "orphan_participants_deleted": int(cleanup_counts["participants_deleted"]),
        "orphan_sources_deleted": int(cleanup_counts["sources_deleted"]),
    }


def hard_delete_email_tenant_data(
    self,
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Hard-delete all normalized email data and linked Media rows for a tenant."""

    resolved_tenant = self._resolve_email_tenant_id(tenant_id)

    with self.transaction() as conn:
        rows = self._fetchall_with_connection(
            conn,
            (
                "SELECT em.media_id AS media_id "
                "FROM email_messages em "
                "WHERE em.tenant_id = ? "
                "ORDER BY em.id ASC"
            ),
            (resolved_tenant,),
        )
    media_ids = [int(row["media_id"]) for row in rows]

    deleted_media_ids: list[int] = []
    failed_media_ids: list[int] = []
    for media_id in media_ids:
        try:
            removed = permanently_delete_item(self, int(media_id))
        except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
            logger.warning(
                "Tenant email hard delete failed for tenant={} media_id={}: {}",
                resolved_tenant,
                media_id,
                exc,
            )
            failed_media_ids.append(int(media_id))
            continue
        if removed:
            deleted_media_ids.append(int(media_id))
        else:
            failed_media_ids.append(int(media_id))

    sync_state_deleted = 0
    sources_deleted = 0
    backfill_deleted = 0
    cleanup_counts: dict[str, int] = {
        "labels_deleted": 0,
        "participants_deleted": 0,
        "sources_deleted": 0,
    }

    with self.transaction() as conn:
        cleanup_counts = _cleanup_email_orphans_for_tenant(
            self,
            conn,
            tenant_id=resolved_tenant,
            delete_empty_sources=True,
        )

        if not failed_media_ids:
            sync_cursor = self._execute_with_connection(
                conn,
                "DELETE FROM email_sync_state WHERE tenant_id = ?",
                (resolved_tenant,),
            )
            sync_state_deleted = int(getattr(sync_cursor, "rowcount", 0) or 0)

            source_cursor = self._execute_with_connection(
                conn,
                "DELETE FROM email_sources WHERE tenant_id = ?",
                (resolved_tenant,),
            )
            sources_deleted = int(getattr(source_cursor, "rowcount", 0) or 0)

            backfill_cursor = self._execute_with_connection(
                conn,
                "DELETE FROM email_backfill_state WHERE tenant_id = ?",
                (resolved_tenant,),
            )
            backfill_deleted = int(getattr(backfill_cursor, "rowcount", 0) or 0)
        else:
            sources_deleted = int(cleanup_counts.get("sources_deleted", 0))

    return {
        "tenant_id": resolved_tenant,
        "candidate_media_count": int(len(media_ids)),
        "deleted_media_count": int(len(deleted_media_ids)),
        "deleted_media_ids": deleted_media_ids,
        "failed_media_ids": failed_media_ids,
        "sync_state_deleted": int(sync_state_deleted),
        "sources_deleted": int(sources_deleted),
        "backfill_state_deleted": int(backfill_deleted),
        "orphan_labels_deleted": int(cleanup_counts.get("labels_deleted", 0)),
        "orphan_participants_deleted": int(cleanup_counts.get("participants_deleted", 0)),
        "orphan_sources_deleted": int(cleanup_counts.get("sources_deleted", 0)),
    }


__all__ = [
    "_cleanup_email_orphans_for_tenant",
    "_parse_email_retention_datetime",
    "enforce_email_retention_policy",
    "hard_delete_email_tenant_data",
]
