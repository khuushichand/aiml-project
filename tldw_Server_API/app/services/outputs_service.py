from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.exceptions import InvalidStoragePathError


_SAFE_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def normalize_output_storage_path(user_id: int, storage_path: str) -> str:
    """Normalize legacy storage paths to a safe filename under the user outputs directory."""
    if not storage_path:
        raise InvalidStoragePathError("invalid_path")

    if (
        _SAFE_OUTPUT_NAME_RE.match(storage_path)
        and os.sep not in storage_path
        and (os.altsep is None or os.altsep not in storage_path)
    ):
        return storage_path

    candidate = Path(storage_path).expanduser()
    if (os.sep in storage_path or (os.altsep and os.altsep in storage_path)) and not candidate.is_absolute():
        raise InvalidStoragePathError("invalid_path")
    candidate_name = candidate.name
    if not candidate_name or not _SAFE_OUTPUT_NAME_RE.match(candidate_name):
        raise InvalidStoragePathError("invalid_path")

    if candidate.is_absolute():
        try:
            base_dir = DatabasePaths.get_user_base_directory(user_id) / "outputs"
            base_resolved = base_dir.resolve(strict=False)
            resolved = candidate.resolve(strict=False)
        except Exception as exc:
            raise InvalidStoragePathError("invalid_path") from exc
        if not resolved.is_relative_to(base_resolved) or resolved.parent != base_resolved:
            raise InvalidStoragePathError("invalid_path")

    return candidate_name

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
        new_path = cdb.resolve_output_storage_path(new_path)
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
