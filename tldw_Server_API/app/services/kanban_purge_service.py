"""
Kanban soft-delete purge scheduler.

Permanently removes soft-deleted Kanban items after a grace period.

Enable via env:
  - KANBAN_PURGE_ENABLED=true
  - KANBAN_PURGE_INTERVAL_SEC=86400 (default daily)
  - KANBAN_PURGE_GRACE_DAYS=30
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def _enumerate_user_ids() -> list[int]:
    """Get list of user IDs from user database directories."""
    try:
        base = DatabasePaths.get_user_db_base_dir()
    except Exception as exc:
        logger.debug(f"kanban_purge: failed to resolve user db base dir: {exc}")
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


def _purge_for_user(user_id: int, grace_days: int) -> dict:
    """Purge soft-deleted kanban items for a user and return counts."""
    db_path = DatabasePaths.get_kanban_db_path(user_id)
    db = KanbanDB(db_path=str(db_path), user_id=str(user_id))
    try:
        return db.purge_deleted_items(days_old=grace_days)
    finally:
        try:
            db.close()
        except Exception:
            pass


async def start_kanban_purge_scheduler() -> Optional[asyncio.Task]:
    enabled = os.getenv("KANBAN_PURGE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    try:
        interval = int(os.getenv("KANBAN_PURGE_INTERVAL_SEC", "86400"))
    except (TypeError, ValueError):
        interval = 86400
    try:
        grace_days = int(os.getenv("KANBAN_PURGE_GRACE_DAYS", "30"))
    except (TypeError, ValueError):
        grace_days = 30

    async def _runner() -> None:
        await asyncio.sleep(min(interval, 60))
        while True:
            try:
                totals = {"boards": 0, "lists": 0, "cards": 0}
                for user_id in _enumerate_user_ids():
                    counts = _purge_for_user(user_id, grace_days)
                    for key in totals:
                        totals[key] += int(counts.get(key, 0))
                if any(totals.values()):
                    logger.info(
                        "Kanban purge removed boards={boards} lists={lists} cards={cards}",
                        **totals,
                    )
            except Exception as exc:
                logger.debug(f"kanban_purge: purge run failed: {exc}")
            await asyncio.sleep(interval)

    task = asyncio.create_task(_runner(), name="kanban_purge_scheduler")
    logger.info(f"Started Kanban purge scheduler: interval={interval}s grace_days={grace_days}")
    return task


__all__ = ["start_kanban_purge_scheduler"]
