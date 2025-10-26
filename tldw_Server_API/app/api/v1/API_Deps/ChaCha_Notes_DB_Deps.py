# tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB_Deps.py
import asyncio
import os
import json
import threading
from pathlib import Path
from loguru import logger
from typing import Dict, Optional, List

from fastapi import Depends, HTTPException, status
import inspect
from cachetools import LRUCache
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
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Utils.Utils import get_project_root
#
#######################################################################################################################


# --- Configuration ---
_HAS_CACHETOOLS = True
DEFAULT_CHACHA_DB_SUBDIR = "chachanotes_user_dbs" # This will be a sub-directory within the user's main DB directory


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
        raise IOError(
            f"Could not initialize ChaChaNotes storage directory for user {user_id}."
        ) from e

    db_file = user_dir / DatabasePaths.CHACHA_DB_NAME
    # Extra safety: ensure parent exists even if upstream helpers change
    try:
        db_file.parent.mkdir(parents=True, exist_ok=True)
    except Exception as _mk_e:
        logger.debug(f"Parent ensure for ChaChaNotes path failed softly: { _mk_e }")
    logger.info(f"Ensured ChaChaNotes DB directory for user {user_id}: {db_file.parent}")
    return db_file

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
            return default_char['id']
        else:
            logger.info(f"Default character '{DEFAULT_CHARACTER_NAME}' not found. Creating now...")
            card_data = {
                'name': DEFAULT_CHARACTER_NAME,
                'description': DEFAULT_CHARACTER_DESCRIPTION,
                # All other fields will be None or default in the DB
                'personality': "Supportive, patient, and concise.",
                'scenario': "General assistance",
                'system_prompt': "You are a helpful AI assistant.",
                'image': None,
                'post_history_instructions': None,
                'first_message': "Hello! I'm your Helpful AI Assistant. How can I support you today?",
                'message_example': None,
                'creator_notes': "This character is automatically generated to provide a reliable default assistant persona.",
                'alternate_greetings': None,
                'tags': json.dumps(["default", "neutral", "assistant"]), # Store as JSON string
                'creator': "System",
                'character_version': "1.0",
                'extensions': None,
                'client_id': db_instance.client_id # Ensure client_id is set
            }
            # The add_character_card in CharactersRAGDB handles versioning and timestamps.
            char_id = db_instance.add_character_card(card_data)
            if char_id:
                logger.info(f"Successfully created default character '{DEFAULT_CHARACTER_NAME}' with ID: {char_id}.")
                return char_id
            else:
                # This should ideally not happen if add_character_card raises on failure
                logger.error(f"Failed to create default character '{DEFAULT_CHARACTER_NAME}'. add_character_card returned None.")
                return None
    except ConflictError as e: # Should only happen if get_character_card_by_name had an issue or race condition
        logger.warning(f"Conflict error while ensuring default character (likely race condition, re-fetching): {e}")
        # Re-fetch, as it might have been created by another thread.
        refetched_char = db_instance.get_character_card_by_name(DEFAULT_CHARACTER_NAME)
        if refetched_char:
            return refetched_char['id']
        logger.error(f"Still could not get/create default character after conflict: {e}")
        return None
    except (CharactersRAGDBError, SchemaError, InputError) as e:
        logger.error(f"Database error while ensuring default character '{DEFAULT_CHARACTER_NAME}': {e}", exc_info=True)
        return None # Indicate failure
    except Exception as e_gen:
        logger.error(f"Unexpected error while ensuring default character '{DEFAULT_CHARACTER_NAME}': {e_gen}", exc_info=True)
        return None

# --- Main Dependency Function ---

async def get_chacha_db_for_user(
        current_user: User = Depends(get_request_user)
) -> CharactersRAGDB:
    """
    FastAPI dependency to get the CharactersRAGDB instance for the identified user.
    Handles caching, initialization, and schema checks.
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="User identification failed for ChaChaNotes DB.")

    user_id = current_user.id
    base_dir = _resolve_main_user_base_dir()
    cache_key = f"{str(base_dir)}::{user_id}"
    db_instance: Optional[CharactersRAGDB] = None

    with _chacha_db_lock:  # Protects cache access
        db_instance = _chacha_db_instances.get(cache_key)

    if db_instance:
        try:
            # Perform a quick check to see if the connection is alive
            # This is a basic check; the CharactersRAGDB class handles more robust connection checks internally
            conn = db_instance.get_connection()
            conn.execute("SELECT 1")
            db_instance.ensure_character_tables_ready()
            logger.debug(f"Using cached and active ChaChaNotesDB instance for user_id: {user_id}")
            return db_instance
        except (CharactersRAGDBError, AttributeError, Exception) as e:  # Catch broader errors if connection is dead
            logger.warning(f"Cached ChaChaNotesDB instance for user {user_id} seems inactive ({e}). Re-initializing.")
            with _chacha_db_lock:  # Ensure exclusive access for removal
                if _chacha_db_instances.get(cache_key) is db_instance:  # ensure it's the same instance
                    _chacha_db_instances.pop(cache_key, None)
            db_instance = None  # Force re-initialization

    logger.info(f"No usable cached ChaChaNotesDB instance found for user_id: {user_id}. Initializing.")
    with _chacha_db_lock:  # Protects instance creation and cache update
        # Double-check cache in case another thread created it while waiting
        db_instance = _chacha_db_instances.get(cache_key)
        if db_instance:  # pragma: no cover
            logger.debug(f"ChaChaNotesDB instance for user {user_id} created concurrently by another thread.")
            return db_instance

        db_path: Optional[Path] = None
        try:
            db_path = _get_chacha_db_path_for_user(user_id)
            # Defensive: ensure directory exists in the exact resolved path
            try:
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            except Exception as _mk2:
                logger.debug(f"Secondary ensure for ChaChaNotes parent failed softly: {_mk2}")
            logger.info(f"Initializing CharactersRAGDB instance for user {user_id} at path: {db_path}")

            db_instance = CharactersRAGDB(db_path=str(db_path), client_id=str(current_user.id))

            # Ensure optional auxiliary table for message metadata (safe no-op if exists)
            try:
                db_instance.execute_query(
                    """
                    CREATE TABLE IF NOT EXISTS message_metadata(
                      message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                      tool_calls_json TEXT,
                      extra_json TEXT,
                      last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """,
                    script=False,
                    commit=True,
                )
            except Exception as _aux:
                logger.debug(f"Optional table ensure (message_metadata) skipped: {_aux}")

            # +++ Ensure default character exists after DB instance is created +++
            # Run synchronous function in thread pool to avoid blocking async context
            default_char_id = await asyncio.to_thread(_ensure_default_character, db_instance)
            if default_char_id is None:
                # This is a problem, the application might not function correctly without a default.
                logger.error(f"Failed to ensure default character for user {user_id}. This might impact functionality.")
                # Depending on strictness, you could raise an HTTPException here.
                # For now, we'll log and proceed, but chat saving might fail if it relies on this.

            _chacha_db_instances[cache_key] = db_instance
            logger.info(f"CharactersRAGDB instance created and cached successfully for user {user_id}")

        except (CharactersRAGDBError, SchemaError, InputError, ConflictError) as e:
            log_path_str = str(db_path) if db_path else f"directory for user_id {user_id}"
            logger.error(f"Failed to initialize CharactersRAGDB for user {user_id} at {log_path_str}: {e}",
                          exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not initialize character & notes database for user: {e}"
            ) from e
        except IOError as e:  # Catch error from _get_chacha_db_path_for_user
            logger.error(f"Failed to get CharactersRAGDB path for user {user_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            ) from e
        except Exception as e:
            log_path_str = str(db_path) if db_path else f"directory for user_id {user_id}"
            logger.error(f"Unexpected error initializing CharactersRAGDB for user {user_id} at {log_path_str}: {e}",
                          exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during character & notes database setup for user."
            ) from e
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

# Example of how to register for shutdown event in FastAPI:
# from fastapi import FastAPI
# app = FastAPI()
# @app.on_event("shutdown")
# async def shutdown_event():
#     close_all_chacha_db_instances()
#     # also close other DB instances if you have similar managers
