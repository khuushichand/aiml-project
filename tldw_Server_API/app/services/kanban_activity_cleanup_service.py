"""
Kanban activity cleanup scheduler.

Prunes old kanban_activities rows based on per-board retention settings.

Enable via env:
  - KANBAN_ACTIVITY_CLEANUP_ENABLED=true
  - KANBAN_ACTIVITY_CLEANUP_INTERVAL_SEC=86400 (default daily)
"""

from __future__ import annotations

import asyncio
import os

from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB


def _enumerate_user_ids() -> list[int]:
    """Get list of user IDs from user database directories."""
    try:
        base = DatabasePaths.get_user_db_base_dir()
    except Exception as exc:
        logger.debug(f"kanban_activity_cleanup: failed to resolve user db base dir: {exc}")
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
        except Exception:
            uids = []

    return sorted(set(uids))


def _cleanup_for_user(user_id: int) -> int:
    """Run cleanup for a single user's kanban activities."""
    db_path = DatabasePaths.get_kanban_db_path(user_id)
    db = KanbanDB(db_path=str(db_path), user_id=str(user_id))
    try:
        return db.cleanup_old_activities()
    finally:
        try:
            db.close()
        except Exception:
            pass


async def start_kanban_activity_cleanup_scheduler() -> asyncio.Task | None:
    enabled = os.getenv("KANBAN_ACTIVITY_CLEANUP_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    try:
        interval = int(os.getenv("KANBAN_ACTIVITY_CLEANUP_INTERVAL_SEC", "86400"))
    except (TypeError, ValueError):
        interval = 86400

    async def _runner():
        await asyncio.sleep(min(interval, 60))
        while True:
            try:
                total_deleted = 0
                for user_id in _enumerate_user_ids():
                    total_deleted += _cleanup_for_user(user_id)
                if total_deleted:
                    logger.info(f"Kanban activity cleanup removed {total_deleted} old activities")
            except Exception as exc:
                logger.debug(f"kanban_activity_cleanup: cleanup run failed: {exc}")
            await asyncio.sleep(interval)

    task = asyncio.create_task(_runner(), name="kanban_activity_cleanup_scheduler")
    logger.info(f"Started Kanban activity cleanup scheduler: interval={interval}s")
    return task
