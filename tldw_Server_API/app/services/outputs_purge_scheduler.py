"""
Daily outputs purge scheduler.

Runs a daily cleanup to remove outputs according to retention policy and
aged soft-deleted rows. Optionally deletes files before removing DB rows.

Enable via env:
  - OUTPUTS_PURGE_ENABLED=true
  - OUTPUTS_PURGE_INTERVAL_SEC=86400 (default daily)
  - OUTPUTS_PURGE_DELETE_FILES=false
  - OUTPUTS_PURGE_GRACE_DAYS=30

This is a simple asyncio interval job (keeps latency minimal). For cron-timezone
exactness, integrate with the APScheduler service later.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase


def _get_user_db_base_dir() -> Path:
    try:
        from tldw_Server_API.app.core.config import settings
        val = settings.get("USER_DB_BASE_DIR")
        if val:
            return Path(val)
    except Exception:
        pass
    # Fallback to repo default
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "Databases" / "user_databases"


def _enumerate_user_ids() -> list[int]:
    base = _get_user_db_base_dir()
    if not base.exists():
        return []
    uids: list[int] = []
    for p in base.iterdir():
        if p.is_dir():
            try:
                uids.append(int(p.name))
            except Exception:
                continue
    if not uids:
        try:
            uids = [DatabasePaths.get_single_user_id()]
        except Exception:
            uids = []
    return sorted(set(uids))


async def _purge_for_user(user_id: int, delete_files: bool, grace_days: int) -> tuple[int, int]:
    """Return (removed, files_deleted)."""
    cdb = CollectionsDatabase.for_user(user_id)
    # Build candidate set similar to /outputs/purge endpoint
    from datetime import datetime
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    ids: set[int] = set()
    paths: dict[int, str] = {}
    try:
        cur = cdb.backend.execute(
            "SELECT id, storage_path FROM outputs WHERE user_id = ? AND retention_until IS NOT NULL AND retention_until <= ?",
            (str(user_id), now),
        )
        for row in cur.rows:
            rid = int(row["id"]) if isinstance(row, dict) else int(row[0])
            ids.add(rid)
            paths[rid] = row["storage_path"] if isinstance(row, dict) else row[1]
    except Exception:
        pass
    try:
        cur2 = cdb.backend.execute(
            "SELECT id, storage_path FROM outputs WHERE user_id = ? AND deleted = 1 AND deleted_at IS NOT NULL AND julianday(?) - julianday(deleted_at) >= ?",
            (str(user_id), now, grace_days),
        )
        for row in cur2.rows:
            rid = int(row["id"]) if isinstance(row, dict) else int(row[0])
            ids.add(rid)
            paths[rid] = row["storage_path"] if isinstance(row, dict) else row[1]
    except Exception:
        pass
    files_deleted = 0
    if delete_files and ids:
        for rid, pth in list(paths.items()):
            try:
                p = Path(pth)
                if p.exists():
                    p.unlink()
                    files_deleted += 1
            except Exception:
                continue
    removed = 0
    if ids:
        placeholders = ",".join(["?"] * len(ids))
        try:
            cdb.backend.execute(
                f"DELETE FROM outputs WHERE user_id = ? AND id IN ({placeholders})",
                tuple([str(user_id)] + list(ids)),
            )
            removed = len(ids)
        except Exception:
            removed = 0
    return removed, files_deleted


async def start_outputs_purge_scheduler() -> Optional[asyncio.Task]:
    enabled = os.getenv("OUTPUTS_PURGE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    try:
        interval = int(os.getenv("OUTPUTS_PURGE_INTERVAL_SEC", "86400"))
    except Exception:
        interval = 86400
    delete_files = os.getenv("OUTPUTS_PURGE_DELETE_FILES", "false").lower() in {"1", "true", "yes", "on"}
    try:
        grace_days = int(os.getenv("OUTPUTS_PURGE_GRACE_DAYS", "30"))
    except Exception:
        grace_days = 30

    async def _runner():
        await asyncio.sleep(min(interval, 60))
        while True:
            try:
                uids = _enumerate_user_ids()
                total_removed = 0
                total_files = 0
                for uid in uids:
                    r, f = await _purge_for_user(uid, delete_files, grace_days)
                    total_removed += r
                    total_files += f
                if total_removed or total_files:
                    logger.info(f"Outputs purge: removed={total_removed} files_deleted={total_files}")
            except Exception as e:
                logger.debug(f"Outputs purge run failed: {e}")
            await asyncio.sleep(interval)

    task = asyncio.create_task(_runner(), name="outputs_purge_scheduler")
    logger.info(f"Started outputs purge scheduler: interval={interval}s delete_files={delete_files} grace_days={grace_days}")
    return task

