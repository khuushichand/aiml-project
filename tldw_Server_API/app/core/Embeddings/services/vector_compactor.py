"""
Embeddings Vector Compactor

Periodic job to propagate soft-deletes from the Media DB into Chroma collections
by removing vectors associated with deleted documents.

Scoped per user: uses SINGLE_USER_FIXED_ID by default. For multi-user setups,
operators can run one instance per user or extend this to iterate users.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Optional

from loguru import logger

try:
    import redis.asyncio as aioredis  # optional for distributed locks
except Exception:  # pragma: no cover
    aioredis = None  # type: ignore

from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


async def _get_media_ids_marked_deleted(db_path: str) -> list[int]:
    db = create_media_database(client_id="embeddings_vector_compactor", db_path=db_path)
    try:
        cur = db.execute_query("SELECT id FROM Media WHERE deleted = 1")
        rows = cur.fetchall() or []
        return [int(r[0]) for r in rows]
    finally:
        try:
            db.close_connection()
        except Exception:
            pass


def _collection_name_for(user_id: str, media_id: int) -> str:
    return f"user_{user_id}_media_{media_id}"


async def compact_once(user_id: str, db_path: Optional[str] = None) -> int:
    """Run a single compaction pass for the given user.

    Returns the number of collections touched.
    """
    touched = 0
    try:
        from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
        from tldw_Server_API.app.core.config import settings
    except Exception as e:  # pragma: no cover
        logger.error(f"Compactor initialization failed: {e}")
        return 0

    default_path = str(DatabasePaths.get_media_db_path(int(user_id) if str(user_id).isdigit() else DatabasePaths.get_single_user_id()))
    dbp = db_path or os.getenv("MEDIA_DB_PATH", default_path)
    ids = await _get_media_ids_marked_deleted(dbp)
    if not ids:
        return 0

    mgr = ChromaDBManager(user_id=user_id, user_embedding_config=settings)
    for mid in ids:
        try:
            coll_name = _collection_name_for(user_id, mid)
            col = mgr.get_or_create_collection(coll_name)
            delete = getattr(col, "delete", None)
            if callable(delete):
                delete(where={"media_id": str(mid)})
                touched += 1
                logger.info(f"Compactor: removed vectors for media_id={mid} in collection={coll_name}")
        except Exception as e:
            logger.warning(f"Compactor error removing vectors for media_id={mid}: {e}")
    try:
        mgr.close()
    except Exception:
        pass
    return touched


async def run(stop_event: Optional[asyncio.Event] = None) -> None:
    """Run the periodic compactor loop.

    Environment variables:
    - EMBEDDINGS_COMPACTOR_INTERVAL_SECONDS (default: 1800)
    - COMPACTOR_USER_ID (default: SINGLE_USER_FIXED_ID from settings or "1")
    - MEDIA_DB_PATH (optional)
    """
    try:
        from tldw_Server_API.app.core.config import settings
    except Exception as e:  # pragma: no cover
        logger.error(f"Compactor settings load failed: {e}")
        return

    interval = int(os.getenv("EMBEDDINGS_COMPACTOR_INTERVAL_SECONDS", "1800") or 1800)
    user_id = os.getenv("COMPACTOR_USER_ID") or str(settings.get("SINGLE_USER_FIXED_ID", "1"))
    logger.info(f"Starting Embeddings Vector Compactor for user_id={user_id}, interval={interval}s")

    while True:
        try:
            touched = await compact_once(user_id)
            logger.debug(f"Compactor pass complete at {datetime.utcnow().isoformat()} - touched={touched}")
        except Exception as e:
            logger.error(f"Compactor pass error: {e}")

        if stop_event is not None and stop_event.is_set():
            logger.info("Compactor stop requested; exiting")
            break
        try:
            await asyncio.wait_for(asyncio.sleep(max(1, interval)), timeout=None)
        except asyncio.CancelledError:
            logger.info("Compactor cancelled; exiting")
            break
