# DB_Deps.py
# Description: Manages user-specific database instances based on application mode.
#
# Imports
import threading
import os
from pathlib import Path
from loguru import logger
from typing import Dict, Optional

# 3rd-party Libraries
from fastapi import Header, HTTPException, status, Depends, Request
try:
    from cachetools import LRUCache
    _HAS_CACHETOOLS = True
except ImportError:
    _HAS_CACHETOOLS = False
    logger.warning("cachetools not found. User DB instance cache will grow indefinitely. Install with: pip install cachetools")

# Local Imports
# Import the settings dictionary
from tldw_Server_API.app.core.config import settings
# Import the primary user identification dependency and User model
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
# Import the specific Database class
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase, DatabaseError, SchemaError # Adjust import path
from tldw_Server_API.app.core.DB_Management.scope_context import get_scope
from tldw_Server_API.app.core.DB_Management.DB_Manager import get_content_backend_instance
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType

#######################################################################################################################

# Note: Do not cache USER_DB_BASE_DIR at import time. Tests may set USER_DB_BASE_DIR
# via environment after module import. We will resolve it at request time in helpers.

# --- Global Cache for User DB Instances ---
MAX_CACHED_DB_INSTANCES = 100  # Adjust as needed

if _HAS_CACHETOOLS:
    # Keyed by user ID (int)
    _user_db_instances: LRUCache = LRUCache(maxsize=MAX_CACHED_DB_INSTANCES)
    logger.info(f"Using LRUCache for user DB instances (maxsize={MAX_CACHED_DB_INSTANCES}).")
else:
    # Keyed by user ID (int)
    _user_db_instances: Dict[int, MediaDatabase] = {} # Fallback to standard dict

_user_db_lock = threading.Lock() # Protects access to _user_db_instances

#######################################################################################################################

# --- Helper Functions ---

def _get_db_path_for_user(user_id: int) -> Path:
    """
    Determines the database file path for a given user ID.
    Ensures the user's specific directory exists.
    Uses USER_DB_BASE_DIR assigned from settings.
    """
    # user_id will be settings["SINGLE_USER_FIXED_ID"] in single-user mode
    user_dir_name = str(user_id)
    # Resolve base dir dynamically: prefer env override, then settings
    base_dir_env = os.environ.get("USER_DB_BASE_DIR")
    # Test-mode safety: isolate user DBs to a per-process temp dir unless explicitly overridden
    if not base_dir_env and str(os.getenv("TESTING", "")).lower() in {"1", "true", "yes", "on"}:
        try:
            import tempfile, time
            run_tag = f"pid{os.getpid()}"
            # Use project Databases/user_databases_test/<run_tag> to keep nearby but isolated
            project_root = settings.get("PROJECT_ROOT")  # type: ignore[attr-defined]
            if project_root:
                base_dir_env = str(Path(project_root) / "Databases" / "user_databases_test" / run_tag)
            else:
                base_dir_env = tempfile.mkdtemp(prefix="user_databases_test_")
            # Set env so subsequent calls use the same directory
            os.environ["USER_DB_BASE_DIR"] = base_dir_env
        except Exception:
            pass
    base_dir = Path(base_dir_env) if base_dir_env else Path(settings["USER_DB_BASE_DIR"])  # type: ignore[index]
    user_dir = base_dir / user_dir_name
    db_file = user_dir / "Media_DB_v2.db" # Using standard Media_DB_v2.db naming

    try:
        user_dir.mkdir(parents=True, exist_ok=True)
        # Optional: logging.debug(f"Ensured directory exists for user {user_id}: {user_dir}")
    except OSError as e:
        logger.error(f"Could not create database directory for user_id {user_id} at {user_dir}: {e}", exc_info=True)
        # Raise a standard exception to be caught by the main dependency
        raise IOError(f"Could not initialize storage directory for user {user_id}.") from e
    return db_file

# --- Main Dependency Function ---

async def get_media_db_for_user(
    request: Request,
    # Depends on the primary authentication/identification dependency
    current_user: User = Depends(get_request_user)
) -> MediaDatabase:
    """
    FastAPI dependency to get the Database instance for the identified user.

    Works in both single-user (using fixed ID from settings) and multi-user modes.
    Handles caching, initialization, and schema checks. Uses configuration
    values assigned from the 'settings' dictionary.

    Args:
        current_user: The User object (either fixed or fetched) provided by `get_request_user`.

    Returns:
        A Database instance connected to the appropriate user's database file.

    Raises:
        HTTPException: If authentication fails (handled by `get_request_user`),
                       or if the database cannot be initialized.
    """
    if not current_user or not isinstance(current_user.id, int):
        logger.error("get_media_db_for_user called without a valid User object/ID.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User identification failed.")

    user_id = current_user.id # Will be SINGLE_USER_FIXED_ID in single-user mode
    db_instance: Optional[MediaDatabase] = None
    backend_mode_hint = (os.getenv("CONTENT_DB_MODE") or str(settings.get("CONTENT_DB_BACKEND", "sqlite"))).strip().lower()
    require_shared_backend = backend_mode_hint in {"postgres", "postgresql"}

    try:
        shared_backend = get_content_backend_instance()
    except RuntimeError as exc:
        logger.error(f"Content backend initialization failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PostgreSQL content backend required but unavailable. Check server logs."
        ) from exc

    shared_backend_type = getattr(shared_backend, "backend_type", None)
    if require_shared_backend and shared_backend_type != BackendType.POSTGRESQL:
        logger.error("CONTENT_DB_MODE=postgres but shared backend is not PostgreSQL or missing.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PostgreSQL content backend required but unavailable. Check server configuration.",
        )

    use_shared_backend = shared_backend_type == BackendType.POSTGRESQL
    if require_shared_backend:
        use_shared_backend = True

    # --- Check Cache ---
    # Read lock implicitly handled by context manager
    with _user_db_lock:
        db_instance = _user_db_instances.get(user_id)
    # TEST_MODE: log cache hit/miss visibility for debugging
    try:
        if str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "on"}:
            logger.warning(
                f"TEST_MODE: DB_Deps cache {'hit' if db_instance else 'miss'} for user_id={user_id}"
            )
    except Exception:
        pass

    if db_instance:
        # Optional: Add connection check if needed, though Database class might handle it
        logger.debug(f"Using cached Database instance for user_id: {user_id}")
        return db_instance

    # --- Instance Not Cached: Create New One ---
    logger.info(f"No cached DB instance found for user_id: {user_id}. Initializing.")
    # Acquire write lock
    with _user_db_lock:
        # Double-check cache in case another thread created it while waiting
        db_instance = _user_db_instances.get(user_id)
        if db_instance:
            logger.debug(f"DB instance for user {user_id} created concurrently.")
            try:
                if str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "on"}:
                    _dbp = getattr(db_instance, 'db_path_str', getattr(db_instance, 'db_path', '?'))
                    logger.warning(f"TEST_MODE: DB_Deps returning concurrently-created cached instance user_id={user_id} db_path={_dbp}")
            except Exception:
                pass
            return db_instance

        # --- Get Path and Initialize ---
        db_path: Optional[Path] = None # Define scope for logging in except block
        try:
            if use_shared_backend:
                db_path = Path(":memory:")
                logger.info(f"Initializing Database instance for user {user_id} using shared Postgres backend")
                db_instance = MediaDatabase(
                    db_path=str(db_path),
                    client_id=str(current_user.id),
                    backend=shared_backend,
                )
            else:
                db_path = _get_db_path_for_user(user_id)
                logger.info(f"Initializing Database instance for user {user_id} at path: {db_path}")

                # Instantiate the Database class for the specific user ID's path
                # Use SERVER_CLIENT_ID assigned from settings dict
                db_instance = MediaDatabase(db_path=str(db_path), client_id=str(current_user.id))

            # --- Store in Cache ---
            _user_db_instances[user_id] = db_instance
            logger.info(f"Database instance created and cached successfully for user {user_id}")
            try:
                if str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "on"}:
                    _dbp = getattr(db_instance, 'db_path_str', getattr(db_instance, 'db_path', '?'))
                    logger.warning(f"TEST_MODE: DB_Deps cached new instance user_id={user_id} db_path={_dbp} shared_backend={use_shared_backend}")
            except Exception:
                pass

        except (DatabaseError, SchemaError) as e:
            log_path = db_path or f"directory for user_id {user_id}"
            logger.error(f"Failed to initialize database for user {user_id} at {log_path}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not initialize database for user: {e}"
            ) from e
        except IOError as e: # Catch error from _get_db_path_for_user
            logger.error(f"Failed to get DB path for user {user_id}: {e}", exc_info=True)
            raise HTTPException(
                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail=str(e) # Use the message from IOError
             ) from e
        except Exception as e:
            log_path = db_path or f"directory for user_id {user_id}"
            logger.error(f"Unexpected error initializing database for user {user_id} at {log_path}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred during database setup for user."
            ) from e

    # Return the newly created and cached instance
    try:
        scope = get_scope()
        if scope:
            db_instance.default_org_id = scope.effective_org_id
            db_instance.default_team_id = scope.effective_team_id
    except Exception:
        pass
    return db_instance


def reset_media_db_cache() -> None:
    """Clear cached MediaDatabase instances (useful for tests)."""
    with _user_db_lock:
        try:
            # Attempt to close outstanding connections for cache entries
            values_iter = (
                _user_db_instances.values()
                if hasattr(_user_db_instances, "values")
                else []  # type: ignore[assignment]
            )
            for db in list(values_iter):  # type: ignore[arg-type]
                try:
                    if hasattr(db, "close_connection"):
                        db.close_connection()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            _user_db_instances.clear()  # type: ignore[attr-defined]
        except Exception:
            pass


async def try_get_media_db_for_user(
    current_user: User = Depends(get_request_user)
) -> Optional[MediaDatabase]:
    """
    Optional version of get_media_db_for_user for endpoints that can operate without DB.
    Returns None instead of raising on initialization failures.
    """
    try:
        return await get_media_db_for_user(current_user=current_user)
    except HTTPException as e:
        logger.warning(f"Optional Media DB unavailable for user {getattr(current_user, 'id', '?')}: {e.detail}")
        return None
    except Exception as e:
        logger.warning(
            f"Optional Media DB unexpected error for user {getattr(current_user, 'id', '?')}: {e}",
            exc_info=True
        )
        return None

#
# End of DB_Deps.py
########################################################################################################################
