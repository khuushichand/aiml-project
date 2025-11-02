from __future__ import annotations

from typing import Dict, List, Optional
from loguru import logger

def update_output_artifact_db(
    cdb,
    output_id: int,
    user_id: int,
    new_title: Optional[str],
    new_path: Optional[str],
    new_format: Optional[str],
    retention_until: Optional[str],
):
    """Apply partial updates to an output artifact row and return the refreshed row.

    This function encapsulates the SQL UPDATE previously issued from the endpoint.
    """
    sets: list[str] = []
    params: list[object] = []
    if new_title is not None:
        sets.append("title = ?")
        params.append(new_title)
    if new_path is not None:
        sets.append("storage_path = ?")
        params.append(new_path)
    if new_format is not None:
        sets.append("format = ?")
        params.append(new_format)
    if retention_until is not None:
        sets.append("retention_until = ?")
        params.append(retention_until)
    if sets:
        params.extend([output_id, user_id])
        q = f"UPDATE outputs SET {', '.join(sets)} WHERE id = ? AND user_id = ? AND deleted = 0"
        try:
            cdb.backend.execute(q, tuple(params))
        except Exception as e:
            logger.error(f"outputs_service.update: DB update failed: {e}")
            raise
    try:
        return cdb.get_output_artifact(output_id)
    except Exception as e:
        logger.error(f"outputs_service.update: failed to fetch updated row: {e}")
        raise


def find_outputs_to_purge(
    cdb,
    now_iso: str,
    soft_deleted_grace_days: int,
    include_retention: bool,
) -> Dict[int, str]:
    """Return a mapping of output_id -> storage_path for purge candidates.

    Combines retention-based and aged soft-deleted selections.
    """
    paths: Dict[int, str] = {}
    # Retention-based candidates
    if include_retention:
        try:
            cur = cdb.backend.execute(
                "SELECT id, storage_path FROM outputs WHERE user_id = ? AND retention_until IS NOT NULL AND retention_until <= ?",
                (cdb.user_id, now_iso),
            )
            for row in cur.rows:
                rid = int(row["id"]) if isinstance(row, dict) else int(row[0])
                paths[rid] = row["storage_path"] if isinstance(row, dict) else row[1]
        except Exception as e:
            logger.warning(f"outputs_service.purge: retention scan failed: {e}")
    # Soft-deleted grace candidates
    try:
        cur2 = cdb.backend.execute(
            "SELECT id, storage_path FROM outputs WHERE user_id = ? AND deleted = 1 AND deleted_at IS NOT NULL AND julianday(?) - julianday(deleted_at) >= ?",
            (cdb.user_id, now_iso, soft_deleted_grace_days),
        )
        for row in cur2.rows:
            rid = int(row["id"]) if isinstance(row, dict) else int(row[0])
            paths[rid] = row["storage_path"] if isinstance(row, dict) else row[1]
    except Exception as e:
        logger.warning(f"outputs_service.purge: soft-deleted scan failed: {e}")
    return paths


def delete_outputs_by_ids(cdb, user_id: int, ids: List[int]) -> int:
    """Delete output rows by IDs for a user. Returns number of IDs requested (best-effort)."""
    if not ids:
        return 0
    placeholders = ",".join(["?"] * len(ids))
    try:
        cdb.backend.execute(
            f"DELETE FROM outputs WHERE user_id = ? AND id IN ({placeholders})",
            tuple([user_id] + list(ids)),
        )
        return len(ids)
    except Exception as e:
        logger.error(f"outputs_service.purge: delete failed: {e}")
        raise
