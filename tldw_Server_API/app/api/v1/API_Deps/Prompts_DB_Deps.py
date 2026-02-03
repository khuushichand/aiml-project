# tldw_Server_API/app/api/v1/API_Deps/Prompts_DB_Deps.py
#
# Imports
import asyncio
import os
import uuid as _uuid
from pathlib import Path
from typing import Optional

from cachetools import LRUCache  # Assuming cachetools is available

#
# Third-party imports
from fastapi import Depends, HTTPException, Request, status
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Prompt_Management.Prompts_Interop import (
    ConflictError,
    DatabaseError,
    InputError,
    PromptsDatabase,
    SchemaError,
)

#
# Local Imports

#
########################################################################################################################
#
# Functions:

# Back-compat for tests that patch this module-level path.
try:
    MAIN_USER_DATA_BASE_DIR = DatabasePaths.get_user_db_base_dir()
except Exception:
    MAIN_USER_DATA_BASE_DIR = None

# --- Configuration ---
SERVER_CLIENT_ID = settings.get("SERVER_CLIENT_ID")
if not SERVER_CLIENT_ID:
    SERVER_CLIENT_ID = "default_server_client_id_prompts" # Unique default
    logger.warning(f"SERVER_CLIENT_ID not set for prompts, using placeholder: {SERVER_CLIENT_ID}")

# --- Global Cache for Prompts DB Instances (managed by prompts_interop, but we track paths) ---
MAX_CACHED_PROMPTS_DB_INSTANCES = settings.get("MAX_CACHED_PROMPTS_DB_INSTANCES", 20)
_prompts_db_paths_cache: LRUCache = LRUCache(maxsize=MAX_CACHED_PROMPTS_DB_INSTANCES)
_prompts_cache_lock = asyncio.Lock()

# --- Helper Functions ---

def _get_prompts_db_path_for_user(user_id: int, salt: Optional[str] = None) -> Path:
    """
    Determines the Prompts database file path for a given user ID.
    Ensures the user's specific directory exists.
    Path: USER_DB_BASE_DIR / <user_id> / prompts_user_dbs / user_prompts_v2.sqlite
    When salt is provided: USER_DB_BASE_DIR / <user_id> / prompts_user_dbs / user_prompts_v2_{salt}.sqlite
    """
    db_file = DatabasePaths.get_prompts_db_path(user_id, salt=salt)
    logger.info(f"Ensured Prompts DB directory for user {user_id}: {db_file.parent}")
    return db_file

# --- Main Dependency Function ---

_user_db_instances: LRUCache | None = None
_user_db_locks: LRUCache | None = None


def _close_prompts_db_instance(
    cache_key: tuple[int, str],
    db_instance: PromptsDatabase,
    *,
    reason: str,
) -> None:
    try:
        db_instance.close_connection()
        logger.info(
            "Closed PromptsDatabase instance for cache_key=%s (reason=%s).",
            cache_key,
            reason,
        )
    except Exception as exc:
        logger.error(
            "Error closing PromptsDatabase instance for cache_key=%s (reason=%s): %s",
            cache_key,
            reason,
            exc,
            exc_info=True,
        )


def _on_prompts_db_eviction(cache_key: tuple[int, str], db_instance: PromptsDatabase) -> None:
    _close_prompts_db_instance(cache_key, db_instance, reason="evicted")
    if _user_db_locks is not None:
        _user_db_locks.pop(cache_key, None)


def _on_prompts_lock_eviction(cache_key: tuple[int, str], _lock: asyncio.Lock) -> None:
    if _user_db_instances is None:
        return
    db_instance = _user_db_instances.pop(cache_key, None)
    if db_instance:
        _close_prompts_db_instance(cache_key, db_instance, reason="lock-evicted")


class _EvictingLRUCache(LRUCache):
    def __init__(self, *args, on_evict=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_evict = on_evict

    def popitem(self):
        cache_key, value = super().popitem()
        if self._on_evict is not None:
            try:
                self._on_evict(cache_key, value)
            except Exception as exc:
                logger.error(
                    "Prompts DB cache eviction callback failed for %s: %s",
                    cache_key,
                    exc,
                    exc_info=True,
                )
        return cache_key, value


_user_db_instances = _EvictingLRUCache(
    maxsize=MAX_CACHED_PROMPTS_DB_INSTANCES,
    on_evict=_on_prompts_db_eviction,
)
_user_db_locks = _EvictingLRUCache(
    maxsize=MAX_CACHED_PROMPTS_DB_INSTANCES,
    on_evict=_on_prompts_lock_eviction,
)


def _is_db_instance_alive(db_instance: PromptsDatabase) -> bool:
    try:
        conn = db_instance.get_connection()
        conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def _create_prompts_db_instance(
    user_id: int,
    salt: Optional[str],
    client_id: str,
) -> tuple[PromptsDatabase, Path]:
    db_path = _get_prompts_db_path_for_user(user_id, salt=salt)
    db_instance = PromptsDatabase(db_path=str(db_path), client_id=client_id)
    return db_instance, db_path


async def get_prompts_db_for_user(
        current_user: User = Depends(get_request_user),
        request: Request = None
) -> PromptsDatabase:
    """
    FastAPI dependency to get the PromptsDatabase instance for the identified user,
    managed via the prompts_interop layer.
    """
    assert _user_db_instances is not None and _user_db_locks is not None
    # More robust check for User object and its id
    if not isinstance(current_user, User) or not hasattr(current_user, 'id') or not isinstance(current_user.id, int):
        logger.error(
            f"get_prompts_db_for_user called with an invalid User object. "
            f"Expected User model with int id. Got type: {type(current_user)}, value: {current_user}"
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="User identification failed for Prompts DB (Invalid User object).")

    user_id = current_user.id

    # In test mode, isolate DB per app instance to avoid cross-test conflicts
    salt = ""
    try:
        if os.environ.get("TEST_MODE", "").lower() == "true" and request is not None:
            if not hasattr(request.app.state, "prompts_db_salt"):
                setattr(request.app.state, "prompts_db_salt", _uuid.uuid4().hex)
            salt = str(getattr(request.app.state, "prompts_db_salt"))
    except Exception:
        salt = ""

    cache_key = (user_id, salt)

    # Get or create a lock for this specific user_id
    async with _prompts_cache_lock:
        user_specific_lock = _user_db_locks.get(cache_key)
        if user_specific_lock is None:
            user_specific_lock = asyncio.Lock()
        _user_db_locks[cache_key] = user_specific_lock

    async with user_specific_lock:
        # Check if an instance for this user_id already exists (cached for this request/app lifetime if persistent)
        # The prompts_interop itself doesn't manage multiple DBs, it manages ONE.
        # So, we need a way to tell prompts_interop WHICH db to use, or manage instances here.
        # Let's manage instances here and pass the db_path to prompts_interop.
        # This means prompts_interop's global _db_instance is less useful in a multi-user, multi-db context.
        #
        # REVISED APPROACH:
        # The `prompts_interop` as written manages a SINGLE global instance.
        # For a multi-user system where each user has their OWN DB, we cannot use
        # the interop's global instance directly.
        #
        # Option 1: Modify `prompts_interop` to NOT use a global singleton, but return instances. (More work)
        # Option 2: Instantiate `PromptsDatabase` directly here, and wrap its calls.
        #           This bypasses the benefit of the interop being a single point of call.
        # Option 3: (Chosen for simplicity given current interop)
        #           The interop layer is more of a "wrapper" for the DB methods.
        #           We will instantiate PromptsDatabase directly here, per user.
        #           The `prompts_interop.py` utility functions that take `db_instance` can still be used.
        #           The interop's own instance-based methods will be bypassed.

        async with _prompts_cache_lock:
            try:
                db_instance = _user_db_instances[cache_key]
            except KeyError:
                db_instance = None
        if db_instance:
            is_alive = await asyncio.to_thread(_is_db_instance_alive, db_instance)
            if is_alive:
                logger.debug(f"Using cached PromptsDatabase instance for user_id: {user_id}")
                async with _prompts_cache_lock:
                    _user_db_locks[cache_key] = user_specific_lock
                return db_instance
            logger.warning(f"Cached PromptsDatabase for user {user_id} inactive. Re-creating.")
            async with _prompts_cache_lock:
                _user_db_instances.pop(cache_key, None)
            await asyncio.to_thread(
                _close_prompts_db_instance,
                cache_key,
                db_instance,
                reason="inactive",
            )

        # If not cached or cache was bad, create a new one
        db_path: Optional[Path] = None
        try:
            # Call with positional args to be compatible with test monkeypatches
            db_instance, db_path = await asyncio.to_thread(
                _create_prompts_db_instance,
                user_id,
                salt or None,
                str(current_user.id),
            )
            logger.info(f"Initializing PromptsDatabase instance for user {user_id} at path: {db_path}")

            # Instantiate PromptsDatabase directly
            # The client_id for the PromptsDatabase should be the SERVER_CLIENT_ID,
            # as it's the server application making changes on behalf of the user.
            # If you need to track the specific end-user initiating the change,
            # that would be a different field, or SERVER_CLIENT_ID could be user-specific.
            # For now, using a global server client ID.
            async with _prompts_cache_lock:
                _user_db_instances[cache_key] = db_instance # Cache it for this user/app salt
                _user_db_locks[cache_key] = user_specific_lock
            logger.info(f"PromptsDatabase instance created and cached for user {user_id} (salt={salt or 'none'}) at {db_path}")
            return db_instance

        except (DatabaseError, SchemaError, InputError, ConflictError) as e:
            log_path_str = str(db_path) if db_path else f"directory for user_id {user_id}"
            logger.error(f"Failed to initialize PromptsDatabase for user {user_id} at {log_path_str}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not initialize prompts database for user: {str(e)}"
            ) from e
        except IOError as e:
            logger.error(f"Failed to get PromptsDatabase path for user {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
        except Exception as e:
            log_path_str = str(db_path) if db_path else f"directory for user_id {user_id}"
            logger.error(f"Unexpected error initializing PromptsDatabase for user {user_id} at {log_path_str}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during prompts database setup."
            ) from e


def close_all_cached_prompts_db_instances():
    """Closes all cached PromptsDatabase connections. Useful for application shutdown."""
    if _user_db_instances is None or _user_db_locks is None:
        return
    logger.info(f"Closing all cached PromptsDatabase instances ({len(_user_db_instances)})...")
    for cache_key, db_instance in list(_user_db_instances.items()):
        try:
            db_instance.close_connection() # PromptsDatabase handles its own thread-local connections
            logger.info(f"Closed PromptsDatabase connection for cache_key {cache_key}.")
        except Exception as e:
            logger.error(f"Error closing PromptsDatabase instance for cache_key {cache_key}: {e}", exc_info=True)
    _user_db_instances.clear()
    _user_db_locks.clear() # Clear user-specific locks as well
    logger.info("All PromptsDatabase instances cleared from cache and locks removed.")

# Register for shutdown in your main FastAPI app:
# @app.on_event("shutdown")
# async def shutdown_event():
#     close_all_cached_prompts_db_instances()

#
# End of Prompts_DB_Deps.py
########################################################################################################################
