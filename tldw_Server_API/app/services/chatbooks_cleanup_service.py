from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.Chatbooks.chatbook_service import ChatbookService
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def _get_user_db_base_dir() -> Path:
    """Get the base directory for user databases."""
    try:
        from tldw_Server_API.app.core.config import settings
        val = settings.get("USER_DB_BASE_DIR")
        if val:
            return Path(val)
    except Exception as e:
        logger.debug(f"chatbooks_cleanup: failed to read USER_DB_BASE_DIR: {e}")

    project_root = Path(__file__).resolve().parents[3]
    return project_root / "Databases" / "user_databases"


def _enumerate_user_ids() -> list[int]:
    """Get list of user IDs from user database directories."""
    base = _get_user_db_base_dir()
    if not base.exists():
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


def _build_chacha_db_for_user(user_id: int) -> CharactersRAGDB:
    """Build a per-user ChaChaNotes DB handle for cleanup tasks."""
    try:
        db_path = DatabasePaths.get_chacha_db_path(user_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return CharactersRAGDB(db_path=str(db_path), client_id=str(user_id))
    except Exception as e:
        logger.warning(f"chatbooks_cleanup: fallback path for user {user_id} due to: {e}")
        base = Path(__file__).resolve().parents[3] / "Databases" / "user_databases" / str(user_id)
        base.mkdir(parents=True, exist_ok=True)
        return CharactersRAGDB(db_path=str(base / "ChaChaNotes.db"), client_id=str(user_id))


async def run_chatbooks_cleanup_loop(stop_event: Optional[asyncio.Event] = None) -> None:
    """Run scheduled cleanup of expired chatbook exports."""
    interval_sec = int(os.getenv("CHATBOOKS_CLEANUP_INTERVAL_SEC", "0") or "0")
    if interval_sec <= 0:
        logger.info("Chatbooks cleanup scheduler disabled by CHATBOOKS_CLEANUP_INTERVAL_SEC")
        return

    logger.info(f"Starting chatbooks cleanup worker (every {interval_sec}s)")

    while True:
        if stop_event and stop_event.is_set():
            logger.info("Stopping chatbooks cleanup worker on shutdown signal")
            return
        try:
            deleted_total = 0
            for user_id in _enumerate_user_ids():
                db = _build_chacha_db_for_user(user_id)
                svc = ChatbookService(str(user_id), db, user_id_int=user_id)
                deleted_total += svc.cleanup_expired_exports()
            if deleted_total:
                logger.info(f"Chatbooks cleanup removed {deleted_total} expired export files")
        except Exception as exc:
            logger.warning(f"Chatbooks cleanup loop error: {exc}")
        await asyncio.sleep(interval_sec)
