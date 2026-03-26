"""Package-owned claims direct read helpers."""

from __future__ import annotations

from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)
from tldw_Server_API.app.core.DB_Management.scope_context import get_scope


_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def get_claims_by_media(
    self,
    media_id: int,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Fetch claims for a media item ordered by chunk then id."""
    cur = self.execute_query(
        """
        SELECT id, media_id, chunk_index, span_start, span_end, claim_text, confidence,
               extractor, extractor_version, chunk_hash, created_at, uuid,
               last_modified, version, client_id,
               review_status, reviewer_id, review_group, reviewed_at,
               review_notes, review_version, review_reason_code, claim_cluster_id
        FROM Claims
        WHERE media_id = ? AND deleted = 0
        ORDER BY chunk_index ASC, id ASC
        LIMIT ? OFFSET ?
        """,
        (media_id, int(limit), int(max(0, offset))),
    )
    rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_claim_with_media(
    self,
    claim_id: int,
    *,
    include_deleted: bool = False,
) -> dict[str, Any] | None:
    """Fetch a claim by id with scoped media visibility metadata."""
    conditions: list[str] = ["c.media_id = m.id", "c.id = ?"]
    params: list[Any] = [int(claim_id)]

    if not include_deleted:
        conditions.append("c.deleted = 0")

    try:
        scope = get_scope()
    except _MEDIA_NONCRITICAL_EXCEPTIONS as scope_err:
        logger.debug("Failed to resolve scope for claim lookup: {}", scope_err)
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
        "LIMIT 1"
    )
    row = self.execute_query(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def get_claims_by_uuid(self, uuids: list[str]) -> list[dict[str, Any]]:
    """Fetch claims by UUID preserving backend row order."""
    if not uuids:
        return []
    placeholders = ",".join("?" * len(uuids))
    sql = (
        "SELECT id, uuid, media_id, chunk_index, claim_text, reviewer_id, review_group "  # nosec B608
        f"FROM Claims WHERE uuid IN ({placeholders})"
    )
    rows = self.execute_query(sql, tuple(uuids)).fetchall()
    return [dict(row) for row in rows]
