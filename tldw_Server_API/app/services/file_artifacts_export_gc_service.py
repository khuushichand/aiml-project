"""
Periodic cleanup for expired file artifact exports.

Env:
  FILES_EXPORT_GC_ENABLED=true|false
  FILES_EXPORT_GC_INTERVAL_SEC=3600
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.exceptions import StoragePathValidationError


def _enumerate_user_ids() -> list[int]:
    try:
        base = DatabasePaths.get_user_db_base_dir()
    except Exception as exc:
        logger.debug(f"files_export_gc: failed to resolve user db base dir: {exc}")
        return []
    uids: list[int] = []
    for p in base.iterdir():
        if p.is_dir():
            try:
                uids.append(int(p.name))
            except (TypeError, ValueError):
                continue
    if not uids:
        try:
            uids = [DatabasePaths.get_single_user_id()]
        except Exception as exc:
            logger.debug(f"files_export_gc: failed to derive single user id: {exc}")
            uids = []
    return sorted(set(uids))


async def _purge_expired_exports_for_user(user_id: int, now_iso: str) -> tuple[int, int]:
    """Return (cleared_exports, files_deleted)."""
    cdb = CollectionsDatabase.for_user(user_id=user_id)
    rows = cdb.list_file_artifacts_expired_exports(now_iso=now_iso)
    if not rows:
        return 0, 0
    files_deleted = 0
    cleared = 0
    for row in rows:
        file_id = int(row.get("id"))
        storage_path = row.get("export_storage_path")
        if storage_path:
            try:
                relative_name = cdb.resolve_temp_output_storage_path(storage_path)
                outputs_dir = DatabasePaths.get_user_temp_outputs_dir(user_id)
                path = outputs_dir / relative_name
                if path.exists():
                    path.unlink()
                    files_deleted += 1
            except StoragePathValidationError as exc:
                logger.warning(f"files_export_gc: invalid export path for file {file_id}: {exc}")
            except (OSError, PermissionError) as exc:
                logger.warning(f"files_export_gc: failed to delete export file for {file_id}: {exc}")
        try:
            cdb.update_file_artifact_export(
                file_id,
                export_status="none",
                export_format=row.get("export_format"),
                export_storage_path=None,
                export_bytes=row.get("export_bytes"),
                export_content_type=row.get("export_content_type"),
                export_job_id=row.get("export_job_id"),
                export_expires_at=None,
                export_consumed_at=None,
            )
            cleared += 1
        except KeyError:
            logger.debug(f"files_export_gc: file artifact not found for {file_id}")
        except Exception as exc:
            logger.warning(f"files_export_gc: failed to clear export state for {file_id}: {exc}")
    return cleared, files_deleted


async def start_file_artifacts_export_gc_scheduler() -> Optional[asyncio.Task]:
    enabled = os.getenv("FILES_EXPORT_GC_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    try:
        interval = int(os.getenv("FILES_EXPORT_GC_INTERVAL_SEC", "3600"))
    except (TypeError, ValueError) as exc:
        logger.debug(f"files_export_gc: invalid FILES_EXPORT_GC_INTERVAL_SEC; using default: {exc}")
        interval = 3600

    async def _runner():
        await asyncio.sleep(min(interval, 60))
        while True:
            try:
                now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                total_cleared = 0
                total_files = 0
                for uid in _enumerate_user_ids():
                    cleared, files_deleted = await _purge_expired_exports_for_user(uid, now_iso)
                    total_cleared += cleared
                    total_files += files_deleted
                if total_cleared or total_files:
                    logger.info(f"Files export GC: cleared={total_cleared} files_deleted={total_files}")
            except Exception as exc:
                logger.debug(f"files_export_gc: run failed: {exc}")
            await asyncio.sleep(interval)

    task = asyncio.create_task(_runner(), name="file_artifacts_export_gc")
    logger.info(f"Started file artifacts export GC scheduler: interval={interval}s")
    return task
