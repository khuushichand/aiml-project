# tldw_Server_API/app/api/v1/API_Deps/kanban_deps.py
"""
FastAPI dependency injection for Kanban database access.

Provides per-user KanbanDB instances with caching for performance.
"""
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from cachetools import LRUCache
from fastapi import Depends, HTTPException, status
from loguru import logger

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.DB_Management.Kanban_DB import (
    KanbanDB,
    KanbanDBError,
    InputError,
    ConflictError,
    NotFoundError,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


# --- Configuration ---
_KANBAN_EXECUTOR: Optional[ThreadPoolExecutor] = None
_KANBAN_EXECUTOR_SHUTDOWN: bool = False
_KANBAN_EXECUTOR_LOCK = threading.Lock()
_KANBAN_EXECUTOR_MAX_WORKERS = max(1, int(settings.get("KANBAN_EXECUTOR_MAX_WORKERS", "4")))
_KANBAN_INIT_TIMEOUT_SECS = float(settings.get("KANBAN_INIT_TIMEOUT_SECS", "5"))

# --- Global Cache for KanbanDB Instances ---
MAX_CACHED_KANBAN_DB_INSTANCES = int(settings.get("MAX_CACHED_KANBAN_DB_INSTANCES", "50"))
_kanban_db_instances: LRUCache = LRUCache(maxsize=MAX_CACHED_KANBAN_DB_INSTANCES)
_kanban_db_lock = threading.Lock()

# --- Health Tracking ---
_KANBAN_HEALTH_LOCK = threading.Lock()
_KANBAN_HEALTH: Dict[str, Any] = {
    "init_attempts": 0,
    "init_failures": 0,
    "last_init_ms": None,
    "last_error": None,
    "cached_instances": 0,
}


def _get_kanban_executor() -> ThreadPoolExecutor:
    """
    Return a live executor for Kanban DB work.

    Recreates the executor if it has been shut down.
    """
    global _KANBAN_EXECUTOR, _KANBAN_EXECUTOR_SHUTDOWN
    with _KANBAN_EXECUTOR_LOCK:
        if _KANBAN_EXECUTOR is None or _KANBAN_EXECUTOR_SHUTDOWN:
            _KANBAN_EXECUTOR = ThreadPoolExecutor(
                max_workers=_KANBAN_EXECUTOR_MAX_WORKERS,
                thread_name_prefix="kanban-db",
            )
            _KANBAN_EXECUTOR_SHUTDOWN = False
        return _KANBAN_EXECUTOR


def _record_init(duration_ms: float, success: bool, error: Optional[Exception] = None) -> None:
    """Record initialization metrics."""
    with _KANBAN_HEALTH_LOCK:
        _KANBAN_HEALTH["init_attempts"] += 1
        _KANBAN_HEALTH["last_init_ms"] = duration_ms
        _KANBAN_HEALTH["cached_instances"] = len(_kanban_db_instances)
        if success:
            _KANBAN_HEALTH["last_error"] = None
        else:
            _KANBAN_HEALTH["init_failures"] += 1
            _KANBAN_HEALTH["last_error"] = str(error) if error else "unknown error"


def get_kanban_health_snapshot() -> Dict[str, Any]:
    """Get current health metrics snapshot."""
    with _KANBAN_HEALTH_LOCK:
        return {
            "status": "degraded" if _KANBAN_HEALTH.get("init_failures") else "healthy",
            "init_attempts": _KANBAN_HEALTH.get("init_attempts"),
            "init_failures": _KANBAN_HEALTH.get("init_failures"),
            "last_init_ms": _KANBAN_HEALTH.get("last_init_ms"),
            "last_error": _KANBAN_HEALTH.get("last_error"),
            "cached_instances": len(_kanban_db_instances),
        }


def _create_kanban_db(user_id: int) -> KanbanDB:
    """
    Create a KanbanDB instance for a user.

    This runs in the executor thread pool.
    """
    db_path = DatabasePaths.get_kanban_db_path(user_id)
    logger.info(f"Initializing KanbanDB instance for user {user_id} at path: {db_path}")
    db_instance = KanbanDB(db_path=str(db_path), user_id=str(user_id))
    return db_instance


def _health_check_instance(db_instance: KanbanDB) -> bool:
    """Quick health check for a cached instance."""
    try:
        # Simple query to verify connection works
        db_instance.list_boards(limit=1)
        return True
    except Exception as e:
        logger.warning(f"Kanban health probe failed: {e}")
        return False


async def _is_instance_healthy(db_instance: KanbanDB) -> bool:
    """Async wrapper for health check."""
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_health_check_instance, db_instance),
            timeout=1.0,
        )
        return bool(result)
    except Exception:
        return False


async def _get_or_init_db_instance(user_id: int) -> KanbanDB:
    """
    Get or create a KanbanDB instance for a user.

    Uses caching with health checks to avoid returning stale instances.
    """
    cache_key = f"kanban::{user_id}"

    # Check cache first
    with _kanban_db_lock:
        db_instance = _kanban_db_instances.get(cache_key)

    if db_instance:
        if await _is_instance_healthy(db_instance):
            return db_instance
        logger.warning(f"Kanban cached instance unhealthy for user {user_id}; evicting and rebuilding.")
        with _kanban_db_lock:
            if _kanban_db_instances.get(cache_key) is db_instance:
                _kanban_db_instances.pop(cache_key, None)

    # Create new instance
    loop = asyncio.get_running_loop()
    start = time.perf_counter()
    try:
        db_instance = await asyncio.wait_for(
            loop.run_in_executor(_get_kanban_executor(), _create_kanban_db, user_id),
            timeout=_KANBAN_INIT_TIMEOUT_SECS,
        )
        duration_ms = (time.perf_counter() - start) * 1000
        _record_init(duration_ms, True)
        logger.debug(f"KanbanDB initialized for user {user_id} in {duration_ms:.2f}ms")
    except asyncio.TimeoutError as e:
        _record_init(_KANBAN_INIT_TIMEOUT_SECS * 1000, False, e)
        logger.error(f"Kanban DB initialization timed out for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kanban database initialization timed out",
        ) from e
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        _record_init(duration_ms, False, e)
        logger.error(f"Kanban DB initialization failed for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not initialize Kanban database for user: {e}",
        ) from e

    # Cache the instance
    with _kanban_db_lock:
        _kanban_db_instances[cache_key] = db_instance
        _KANBAN_HEALTH["cached_instances"] = len(_kanban_db_instances)

    return db_instance


async def get_kanban_db_for_user(current_user: User = Depends(get_request_user)) -> KanbanDB:
    """
    FastAPI dependency to get the KanbanDB instance for the authenticated user.

    Handles caching and health checks; initialization runs in a dedicated executor.

    Args:
        current_user: The authenticated user from the request.

    Returns:
        KanbanDB instance for the user.

    Raises:
        HTTPException: If user identification fails or DB initialization fails.
    """
    if not current_user or not isinstance(current_user.id, int):
        logger.error("get_kanban_db_for_user called without a valid User object or user.id is not int.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User identification failed for Kanban DB."
        )

    user_id = current_user.id
    return await _get_or_init_db_instance(user_id)


def close_all_kanban_db_instances() -> None:
    """
    Close all cached KanbanDB instances.

    Should be called during application shutdown.
    """
    with _kanban_db_lock:
        logger.info(f"Closing all cached KanbanDB instances ({len(_kanban_db_instances)})...")
        _kanban_db_instances.clear()
        logger.info("All KanbanDB instances closed and cache cleared.")


def shutdown_kanban_executor(wait: bool = False) -> None:
    """
    Shut down the Kanban executor to avoid lingering threads on shutdown.

    Args:
        wait: If True, block until all pending futures complete.
    """
    global _KANBAN_EXECUTOR, _KANBAN_EXECUTOR_SHUTDOWN
    with _KANBAN_EXECUTOR_LOCK:
        executor = _KANBAN_EXECUTOR
        _KANBAN_EXECUTOR = None
        _KANBAN_EXECUTOR_SHUTDOWN = True
    if executor is None:
        return
    try:
        executor.shutdown(wait=wait, cancel_futures=True)
        logger.info("Kanban executor shut down successfully.")
    except Exception as e:
        logger.debug(f"Kanban executor shutdown error: {e}")


# --- Exception Handlers (for use in endpoints) ---

def handle_kanban_db_error(e: Exception) -> HTTPException:
    """
    Convert KanbanDB exceptions to appropriate HTTP responses.

    Args:
        e: The exception to handle.

    Returns:
        HTTPException with appropriate status code.
    """
    if isinstance(e, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    elif isinstance(e, InputError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    elif isinstance(e, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    elif isinstance(e, KanbanDBError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    else:
        logger.error(f"Unexpected error in Kanban operation: {e}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )
