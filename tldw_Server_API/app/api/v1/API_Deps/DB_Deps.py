# DB_Deps.py
# Description: Manages user-specific database instances based on application mode.
#
# Imports
import threading
import os
from pathlib import Path
from loguru import logger
from typing import Dict, Optional, AsyncGenerator

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
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
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
    base_dir_env = os.environ.get("USER_DB_BASE_DIR")
    # Test-mode safety: isolate user DBs to a per-process temp dir unless explicitly overridden
    if not base_dir_env and str(os.getenv("TESTING", "")).lower() in {"1", "true", "yes", "on"}:
        try:
            import tempfile
            run_tag = (
                os.getenv("TLDW_TEST_RUN_ID")
                or os.getenv("PYTEST_XDIST_WORKER")
                or "default"
            )
            safe_run_tag = "".join(
                ch if ch.isalnum() or ch in "-_." else "_"
                for ch in str(run_tag)
            )
            # Use project Databases/user_databases_test/<run_tag> to keep nearby but stable across processes
            project_root = settings.get("PROJECT_ROOT")  # type: ignore[attr-defined]
            if project_root:
                base_dir_env = str(
                    Path(project_root) / "Databases" / "user_databases_test" / safe_run_tag
                )
            else:
                base_dir_env = str(
                    Path(tempfile.gettempdir()) / "tldw_user_databases_test" / safe_run_tag
                )
            # Set env so subsequent calls use the same directory
            os.environ.setdefault("USER_DB_BASE_DIR", base_dir_env)
        except Exception as e:
            logger.warning(
                "TESTING mode: failed to derive project-root user DB dir; falling back to temp dir. Error: %s",
                e,
                exc_info=True,
            )
            run_tag = (
                os.getenv("TLDW_TEST_RUN_ID")
                or os.getenv("PYTEST_XDIST_WORKER")
                or "default"
            )
            safe_run_tag = "".join(
                ch if ch.isalnum() or ch in "-_." else "_"
                for ch in str(run_tag)
            )
            base_dir_env = str(
                Path(tempfile.gettempdir()) / "tldw_user_databases_test" / safe_run_tag
            )
            os.environ.setdefault("USER_DB_BASE_DIR", base_dir_env)
    try:
        return DatabasePaths.get_media_db_path(user_id)
    except Exception as e:
        logger.error(f"Could not resolve database directory for user_id {user_id}: {e}", exc_info=True)
        raise IOError(f"Could not initialize storage directory for user {user_id}.") from e

def _resolve_media_db_for_user(current_user: User) -> MediaDatabase:
    if not current_user or not isinstance(current_user.id, int):
        logger.error("get_media_db_for_user called without a valid User object/ID.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User identification failed.")

    user_id = current_user.id  # Will be SINGLE_USER_FIXED_ID in single-user mode
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
        logger.debug(f"Using cached Database instance for user_id: {user_id}")
        return db_instance

    # --- Instance Not Cached: Create New One ---
    logger.info(f"No cached DB instance found for user_id: {user_id}. Initializing.")
    with _user_db_lock:
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

        db_path: Optional[Path] = None
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
                db_instance = MediaDatabase(db_path=str(db_path), client_id=str(current_user.id))

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
        except IOError as e:
            logger.error(f"Failed to get DB path for user {user_id}: {e}", exc_info=True)
            raise HTTPException(
                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail=str(e)
             ) from e
        except Exception as e:
            log_path = db_path or f"directory for user_id {user_id}"
            logger.error(f"Unexpected error initializing database for user {user_id} at {log_path}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during database setup for user."
            ) from e

    try:
        scope = get_scope()
        if scope:
            db_instance.default_org_id = scope.effective_org_id
            db_instance.default_team_id = scope.effective_team_id
    except Exception:
        pass
    return db_instance


# --- Main Dependency Function ---

async def get_media_db_for_user(
    request: Request,
    current_user: User = Depends(get_request_user)
) -> AsyncGenerator[MediaDatabase, None]:
    db_instance = _resolve_media_db_for_user(current_user)
    try:
        yield db_instance
    finally:
        try:
            if hasattr(db_instance, "release_context_connection"):
                db_instance.release_context_connection()
        except Exception:
            pass


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
                    if hasattr(db, "release_context_connection"):
                        db.release_context_connection()
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
    request: Request,
    current_user: User = Depends(get_request_user),
) -> AsyncGenerator[Optional[MediaDatabase], None]:
    """
    Optional version of get_media_db_for_user for endpoints that can operate without DB.
    Returns None instead of raising on initialization failures.
    """
    db_instance: Optional[MediaDatabase] = None
    try:
        db_instance = _resolve_media_db_for_user(current_user)
    except HTTPException as e:
        if e.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
            raise
        logger.warning(f"Optional Media DB unavailable for user {getattr(current_user, 'id', '?')}: {e.detail}")
        yield None
        return
    except Exception as e:
        logger.warning(
            f"Optional Media DB unexpected error for user {getattr(current_user, 'id', '?')}: {e}",
            exc_info=True
        )
        yield None
        return
    try:
        yield db_instance
    finally:
        try:
            if db_instance and hasattr(db_instance, "release_context_connection"):
                db_instance.release_context_connection()
        except Exception:
            pass

#
# End of DB_Deps.py
########################################################################################################################
