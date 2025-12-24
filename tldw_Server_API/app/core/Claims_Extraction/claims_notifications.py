from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def record_review_assignment_notifications(
    *,
    db: MediaDatabase,
    owner_user_id: str,
    assignments: List[Dict[str, Any]],
) -> int:
    if not assignments:
        return 0
    uuids = [str(item.get("uuid")) for item in assignments if item.get("uuid")]
    if not uuids:
        return 0
    rows = db.get_claims_by_uuid(uuids)
    row_by_uuid = {str(row.get("uuid")): row for row in rows if row.get("uuid")}
    inserted = 0
    for item in assignments:
        claim_uuid = str(item.get("uuid") or "")
        row = row_by_uuid.get(claim_uuid)
        if not row:
            continue
        payload = {
            "claim_id": int(row.get("id") or 0),
            "claim_uuid": claim_uuid,
            "media_id": int(row.get("media_id") or 0),
            "chunk_index": int(row.get("chunk_index") or 0),
            "claim_text": str(row.get("claim_text") or ""),
            "reviewer_id": item.get("reviewer_id"),
            "review_group": item.get("review_group"),
        }
        try:
            db.insert_claim_notification(
                user_id=str(owner_user_id),
                kind="review_assignment",
                target_user_id=str(item.get("reviewer_id")) if item.get("reviewer_id") is not None else None,
                target_review_group=str(item.get("review_group")) if item.get("review_group") else None,
                resource_type="claim",
                resource_id=str(row.get("id") or ""),
                payload_json=json.dumps(payload),
            )
            inserted += 1
        except Exception as exc:
            logger.debug(f"Failed to insert review assignment notification: {exc}")
    return inserted


def record_watchlist_cluster_notifications(
    *,
    db: MediaDatabase,
    owner_user_id: str,
    clusters: Dict[int, Dict[str, Any]],
    member_counts: Dict[int, int],
    subscriptions: Dict[int, List[int]],
) -> int:
    if not subscriptions:
        return 0
    inserted = 0
    for cluster_id, job_ids in subscriptions.items():
        cluster = clusters.get(int(cluster_id))
        if not cluster:
            continue
        member_count = int(member_counts.get(int(cluster_id), 0))
        if member_count <= 0:
            continue
        latest = db.get_latest_claim_notification(
            user_id=str(owner_user_id),
            kind="watchlist_cluster_update",
            resource_type="cluster",
            resource_id=str(cluster_id),
        )
        if latest:
            try:
                payload = json.loads(latest.get("payload_json") or "{}")
            except Exception:
                payload = {}
            try:
                if int(payload.get("member_count") or 0) == member_count:
                    continue
            except Exception:
                pass
        payload = {
            "cluster_id": int(cluster_id),
            "canonical_claim_text": str(cluster.get("canonical_claim_text") or ""),
            "member_count": member_count,
            "watchlist_job_ids": [int(j) for j in job_ids if j is not None],
        }
        try:
            db.insert_claim_notification(
                user_id=str(owner_user_id),
                kind="watchlist_cluster_update",
                target_user_id=str(owner_user_id),
                resource_type="cluster",
                resource_id=str(cluster_id),
                payload_json=json.dumps(payload),
            )
            inserted += 1
        except Exception as exc:
            logger.debug(f"Failed to insert watchlist cluster notification: {exc}")
    return inserted
