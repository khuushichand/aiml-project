"""Package-owned claims review read helpers."""

from __future__ import annotations

from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)
from tldw_Server_API.app.core.DB_Management.scope_context import get_scope


_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def list_claim_review_history(self, claim_id: int) -> list[dict[str, Any]]:
    """Return ordered review log entries for a claim."""
    cur = self.execute_query(
        "SELECT id, claim_id, old_status, new_status, old_text, new_text, reviewer_id, notes, "
        "reason_code, action_ip, action_user_agent, created_at "
        "FROM claims_review_log WHERE claim_id = ? ORDER BY created_at ASC",
        (int(claim_id),),
    )
    rows = cur.fetchall()
    return [dict(row) for row in rows]


def list_review_queue(
    self,
    *,
    status: str | None = None,
    reviewer_id: int | None = None,
    review_group: str | None = None,
    media_id: int | None = None,
    extractor: str | None = None,
    owner_user_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    """List claims in the review queue with optional filters (scoped)."""
    try:
        limit = int(limit)
        offset = int(offset)
    except (TypeError, ValueError):
        limit, offset = 100, 0
    limit = max(1, min(1000, limit))
    offset = max(0, offset)

    conditions: list[str] = ["c.media_id = m.id"]
    params: list[Any] = []

    if not include_deleted:
        conditions.append("c.deleted = 0")
    if status is not None:
        conditions.append("c.review_status = ?")
        params.append(str(status))
    if reviewer_id is not None:
        conditions.append("c.reviewer_id = ?")
        params.append(int(reviewer_id))
    if review_group is not None:
        conditions.append("c.review_group = ?")
        params.append(str(review_group))
    if media_id is not None:
        conditions.append("c.media_id = ?")
        params.append(int(media_id))
    if owner_user_id is not None:
        conditions.append("COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?")
        params.append(str(owner_user_id))
    if extractor is not None:
        conditions.append("c.extractor = ?")
        params.append(str(extractor))

    try:
        scope = get_scope()
    except _MEDIA_NONCRITICAL_EXCEPTIONS as scope_err:
        logger.debug("Failed to resolve scope for review queue visibility filter: {}", scope_err)
        scope = None
    if scope and not scope.is_admin:
        visibility_parts: list[str] = []
        user_id_str = str(scope.user_id) if scope.user_id is not None else ""
        if user_id_str:
            visibility_parts.append(
                "(COALESCE(m.visibility, 'personal') = 'personal' "
                "AND (COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?))"
            )
            params.append(user_id_str)
        if scope.team_ids:
            team_placeholders = ",".join("?" * len(scope.team_ids))
            visibility_parts.append(
                f"(m.visibility = 'team' AND m.team_id IN ({team_placeholders}))"
            )
            params.extend(scope.team_ids)
        if scope.org_ids:
            org_placeholders = ",".join("?" * len(scope.org_ids))
            visibility_parts.append(
                f"(m.visibility = 'org' AND m.org_id IN ({org_placeholders}))"
            )
            params.extend(scope.org_ids)

        if visibility_parts:
            conditions.append(f"({' OR '.join(visibility_parts)})")
        else:
            conditions.append("(0 = 1)")

    sql = (
        "SELECT c.id, c.media_id, c.chunk_index, c.span_start, c.span_end, c.claim_text, "  # nosec B608
        "c.confidence, c.extractor, c.extractor_version, c.chunk_hash, c.created_at, c.uuid, "
        "c.last_modified, c.version, c.client_id, c.deleted, "
        "c.review_status, c.reviewer_id, c.review_group, c.reviewed_at, "
        "c.review_notes, c.review_version, c.review_reason_code, c.claim_cluster_id, "
        "m.title AS media_title, m.visibility AS media_visibility, "
        "m.owner_user_id AS media_owner_user_id, m.org_id AS media_org_id, "
        "m.team_id AS media_team_id, m.client_id AS media_client_id "
        "FROM Claims c JOIN Media m ON c.media_id = m.id "
        f"WHERE {' AND '.join(conditions)} "
        "ORDER BY c.reviewed_at DESC, c.id DESC "
        "LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])
    rows = self.execute_query(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]
