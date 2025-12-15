# tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB_Deps.py
import asyncio
import faulthandler
import inspect
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional, Set

from cachetools import LRUCache
from fastapi import Depends, HTTPException, status
from loguru import logger

#
#    logging.warning("cachetools not found. ChaChaNotes DB instance cache will grow indefinitely. "
#                    "Install with: pip install cachetools")
#
# Local Imports
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    SchemaError,
    InputError,
    ConflictError,
)
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Utils.Utils import get_project_root

#
#######################################################################################################################


# --- Configuration ---
_HAS_CACHETOOLS = True
DEFAULT_CHACHA_DB_SUBDIR = "chachanotes_user_dbs"  # This will be a sub-directory within the user's main DB directory
_CHACHA_EXECUTOR: ThreadPoolExecutor | None = None
_CHACHA_EXECUTOR_LOCK = threading.Lock()
_CHACHA_WATCHDOG_SECS = float(os.getenv("CHACHA_INIT_WATCHDOG_SECS", "5"))
_CHACHA_HEALTH_LOCK = threading.Lock()
_CHACHA_HEALTH: Dict[str, Any] = {
    "init_attempts": 0,
    "init_failures": 0,
    "last_init_ms": None,
    "last_error": None,
    "last_warn_dump": None,
    "cached_instances": 0,
    "default_char_ensures": 0,
    "default_char_failures": 0,
    "warm_startups": 0,
}


def _get_chacha_executor() -> ThreadPoolExecutor:
    """
    Return a live executor for ChaChaNotes DB work.

    The main FastAPI app shuts down this executor during application shutdown.
    In test suites, startup/shutdown can happen repeatedly within the same
    Python process; recreating the executor on-demand avoids order-dependent
    failures like "cannot schedule new futures after shutdown".
    """
    global _CHACHA_EXECUTOR
    with _CHACHA_EXECUTOR_LOCK:
        executor = _CHACHA_EXECUTOR
        if executor is None or getattr(executor, "_shutdown", False):
            _CHACHA_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chacha-db")
        return _CHACHA_EXECUTOR


def _normalise_user_base_path(raw_path: Path) -> Path:
    """
    Normalise a configured user database base path.

    Matches the behaviour used by DatabasePaths helpers: expand user home,
    resolve relative paths against the project root, and return an absolute Path.
    """
    try:
        candidate = raw_path.expanduser()
    except Exception:
        candidate = raw_path

    if not candidate.is_absolute():
        project_root = Path(get_project_root())
        candidate = (project_root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def _resolve_main_user_base_dir() -> Path:
    """Resolve the per-user databases base directory dynamically.

    Priority:
    1) Environment variable USER_DB_BASE_DIR (useful for tests)
    2) Project settings (config.txt via core.config)
    3) Emergency fallback path
    """
    env_base = os.environ.get("USER_DB_BASE_DIR")
    if env_base:
        try:
            return _normalise_user_base_path(Path(env_base))
        except Exception:
            pass
    base = settings.get("USER_DB_BASE_DIR")
    if base:
        try:
            return _normalise_user_base_path(Path(base))
        except Exception:
            pass
    logger.critical("CRITICAL: USER_DB_BASE_DIR is not configured in settings or environment. Using fallback.")
    return _normalise_user_base_path(Path("./app_data/user_databases_fallback"))


# USER_CHACHA_DB_BASE_DIR will now be defined *per user* inside _get_chacha_db_path_for_user
# We only need the main base directory here at the module level.


def _record_init(duration_ms: float, success: bool, error: Exception | None = None) -> None:
    with _CHACHA_HEALTH_LOCK:
        _CHACHA_HEALTH["init_attempts"] += 1
        _CHACHA_HEALTH["last_init_ms"] = duration_ms
        _CHACHA_HEALTH["cached_instances"] = len(_chacha_db_instances)
        if success:
            _CHACHA_HEALTH["last_error"] = None
        else:
            _CHACHA_HEALTH["init_failures"] += 1
            _CHACHA_HEALTH["last_error"] = str(error) if error else "unknown error"


def _record_default_character(success: bool) -> None:
    with _CHACHA_HEALTH_LOCK:
        if success:
            _CHACHA_HEALTH["default_char_ensures"] += 1
        else:
            _CHACHA_HEALTH["default_char_failures"] += 1


def _maybe_dump_traceback(reason: str) -> None:
    now = time.time()
    last_dump = _CHACHA_HEALTH.get("last_warn_dump")
    # Rate limit dumps to avoid log spam
    if last_dump and now - float(last_dump) < 300:
        return
    with _CHACHA_HEALTH_LOCK:
        _CHACHA_HEALTH["last_warn_dump"] = now
    try:
        logger.warning(f"ChaChaNotes watchdog dump triggered: {reason}")
        faulthandler.dump_traceback(file=sys.stderr)
    except Exception as dump_err:
        logger.debug(f"Faulthandler dump failed: {dump_err}")


def get_chacha_health_snapshot() -> Dict[str, Any]:
    status = "healthy"
    if _CHACHA_HEALTH.get("init_failures"):
        status = "degraded"
    return {
        "status": status,
        "init_attempts": _CHACHA_HEALTH.get("init_attempts"),
        "init_failures": _CHACHA_HEALTH.get("init_failures"),
        "last_init_ms": _CHACHA_HEALTH.get("last_init_ms"),
        "last_error": _CHACHA_HEALTH.get("last_error"),
        "cached_instances": len(_chacha_db_instances),
        "default_char_ensures": _CHACHA_HEALTH.get("default_char_ensures"),
        "default_char_failures": _CHACHA_HEALTH.get("default_char_failures"),
    }


def resolve_chacha_user_base_dir() -> Path:
    """Public helper to expose the resolved user database base directory."""
    return _resolve_main_user_base_dir()


SERVER_CLIENT_ID = settings.get("SERVER_CLIENT_ID")
if not SERVER_CLIENT_ID:
    logger.error("CRITICAL: SERVER_CLIENT_ID is not configured in settings.")
    SERVER_CLIENT_ID = "default_server_client_id"
    logger.warning(f"SERVER_CLIENT_ID not set, using placeholder: {SERVER_CLIENT_ID}")

# Global directory creation for a *common* ChaChaNotes base is removed
# as each user gets their DB under their own USER_DB_BASE_DIR/user_id/

# +++ Default Character Configuration +++
DEFAULT_CHARACTER_NAME = "Helpful AI Assistant"
DEFAULT_CHARACTER_DESCRIPTION = "A default, friendly assistant created automatically by the system."

# --- Global Cache for ChaChaNotes DB Instances ---
MAX_CACHED_CHACHA_DB_INSTANCES = settings.get("MAX_CACHED_CHACHA_DB_INSTANCES", 20)

if _HAS_CACHETOOLS:
    _chacha_db_instances: LRUCache = LRUCache(maxsize=MAX_CACHED_CHACHA_DB_INSTANCES)
    logger.info(f"Using LRUCache for ChaChaNotes DB instances (maxsize={MAX_CACHED_CHACHA_DB_INSTANCES}).")
else:
    _chacha_db_instances: Dict[str, CharactersRAGDB] = {}

_chacha_db_lock = threading.Lock()
_chacha_default_char_tasks: Set[asyncio.Task] = set()


#######################################################################################################################

# --- Helper Functions ---


def _get_chacha_db_path_for_user(user_id: int) -> Path:
    """
    Resolve the per-user ChaChaNotes DB path under the configured base.

    Policy: store each user's notes/chats DB at
      USER_DB_BASE_DIR / <user_id> / "ChaChaNotes.db"

    Notes:
    - USER_DB_BASE_DIR is read from global settings and can be overridden by env.
    - This per-user layout is intentional to isolate data and simplify backups.
    - A fallback path is used only when USER_DB_BASE_DIR is misconfigured; logs at CRITICAL/ERROR.
    """
    # Build path from the current effective base directory, preferring env override.
    base_dir = _resolve_main_user_base_dir()
    user_dir = Path(base_dir) / str(user_id)
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(
            f"Failed to create user directory for ChaChaNotes at {user_dir}: {e}",
            exc_info=True,
        )
        raise IOError(f"Could not initialize ChaChaNotes storage directory for user {user_id}.") from e

    db_file = user_dir / DatabasePaths.CHACHA_DB_NAME
    # Extra safety: ensure parent exists even if upstream helpers change
    try:
        db_file.parent.mkdir(parents=True, exist_ok=True)
    except Exception as _mk_e:
        logger.debug(f"Parent ensure for ChaChaNotes path failed softly: { _mk_e }")
    logger.info(f"Ensured ChaChaNotes DB directory for user {user_id}: {db_file.parent}")
    return db_file


def _apply_sqlite_tuning(db_instance: CharactersRAGDB) -> None:
    if db_instance.backend_type != BackendType.SQLITE:
        return
    try:
        conn = db_instance.get_connection()
        # Harden concurrency characteristics
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 10000")
    except Exception as e:
        logger.debug(f"ChaChaNotes tuning skipped: {e}")


def _health_check_instance(db_instance: CharactersRAGDB) -> bool:
    try:
        conn = db_instance.get_connection()
        conn.execute("PRAGMA busy_timeout = 1000")
        conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.warning(f"ChaChaNotes health probe failed: {e}")
        return False


def _create_and_prepare_db(user_id: int, client_id: str) -> CharactersRAGDB:
    db_path: Optional[Path] = None
    db_path = _get_chacha_db_path_for_user(user_id)
    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    except Exception as _mk2:
        logger.debug(f"Secondary ensure for ChaChaNotes parent failed softly: {_mk2}")
    logger.info(f"Initializing CharactersRAGDB instance for user {user_id} at path: {db_path}")
    db_instance = CharactersRAGDB(db_path=str(db_path), client_id=str(client_id))
    _apply_sqlite_tuning(db_instance)
    return db_instance


async def _ensure_default_character_async(db_instance: CharactersRAGDB, user_id: int) -> None:
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(_get_chacha_executor(), _ensure_default_character, db_instance),
            timeout=5,
        )
        _record_default_character(True)
    except asyncio.TimeoutError:
        _record_default_character(False)
        logger.warning(f"Timed out ensuring default character for user {user_id}; will retry on next access.")
    except Exception as e:
        _record_default_character(False)
        logger.warning(
            f"Error ensuring default character for user {user_id}: {e}. Continuing; will retry on next access.",
            exc_info=True,
        )


def _ensure_default_character(db_instance: CharactersRAGDB) -> Optional[int]:
    """
    Checks if the default character exists in the DB, creates it if not.
    Returns the character_id of the default character.
    """
    try:
        db_instance.ensure_character_tables_ready()
        default_char = db_instance.get_character_card_by_name(DEFAULT_CHARACTER_NAME)
        if default_char:
            logger.debug(f"Default character '{DEFAULT_CHARACTER_NAME}' already exists with ID: {default_char['id']}.")
            return default_char["id"]
        else:
            logger.info(f"Default character '{DEFAULT_CHARACTER_NAME}' not found. Creating now...")
            card_data = {
                "name": DEFAULT_CHARACTER_NAME,
                "description": DEFAULT_CHARACTER_DESCRIPTION,
                # All other fields will be None or default in the DB
                "personality": "Supportive, patient, and concise.",
                "scenario": "General assistance",
                "system_prompt": "You are a helpful AI assistant.",
                "image": None,
                "post_history_instructions": None,
                "first_message": "Hello! I'm your Helpful AI Assistant. How can I support you today?",
                "message_example": None,
                "creator_notes": "This character is automatically generated to provide a reliable default assistant persona.",
                "alternate_greetings": None,
                "tags": json.dumps(["default", "neutral", "assistant"]),  # Store as JSON string
                "creator": "System",
                "character_version": "1.0",
                "extensions": None,
                "client_id": db_instance.client_id,  # Ensure client_id is set
            }
            # The add_character_card in CharactersRAGDB handles versioning and timestamps.
            char_id = db_instance.add_character_card(card_data)
            if char_id:
                logger.info(f"Successfully created default character '{DEFAULT_CHARACTER_NAME}' with ID: {char_id}.")
                return char_id
            else:
                # This should ideally not happen if add_character_card raises on failure
                logger.error(
                    f"Failed to create default character '{DEFAULT_CHARACTER_NAME}'. add_character_card returned None."
                )
                return None
    except ConflictError as e:  # Should only happen if get_character_card_by_name had an issue or race condition
        logger.warning(f"Conflict error while ensuring default character (likely race condition, re-fetching): {e}")
        # Re-fetch, as it might have been created by another thread.
        refetched_char = db_instance.get_character_card_by_name(DEFAULT_CHARACTER_NAME)
        if refetched_char:
            return refetched_char["id"]
        logger.error(f"Still could not get/create default character after conflict: {e}")
        return None
    except (CharactersRAGDBError, SchemaError, InputError) as e:
        logger.error(f"Database error while ensuring default character '{DEFAULT_CHARACTER_NAME}': {e}", exc_info=True)
        return None  # Indicate failure
    except Exception as e_gen:
        logger.error(
            f"Unexpected error while ensuring default character '{DEFAULT_CHARACTER_NAME}': {e_gen}", exc_info=True
        )
        return None


async def _is_instance_healthy(db_instance: CharactersRAGDB) -> bool:
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_health_check_instance, db_instance),
            timeout=1.0,
        )
        return bool(result)
    except Exception:
        return False


async def _get_or_init_db_instance(user_id: int, client_id: str) -> CharactersRAGDB:
    base_dir = _resolve_main_user_base_dir()
    cache_key = f"{base_dir!s}::{user_id}"
    with _chacha_db_lock:
        db_instance = _chacha_db_instances.get(cache_key)
    if db_instance:
        if await _is_instance_healthy(db_instance):
            return db_instance
        logger.warning(f"ChaChaNotes cached instance unhealthy for user {user_id}; evicting and rebuilding.")
        with _chacha_db_lock:
            if _chacha_db_instances.get(cache_key) is db_instance:
                _chacha_db_instances.pop(cache_key, None)

    loop = asyncio.get_running_loop()
    start = time.perf_counter()
    try:
        db_instance = await asyncio.wait_for(
            loop.run_in_executor(_get_chacha_executor(), _create_and_prepare_db, user_id, client_id),
            timeout=max(_CHACHA_WATCHDOG_SECS * 3, 5),
        )
        duration_ms = (time.perf_counter() - start) * 1000
        _record_init(duration_ms, True)
        if duration_ms / 1000 > _CHACHA_WATCHDOG_SECS:
            _maybe_dump_traceback(f"ChaChaNotes init exceeded {_CHACHA_WATCHDOG_SECS}s for user {user_id}")
    except asyncio.TimeoutError as e:
        _record_init(_CHACHA_WATCHDOG_SECS * 1000, False, e)
        _maybe_dump_traceback(f"ChaChaNotes init timed out for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ChaChaNotes initialization timed out",
        ) from e
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        _record_init(duration_ms, False, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not initialize character & notes database for user: {e}",
        ) from e

    with _chacha_db_lock:
        _chacha_db_instances[cache_key] = db_instance
        _CHACHA_HEALTH["cached_instances"] = len(_chacha_db_instances)
    return db_instance


async def warm_chacha_db_for_user(user_id: int, client_id: str | None = None) -> None:
    try:
        db_instance = await _get_or_init_db_instance(user_id, client_id or str(user_id))
        _CHACHA_HEALTH["warm_startups"] += 1
        task = asyncio.create_task(_ensure_default_character_async(db_instance, user_id))
        _chacha_default_char_tasks.add(task)
        task.add_done_callback(_chacha_default_char_tasks.discard)
    except Exception as e:
        logger.warning(f"Warm-up for ChaChaNotes user {user_id} failed: {e}")


# --- Main Dependency Function ---


async def get_chacha_db_for_user(current_user: User = Depends(get_request_user)) -> CharactersRAGDB:
    """
    FastAPI dependency to get the CharactersRAGDB instance for the identified user.
    Handles caching and health checks; heavy initialization runs in a dedicated executor.
    """
    # Respect FastAPI dependency overrides explicitly if they exist.
    # Some test environments reset overrides aggressively; checking here ensures
    # we still honor an override bound to this callable.
    try:
        from tldw_Server_API.app.main import app as _app  # Local import to avoid import cycles at module load

        override_fn = _app.dependency_overrides.get(get_chacha_db_for_user)
        if override_fn is not None:
            try:
                result = override_fn()
                if inspect.isawaitable(result):
                    result = await result  # type: ignore[func-returns-value]
                if isinstance(result, CharactersRAGDB):
                    return result
            except Exception:
                # Fall back to standard resolution on any override execution issue
                pass
    except Exception:
        # If importing app or inspecting overrides fails, proceed normally
        pass

    logger.info("<<<<< ACTUAL get_chacha_db_for_user CALLED >>>>>")
    if not current_user or not isinstance(current_user.id, int):  # Ensure user_id is an int
        logger.error("get_chacha_db_for_user called without a valid User object or user.id is not int.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User identification failed for ChaChaNotes DB."
        )

    user_id = current_user.id
    db_instance = await _get_or_init_db_instance(user_id, str(current_user.id))
    task = asyncio.create_task(_ensure_default_character_async(db_instance, user_id))
    _chacha_default_char_tasks.add(task)
    task.add_done_callback(_chacha_default_char_tasks.discard)
    return db_instance


def close_all_chacha_db_instances():
    """Closes all cached ChaChaNotesDB connections. Useful for application shutdown."""
    with _chacha_db_lock:
        logger.info(f"Closing all cached ChaChaNotesDB instances ({len(_chacha_db_instances)})...")
        for user_id, db_instance in list(_chacha_db_instances.items()):
            try:
                db_instance.close_all_connections()
                logger.info(f"Closed ChaChaNotesDB instance for user {user_id}.")
            except Exception as e:
                logger.error(f"Error closing ChaChaNotesDB instance for user {user_id}: {e}", exc_info=True)
        _chacha_db_instances.clear()
        logger.info("All ChaChaNotesDB instances closed and cache cleared.")


def shutdown_chacha_executor(wait: bool = False) -> None:
    """Shut down the ChaChaNotes executor to avoid lingering threads on shutdown."""
    global _CHACHA_EXECUTOR
    with _CHACHA_EXECUTOR_LOCK:
        executor = _CHACHA_EXECUTOR
        _CHACHA_EXECUTOR = None
    if executor is None:
        return
    try:
        executor.shutdown(wait=wait, cancel_futures=True)
    except Exception as e:
        logger.debug(f"ChaChaNotes executor shutdown error: {e}")


# Example of how to register for shutdown event in FastAPI:
# from fastapi import FastAPI
# app = FastAPI()
# @app.on_event("shutdown")
# async def shutdown_event():
#     close_all_chacha_db_instances()
#     # also close other DB instances if you have similar managers
