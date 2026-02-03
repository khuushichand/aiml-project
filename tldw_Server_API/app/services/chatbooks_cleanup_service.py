from __future__ import annotations

import asyncio
import os

from loguru import logger

from tldw_Server_API.app.core.Chatbooks.chatbook_service import ChatbookService
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def _enumerate_user_ids() -> list[int]:
    """Get list of user IDs from user database directories."""
    try:
        base = DatabasePaths.get_user_db_base_dir()
    except Exception as exc:
        logger.debug(f"chatbooks_cleanup: failed to resolve user db base dir: {exc}")
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
    db_path = DatabasePaths.get_chacha_db_path(user_id)
    return CharactersRAGDB(db_path=str(db_path), client_id=str(user_id))


async def run_chatbooks_cleanup_loop(stop_event: asyncio.Event | None = None) -> None:
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
