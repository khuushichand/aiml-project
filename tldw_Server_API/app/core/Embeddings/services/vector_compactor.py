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
import sqlite3
from datetime import datetime
from pathlib import Path

from loguru import logger

try:
    import redis.asyncio as aioredis  # optional for distributed locks
except Exception:  # pragma: no cover
    aioredis = None  # type: ignore

try:
    from chromadb.errors import ChromaError
except Exception:  # pragma: no cover
    ChromaError = None  # type: ignore

from tldw_Server_API.app.core.DB_Management.backends.base import (
    DatabaseError as BackendDatabaseError,
)
from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

_DB_CLOSE_EXCEPTIONS = (BackendDatabaseError, sqlite3.Error, OSError, RuntimeError)
_CHROMA_CLOSE_EXCEPTIONS = (RuntimeError, OSError)
if ChromaError is not None:
    _CHROMA_CLOSE_EXCEPTIONS = (*_CHROMA_CLOSE_EXCEPTIONS, ChromaError)


def _sanitize_media_db_path(user_id: str, db_path: str | None) -> str:
    """
    Resolve and validate the media DB path for the given user.

    Ensures that any override stays within the media DB root directory.
    """
    # Compute the default per-user database path and root directory
    default_path = str(
        DatabasePaths.get_media_db_path(
            int(user_id) if str(user_id).isdigit() else DatabasePaths.get_single_user_id()
        )
    )
    default_path_obj = Path(default_path)
    media_root = default_path_obj.parent

    # Start from environment/default behavior if explicit path is not provided
    raw_path = db_path or os.getenv("MEDIA_DB_PATH", default_path)

    # Normalize the candidate path
    candidate = Path(raw_path).expanduser()

    # If the candidate is relative, interpret it as relative to the media root
    if not candidate.is_absolute():
        candidate = media_root / candidate

    # Resolve the final path
    try:
        candidate_resolved = candidate.resolve(strict=False)
    except TypeError:
        # Fallback for environments where strict parameter is not supported
        candidate_resolved = candidate.resolve()

    # Enforce that the final path remains within the media root directory
    try:
        candidate_resolved.relative_to(media_root)
    except ValueError:
        raise ValueError("Invalid media_db_path; must reside within the media DB root directory") from None

    return str(candidate_resolved)


async def _get_media_ids_marked_deleted(db_path: str) -> list[int]:
    db = create_media_database(client_id="embeddings_vector_compactor", db_path=db_path)
    try:
        cur = db.execute_query("SELECT id FROM Media WHERE deleted = 1")
        rows = cur.fetchall() or []
        return [int(r[0]) for r in rows]
    finally:
        try:
            db.close_connection()
        except _DB_CLOSE_EXCEPTIONS as e:
            logger.debug(f"Compactor: failed to close media DB connection: {e}")
        except Exception as e:
            logger.debug(f"Compactor: unexpected error closing media DB connection: {e}")


def _collection_name_for(user_id: str, media_id: int) -> str:
    return f"user_{user_id}_media_{media_id}"


async def compact_once(user_id: str, db_path: str | None = None) -> int:
    """Run a single compaction pass for the given user.

    Returns the number of collections touched.
    """
    touched = 0
    try:
        from tldw_Server_API.app.core.config import settings
        from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
    except Exception as e:  # pragma: no cover
        logger.error(f"Compactor initialization failed: {e}")
        return 0

    try:
        dbp = _sanitize_media_db_path(user_id, db_path)
    except ValueError as e:
        logger.error(f"Compactor received invalid media_db_path for user_id={user_id}: {e}")
        return 0

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
    except _CHROMA_CLOSE_EXCEPTIONS as e:
        logger.debug(f"Compactor: failed to close ChromaDB manager: {e}")
    except Exception as e:
        logger.debug(f"Compactor: unexpected error closing ChromaDB manager: {e}")
    return touched


async def run(stop_event: asyncio.Event | None = None) -> None:
    """Run the periodic compactor loop.

    Environment variables:
    - EMBEDDINGS_COMPACTOR_INTERVAL_SECONDS (default: 1800)
    - COMPACTOR_USER_ID (required in multi-user mode; defaults to SINGLE_USER_FIXED_ID in single-user)
    - MEDIA_DB_PATH (optional)
    """
    try:
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import is_single_user_mode
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    except Exception as e:  # pragma: no cover
        logger.error(f"Compactor settings load failed: {e}")
        return

    interval = int(os.getenv("EMBEDDINGS_COMPACTOR_INTERVAL_SECONDS", "1800") or 1800)
    user_id = os.getenv("COMPACTOR_USER_ID")
    if not user_id:
        if is_single_user_mode():
            user_id = str(DatabasePaths.get_single_user_id())
        else:
            logger.error("Compactor requires COMPACTOR_USER_ID in multi-user mode; exiting")
            return
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
