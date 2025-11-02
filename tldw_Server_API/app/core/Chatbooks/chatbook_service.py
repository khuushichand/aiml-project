from __future__ import annotations
# chatbook_service.py
# Description: Service for creating and importing chatbooks with multi-user support
# Adapted from single-user to multi-user architecture
#
"""
Chatbook Service for Multi-User Environment
--------------------------------------------

Handles the creation, import, and export of chatbooks with user isolation.

Key Adaptations from Single-User:
- User-specific exports with access control
- Job-based operations for async processing
- Temporary storage with automatic cleanup
- Per-user database isolation
- No global state or singletons
"""

import base64
import json
import shutil
import zipfile
import hashlib
import asyncio
import aiofiles
import aiofiles.os
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set, Union
from typing import Dict as _Dict
from uuid import uuid4
from loguru import logger
from contextlib import asynccontextmanager

# Unified audit logging is handled at the API layer. The service no longer
# imports or depends on legacy audit loggers.

# Import custom exceptions
from .exceptions import (
    ChatbookException, ValidationError, FileOperationError,
    DatabaseError, QuotaExceededError, SecurityError,
    JobError, ImportError, ExportError, ArchiveError,
    ConflictError, TemporaryError, TimeoutError,
    is_retryable, get_retry_delay
)

# Legacy job queue shim removed; using in-process task registry

from .chatbook_models import (
    ChatbookManifest, ChatbookContent, ContentItem, ContentType,
    ChatbookVersion, Relationship, ExportJob, ImportJob,
    ExportStatus, ImportStatus, ConflictResolution, ImportConflict,
    ImportStatusData
)
from ..DB_Management.ChaChaNotes_DB import CharactersRAGDB
from ..DB_Management.db_path_utils import DatabasePaths

try:  # Prompts database is optional in some deployments
    from ..DB_Management.Prompts_DB import PromptsDatabase  # type: ignore
except Exception:  # pragma: no cover - defensive guard for stripped builds
    PromptsDatabase = None  # type: ignore

try:
    from ..DB_Management.Media_DB_v2 import (  # type: ignore
        MediaDatabase,
        get_media_transcripts,
        get_media_prompts,
    )
except Exception:  # pragma: no cover
    MediaDatabase = None  # type: ignore
    get_media_transcripts = None  # type: ignore
    get_media_prompts = None  # type: ignore

try:
    from ..DB_Management.Evaluations_DB import EvaluationsDatabase  # type: ignore
except Exception:  # pragma: no cover
    EvaluationsDatabase = None  # type: ignore


class ChatbookService:
    """Service for creating and importing chatbooks with user isolation."""

    def __init__(self, user_id: Union[str, int], db: CharactersRAGDB, user_id_int: Optional[int] = None):
        """
        Initialize the chatbook service for a specific user.

        Args:
            user_id: User identifier (string or integer)
            db: User's ChaChaNotes database instance
            user_id_int: Optional integer form of the user id for cross-database access
        """
        self.user_id_raw = user_id
        self.user_id = str(user_id)
        self.user_id_int: Optional[int] = user_id_int
        if self.user_id_int is None:
            try:
                self.user_id_int = int(self.user_id)
            except (TypeError, ValueError):
                self.user_id_int = None
        self.db = db

        # Track TODOs once per session so we comply with PRD while exposing gaps
        self._todo_messages: Set[str] = set()

        # In-process async task registry (best-effort cancellation)
        self._tasks: _Dict[str, asyncio.Task] = {}
        self._prompts_db: Optional["PromptsDatabase"] = None
        self._media_db: Optional["MediaDatabase"] = None
        self._evaluations_db: Optional["EvaluationsDatabase"] = None

        # Secure user-specific directory using application data path
        # Get base path from environment or use appropriate default
        import os
        import tempfile
        import re

        # Sanitize user_id to prevent path traversal
        # Only allow alphanumeric characters, hyphens, and underscores
        safe_user_id = re.sub(r'[^a-zA-Z0-9_-]', '_', str(self.user_id))
        # Remove any path separators or dangerous patterns
        safe_user_id = safe_user_id.replace('..', '_').replace('/', '_').replace('\\', '_')
        # Limit length to prevent excessively long paths
        safe_user_id = safe_user_id[:255]

        # Use environment variable, or temp dir for testing, or system default
        if os.environ.get('TLDW_USER_DATA_PATH'):
            base_data_dir = Path(os.environ.get('TLDW_USER_DATA_PATH'))
        elif os.environ.get('PYTEST_CURRENT_TEST') or os.environ.get('CI'):
            # Use temp directory during tests or CI
            base_data_dir = Path(tempfile.gettempdir()) / 'tldw_test_data'
        else:
            # Production default
            base_data_dir = Path('/var/lib/tldw/user_data')

        # Create secure user-specific directory with restricted permissions
        self.user_data_dir = base_data_dir / 'users' / safe_user_id / 'chatbooks'
        try:
            self.user_data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        except PermissionError:
            # Fallback to temp directory if system path is not writable
            base_data_dir = Path(tempfile.gettempdir()) / 'tldw_data'
            self.user_data_dir = base_data_dir / 'users' / safe_user_id / 'chatbooks'
            self.user_data_dir.mkdir(parents=True, exist_ok=True)

        # Separate directories for exports and imports
        self.export_dir = self.user_data_dir / 'exports'
        self.import_dir = self.user_data_dir / 'imports'
        self.temp_dir = self.user_data_dir / 'temp'

        for directory in [self.export_dir, self.import_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Jobs backend selection (domain override > module default), legacy flag supported
        backend = (os.getenv("CHATBOOKS_JOBS_BACKEND") or os.getenv("TLDW_JOBS_BACKEND") or "").strip().lower()
        legacy_ps_flag = str(os.getenv("TLDW_USE_PROMPT_STUDIO_QUEUE", "false")).lower() in {"1", "true", "yes"}
        if not backend:
            backend = "prompt_studio" if legacy_ps_flag else "core"
            if legacy_ps_flag:
                logger.warning("TLDW_USE_PROMPT_STUDIO_QUEUE is deprecated; use CHATBOOKS_JOBS_BACKEND=prompt_studio")
        self._jobs_backend = backend if backend in {"prompt_studio", "core"} else "core"

        # Optional Prompt Studio JobManager adapter
        self._ps_job_adapter = None
        self._jobs_db_path: Optional[Path] = None
        if self._jobs_backend == "prompt_studio":
            try:
                from .ps_job_adapter import ChatbooksPSJobAdapter
                self._ps_job_adapter = ChatbooksPSJobAdapter()
                logger.info("Chatbooks: Prompt Studio JobManager adapter enabled (backend=prompt_studio)")
            except Exception as exc:
                logger.warning(
                    f"Chatbooks: Failed to initialize PS Job adapter, falling back to core backend: {exc}"
                )
                self._jobs_backend = "core"
                self._ps_job_adapter = None
        if self._jobs_backend == "core":
            try:
                from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
                self._jobs_db_path = ensure_jobs_tables()
            except Exception as exc:
                logger.debug(f"Jobs core backend migrations skipped: {exc}")

        # Initialize job tracking tables
        self._init_job_tables()


    # -------------------------------------------------------------------------
    # Helper utilities (TODO markers ensure disparities with PRD are surfaced)
    # -------------------------------------------------------------------------
    def _note_todo(self, message: str) -> None:
        """Log a TODO item once to highlight parity gaps with the PRD."""
        if message not in self._todo_messages:
            logger.warning(f"TODO(chatbooks): {message}")
            self._todo_messages.add(message)

    def _get_prompts_db(self) -> Optional["PromptsDatabase"]:
        """Lazily initialize and cache the prompts database."""
        if PromptsDatabase is None:
            self._note_todo("Prompts export/import requires PromptsDatabase module; skipping for current build.")
            return None
        if self._prompts_db is not None:
            return self._prompts_db
        if self.user_id_int is None:
            self._note_todo("Prompts export/import requires numeric user id to resolve database path.")
            return None
        try:
            db_path = DatabasePaths.get_prompts_db_path(self.user_id_int)
            self._prompts_db = PromptsDatabase(db_path, client_id=self.user_id)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning(f"Failed to initialize PromptsDatabase for chatbooks export: {exc}")
            self._note_todo("Prompts export/import initialization failed; inspect logs for details.")
            self._prompts_db = None
        return self._prompts_db

    def _get_media_db(self) -> Optional["MediaDatabase"]:
        """Lazily initialize and cache the media database."""
        if MediaDatabase is None:
            self._note_todo("Media export/import requires MediaDatabase module; skipping media coverage.")
            return None
        if self._media_db is not None:
            return self._media_db
        if self.user_id_int is None:
            self._note_todo("Media export/import requires numeric user id to resolve database path.")
            return None
        try:
            db_path = DatabasePaths.get_media_db_path(self.user_id_int)
            self._media_db = MediaDatabase(db_path, client_id=self.user_id)
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Failed to initialize MediaDatabase for chatbooks export: {exc}")
            self._note_todo("Media export/import initialization failed; inspect logs for details.")
            self._media_db = None
        return self._media_db

    def _get_evaluations_db(self) -> Optional["EvaluationsDatabase"]:
        """Lazily initialize and cache the evaluations database."""
        if EvaluationsDatabase is None:
            self._note_todo("Evaluations export/import requires EvaluationsDatabase module; skipping evaluations coverage.")
            return None
        if self._evaluations_db is not None:
            return self._evaluations_db
        if self.user_id_int is None:
            self._note_todo("Evaluations export/import requires numeric user id to resolve database path.")
            return None
        try:
            db_path = DatabasePaths.get_evaluations_db_path(self.user_id_int)
            # EvaluationsDatabase handles backend resolution internally
            self._evaluations_db = EvaluationsDatabase(str(db_path))
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Failed to initialize EvaluationsDatabase for chatbooks export: {exc}")
            self._note_todo("Evaluations export/import initialization failed; inspect logs for details.")
            self._evaluations_db = None
        return self._evaluations_db

    @staticmethod
    def _normalize_datetime(value: Any) -> Any:
        """Convert datetime-like values to ISO strings."""
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        """Robust timestamp parser for database rows."""
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            try:
                # Treat numeric input as Unix timestamp (UTC)
                return datetime.utcfromtimestamp(value)
            except Exception:
                return None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            # Support trailing Z (UTC)
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(text)
                return ChatbookService._normalize_timestamp_to_naive(parsed)
            except ValueError:
                pass
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(text, fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _normalize_timestamp_to_naive(value: Optional[datetime]) -> Optional[datetime]:
        """Convert aware timestamps to naive UTC for consistent downstream handling."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def _normalize_prompt_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize prompt record for JSON export."""
        payload: Dict[str, Any] = {}
        for key, value in record.items():
            payload[key] = self._normalize_datetime(value)
        return payload

    def _fetch_media_record(self, media_db: "MediaDatabase", identifier: str) -> Optional[Dict[str, Any]]:
        """Retrieve a media row by integer id or uuid."""
        record: Optional[Dict[str, Any]] = None
        try:
            record = media_db.get_media_by_id(int(identifier))
        except Exception:
            record = None
        if not record:
            try:
                record = media_db.get_media_by_uuid(str(identifier))
            except Exception:
                record = None
        if record and isinstance(record, dict):
            return dict(record)
        return record

    def _normalize_media_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize media row for JSON export."""
        payload: Dict[str, Any] = {}
        for key, value in record.items():
            if key == "vector_embedding":
                # handled separately when include_embeddings is true
                continue
            if isinstance(value, (datetime,)):
                payload[key] = value.isoformat()
            elif isinstance(value, (bytes, bytearray, memoryview)):
                payload[key] = base64.b64encode(bytes(value)).decode("ascii")
            else:
                payload[key] = value
        return payload

    def _normalize_transcript_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize transcript row from Media DB helpers."""
        payload: Dict[str, Any] = {}
        for key, value in row.items():
            payload[key] = self._normalize_datetime(value)
        return payload

    def _normalize_evaluation_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize evaluation definition for export."""
        payload: Dict[str, Any] = {}
        for key, value in record.items():
            if key in {"eval_spec", "metadata"} and isinstance(value, str):
                try:
                    payload[key] = json.loads(value)
                    continue
                except json.JSONDecodeError:
                    pass
            payload[key] = self._normalize_datetime(value)
        return payload

    def _normalize_evaluation_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize evaluation run for export."""
        payload: Dict[str, Any] = {}
        for key, value in run.items():
            if key in {"config"} and isinstance(value, str):
                try:
                    payload[key] = json.loads(value)
                    continue
                except json.JSONDecodeError:
                    pass
            payload[key] = self._normalize_datetime(value)
        return payload

    @staticmethod
    def _extension_from_mime(mime_type: Optional[str]) -> str:
        """Infer a safe file extension for an attachment mime type."""
        if not mime_type:
            return ".bin"
        mapping = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif"
        }
        return mapping.get(mime_type.lower(), ".bin")

    def _fetch_results(self, cursor_or_list):
        """
        Helper to convert cursor or list to list of results.
        Handles both real database cursors and mocked list results.
        """
        if hasattr(cursor_or_list, 'fetchall'):
            # It's a cursor - fetch all results
            results = cursor_or_list.fetchall()
            if not results:
                return []

            # sqlite3.Row objects can be converted directly to dict
            # but we need to handle different cases
            first_row = results[0]

            # Try the simplest approach first - direct dict conversion
            try:
                # This works for sqlite3.Row objects
                return [dict(row) for row in results]
            except Exception:
                # If that fails, use cursor description
                if hasattr(cursor_or_list, 'description') and cursor_or_list.description:
                    columns = [desc[0] for desc in cursor_or_list.description]
                    return [dict(zip(columns, row)) for row in results]
                else:
                    # Can't convert to dict, return as tuples
                    return results
        else:
            # It's already a list (from mocked tests)
            return cursor_or_list

    def _get_conversation_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get conversation by name/title - wrapper for search method."""
        try:
            # First try FTS search
            if hasattr(self.db, 'search_conversations_by_title'):
                results = self.db.search_conversations_by_title(
                    name,
                    limit=10,
                    client_id=getattr(self.db, "client_id", None),
                )
                logger.debug(f"FTS search for conversation '{name}', found {len(results)} results")
                # Look for exact match
                for conv in results:
                    conv_title = conv.get('title')
                    conv_name = conv.get('name')
                    logger.debug(f"  Checking: title='{conv_title}', name='{conv_name}'")
                    if conv_title == name or conv_name == name:
                        logger.debug(f"  Found exact match via FTS!")
                        return conv

            # If FTS didn't find it, try direct query (FTS might not be updated yet)
            if hasattr(self.db, 'execute_query'):
                logger.debug(f"FTS failed, trying direct query for '{name}'")
                cursor = self.db.execute_query(
                    "SELECT * FROM conversations WHERE title = ? AND deleted = 0 LIMIT 1",
                    (name,)
                )
                # Fetch results from cursor
                if cursor:
                    results = cursor.fetchall() if hasattr(cursor, 'fetchall') else []
                    logger.debug(f"Direct query returned {len(results)} results")
                    if results and len(results) > 0:
                        logger.debug(f"Found conversation via direct query: {results[0]}")
                        # Convert tuple to dict if needed
                        if isinstance(results[0], tuple):
                            # Assume standard column order
                            return {'id': results[0][0], 'title': results[0][1] if len(results[0]) > 1 else name}
                        return results[0]
                else:
                    logger.debug(f"Direct query returned None/empty cursor")

            logger.debug(f"No match found for '{name}' via FTS or direct query")
            return None
        except Exception as e:
            logger.debug(f"Error searching for conversation by name: {e}")
            return None

    def _get_note_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Get note by title - wrapper for search method."""
        try:
            # First try FTS search
            if hasattr(self.db, 'search_notes'):
                results = self.db.search_notes(title, limit=10)
                logger.debug(f"FTS search for note '{title}', found {len(results)} results")
                # Look for exact match
                for note in results:
                    note_title = note.get('title')
                    logger.debug(f"  Checking note: title='{note_title}'")
                    if note_title == title:
                        logger.debug(f"  Found exact match via FTS!")
                        return note

            # If FTS didn't find it, try direct query (FTS might not be updated yet)
            if hasattr(self.db, 'execute_query'):
                logger.debug(f"FTS failed, trying direct query for note '{title}'")
                cursor = self.db.execute_query(
                    "SELECT * FROM notes WHERE title = ? AND deleted = 0 LIMIT 1",
                    (title,)
                )
                # Fetch results from cursor
                if cursor:
                    results = cursor.fetchall() if hasattr(cursor, 'fetchall') else []
                    logger.debug(f"Direct query returned {len(results)} results for note")
                    if results and len(results) > 0:
                        logger.debug(f"Found note via direct query: {results[0]}")
                        # Convert tuple to dict if needed
                        if isinstance(results[0], tuple):
                            # Assume standard column order
                            return {'id': results[0][0], 'title': results[0][1] if len(results[0]) > 1 else title}
                        return results[0]
                else:
                    logger.debug(f"Direct query returned None/empty cursor for note")

            logger.debug(f"No match found for note '{title}' via FTS or direct query")
            return None
        except Exception as e:
            logger.debug(f"Error searching for note by title: {e}")
            return None

    def _register_job_handlers(self):
        """No-op; legacy job queue handlers removed."""
        return

    def _init_job_tables(self):
        """Initialize database tables for job tracking."""
        try:
            # Export jobs table
            self.db.execute_query("""
                CREATE TABLE IF NOT EXISTS export_jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    chatbook_name TEXT NOT NULL,
                    output_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    progress_percentage INTEGER DEFAULT 0,
                    total_items INTEGER DEFAULT 0,
                    processed_items INTEGER DEFAULT 0,
                    file_size_bytes INTEGER,
                    download_url TEXT,
                    expires_at TIMESTAMP
                )
            """)

            # Import jobs table
            self.db.execute_query("""
                CREATE TABLE IF NOT EXISTS import_jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    chatbook_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    progress_percentage INTEGER DEFAULT 0,
                    total_items INTEGER DEFAULT 0,
                    processed_items INTEGER DEFAULT 0,
                    successful_items INTEGER DEFAULT 0,
                    failed_items INTEGER DEFAULT 0,
                    skipped_items INTEGER DEFAULT 0,
                    conflicts TEXT,  -- JSON array
                    warnings TEXT    -- JSON array
                )
            """)
        except Exception as e:
            logger.error(f"Error initializing job tables: {e}")

    # Alias for compatibility with tests
    async def export_chatbook(self, **kwargs):
        """Alias for create_chatbook to match test expectations."""
        # Extract user_id for internal use but don't pass it to create_chatbook
        user_id = kwargs.pop('user_id', None)

        # Extract chatbook_name and use it as 'name'
        if 'chatbook_name' in kwargs:
            kwargs['name'] = kwargs.pop('chatbook_name')

        # Extract options and merge them into kwargs
        if 'options' in kwargs:
            options = kwargs.pop('options')
            kwargs.update(options)

        # Map content_types to content_selections for compatibility
        if 'content_types' in kwargs:
            content_types = kwargs.pop('content_types')
            # Convert simple list to dict format
            content_selections = {}
            for ct in content_types:
                if ct == "conversations":
                    # Get all conversation IDs when none specified
                    conv_ids = []
                    try:
                        conversations = self.db.execute_query(
                            "SELECT id FROM conversations WHERE deleted = 0"
                        )
                        conv_ids = [c['id'] for c in conversations] if conversations else []
                    except Exception as e:
                        logger.debug(f"Error getting conversations: {e}")
                    content_selections[ContentType.CONVERSATION] = conv_ids
                elif ct == "characters":
                    # Get all character IDs when none specified
                    char_ids = []
                    try:
                        characters = self.db.execute_query(
                            "SELECT id FROM character_cards WHERE deleted = 0"
                        )
                        char_ids = [str(c['id']) for c in characters] if characters else []
                    except Exception as e:
                        logger.debug(f"Error getting characters: {e}")
                    content_selections[ContentType.CHARACTER] = char_ids
                elif ct == "notes":
                    # Get all note IDs when none specified
                    note_ids = []
                    try:
                        notes = self.db.execute_query(
                            "SELECT id FROM notes WHERE deleted = 0"
                        )
                        note_ids = [n['id'] for n in notes] if notes else []
                    except Exception as e:
                        logger.debug(f"Error getting notes: {e}")
                    content_selections[ContentType.NOTE] = note_ids
                elif ct == "world_books":
                    # Get all world book IDs when none specified
                    wb_ids = []
                    try:
                        if hasattr(self, 'world_books') and self.world_books:
                            world_books = self.world_books.list_world_books()
                            wb_ids = [str(wb['id']) for wb in world_books] if world_books else []
                        else:
                            # Fallback to direct database query
                            logger.debug("WorldBookService not available, using direct query")
                    except Exception as e:
                        logger.debug(f"Error getting world books: {e}")
                    content_selections[ContentType.WORLD_BOOK] = wb_ids
                elif ct == "dictionaries":
                    # Get all dictionary IDs when none specified
                    dict_ids = []
                    try:
                        if hasattr(self, 'dictionaries') and self.dictionaries:
                            dictionaries = self.dictionaries.list_dictionaries()
                            dict_ids = [str(d['id']) for d in dictionaries] if dictionaries else []
                        else:
                            # Fallback to direct database query
                            logger.debug("ChatDictionary not available, using direct query")
                    except Exception as e:
                        logger.debug(f"Error getting dictionaries: {e}")
                    content_selections[ContentType.DICTIONARY] = dict_ids
            kwargs['content_selections'] = content_selections

        # Set default values for required params if missing
        kwargs.setdefault('name', 'Test Export')
        kwargs.setdefault('description', 'Test Description')

        # Handle async_job parameter
        if 'async_job' in kwargs:
            kwargs['async_mode'] = kwargs.pop('async_job')

        result = await self.create_chatbook(**kwargs)

        # Convert tuple result to dict for tests
        if isinstance(result, tuple):
            success = result[0]
            message = result[1] if len(result) > 1 else ""
            payload = result[2] if len(result) > 2 else None
            is_async = bool(kwargs.get('async_mode'))
            file_path = None if is_async else payload
            job_id = payload if is_async else None
            content_summary: Dict[str, int] = {}

            # If we have a file path (sync export), read manifest to populate summary
            if file_path:
                try:
                    from zipfile import ZipFile
                    with ZipFile(file_path, 'r') as zf:
                        if 'manifest.json' in zf.namelist():
                            import json as _json
                            manifest_data = _json.loads(zf.read('manifest.json'))
                            # Pull totals from statistics (fallback to top-level for legacy manifests)
                            stats = manifest_data.get('statistics', {}) or {}
                            totals = {
                                'conversations': stats.get('total_conversations', manifest_data.get('total_conversations', 0)),
                                'notes': stats.get('total_notes', manifest_data.get('total_notes', 0)),
                                'characters': stats.get('total_characters', manifest_data.get('total_characters', 0)),
                                'world_books': stats.get('total_world_books', manifest_data.get('total_world_books', 0)),
                                'dictionaries': stats.get('total_dictionaries', manifest_data.get('total_dictionaries', 0)),
                                'documents': stats.get('total_documents', manifest_data.get('total_documents', 0)),
                            }
                            # Only include non-zero entries to keep it tidy
                            content_summary = {k: v for k, v in totals.items() if isinstance(v, int) and v >= 0}
                except Exception as _e:
                    # Fallback to empty summary on any error
                    logger.debug(f"Could not read manifest for content summary: {_e}")

            return {
                "success": success,
                "message": message,
                "file_path": file_path,
                "job_id": job_id,
                "status": "pending" if is_async else "completed",
                "content_summary": content_summary,
            }
        return result

    async def create_chatbook(
        self,
        name: str,
        description: str,
        content_selections: Dict[ContentType, List[str]],
        author: Optional[str] = None,
        include_media: bool = False,
        media_quality: str = "compressed",
        include_embeddings: bool = False,
        include_generated_content: bool = True,
        tags: List[str] = None,
        categories: List[str] = None,
        async_mode: bool = False,
        request_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Create a chatbook from selected content.

        Args:
            name: Chatbook name
            description: Chatbook description
            content_selections: Content to include by type and IDs
            author: Author name
            include_media: Include media files
            media_quality: Media quality level
            include_embeddings: Include embeddings
            include_generated_content: Include generated documents
            tags: Chatbook tags
            categories: Chatbook categories
            async_mode: Run as background job

        Returns:
            Tuple of (success, message, job_id or file_path)
        """
        if async_mode:
            # Create job and run asynchronously
            # If using Prompt Studio backend, create PS job first and reuse its id
            job_id = None
            if self._jobs_backend == "prompt_studio" and self._ps_job_adapter is not None:
                payload = {
                    "domain": "chatbooks",
                    "job_type": "export",
                    "user_id": self.user_id,
                    "name": name,
                    "include_media": include_media,
                    "include_embeddings": include_embeddings,
                    "include_generated_content": include_generated_content,
                    "tags": tags or [],
                    "categories": categories or [],
                }
                try:
                    ps_job = self._ps_job_adapter.create_export_job(payload, request_id=request_id)
                    if ps_job and ps_job.get("id") is not None:
                        job_id = str(ps_job["id"])  # mirror PS id
                except Exception:
                    job_id = None
            if job_id is None:
                job_id = str(uuid4())
            job = ExportJob(
                job_id=job_id,
                user_id=self.user_id,
                status=ExportStatus.PENDING,
                chatbook_name=name
            )

            # Store job in database
            self._save_export_job(job)

            # Start async processing depending on backend
            if self._jobs_backend == "core":
                # Enqueue into core Jobs and start worker if needed
                try:
                    from tldw_Server_API.app.core.Jobs.manager import JobManager
                    if not hasattr(self, "_core_jobs"):
                        self._core_jobs = JobManager()
                    payload = {
                        "action": "export",
                        "chatbooks_job_id": job_id,
                        "name": name,
                        "description": description,
                        "content_selections": {k.value if hasattr(k, 'value') else str(k): v for k, v in content_selections.items()},
                        "author": author,
                        "include_media": include_media,
                        "media_quality": media_quality,
                        "include_embeddings": include_embeddings,
                        "include_generated_content": include_generated_content,
                        "tags": tags or [],
                        "categories": categories or [],
                    }
                    self._core_jobs.create_job(
                        domain="chatbooks",
                        queue="default",
                        job_type="export",
                        payload=payload,
                        owner_user_id=self.user_id,
                        priority=5,
                        max_retries=3,
                        request_id=request_id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to enqueue export job into core Jobs: {e}")
            elif self._jobs_backend == "prompt_studio":
                # Do not start local processing when using Prompt Studio backend.
                # PS worker (external) is responsible for running the job.
                pass

            return True, f"Export job started: {job_id}", job_id
        else:
            # Run synchronously (wrapped in async)
            return await self._create_chatbook_sync_wrapper(
                name, description, content_selections,
                author, include_media, media_quality, include_embeddings,
                include_generated_content, tags, categories
            )

    def _with_transaction(self, func, *args, **kwargs):
        """Execute a function within a database transaction."""
        conn = None
        try:
            # Get connection and start transaction
            conn = self.db.get_connection() if hasattr(self.db, 'get_connection') else None
            if conn:
                conn.execute("BEGIN TRANSACTION")

            # Execute the function
            result = func(*args, **kwargs)

            # Commit if we have a connection
            if conn:
                conn.execute("COMMIT")

            return result

        except Exception as e:
            # Rollback on error
            if conn:
                try:
                    conn.execute("ROLLBACK")
                except Exception as e2:
                    logger.debug(f"Transaction rollback failed: error={e2}")
            logger.error(f"Transaction rolled back: {e}")
            raise
        finally:
            # Close connection
            if conn:
                try:
                    conn.close()
                except Exception as e3:
                    logger.debug(f"Connection close failed after transaction: error={e3}")

    async def _create_chatbook_sync_wrapper(
        self,
        name: str,
        description: str,
        content_selections: Dict[ContentType, List[str]],
        author: Optional[str] = None,
        include_media: bool = False,
        media_quality: str = "compressed",
        include_embeddings: bool = False,
        include_generated_content: bool = True,
        tags: List[str] = None,
        categories: List[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Wrapper for synchronous chatbook creation.

        Returns:
            Tuple of (success, message, file_path)
        """
        work_dir: Optional[Path] = None
        output_path: Optional[Path] = None
        success = False
        try:
            # Create working directory in secure temp location
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            work_dir = self.temp_dir / f"export_{timestamp}_{uuid4().hex[:8]}"
            work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

            # Initialize manifest
            manifest = ChatbookManifest(
                version=ChatbookVersion.V1,
                name=name,
                description=description,
                author=author,
                user_id=hashlib.sha256(self.user_id.encode()).hexdigest()[:16],  # Anonymized
                include_media=include_media,
                include_embeddings=include_embeddings,
                include_generated_content=include_generated_content,
                media_quality=media_quality,
                tags=tags or [],
                categories=categories or [],
                export_id=str(uuid4())
            )

            # Collect content
            content = ChatbookContent()

            # Process each content type
            if ContentType.CONVERSATION in content_selections:
                self._collect_conversations(
                    content_selections[ContentType.CONVERSATION],
                    work_dir, manifest, content
                )

            if ContentType.NOTE in content_selections:
                self._collect_notes(
                    content_selections[ContentType.NOTE],
                    work_dir, manifest, content
                )

            if ContentType.CHARACTER in content_selections:
                self._collect_characters(
                    content_selections[ContentType.CHARACTER],
                    work_dir, manifest, content
                )

            if ContentType.WORLD_BOOK in content_selections:
                self._collect_world_books(
                    content_selections[ContentType.WORLD_BOOK],
                    work_dir, manifest, content
                )

            if ContentType.DICTIONARY in content_selections:
                self._collect_dictionaries(
                    content_selections[ContentType.DICTIONARY],
                    work_dir, manifest, content
                )

            if ContentType.MEDIA in content_selections:
                self._collect_media_items(
                    content_selections[ContentType.MEDIA],
                    work_dir, manifest, content,
                    include_media=include_media,
                    include_embeddings=include_embeddings
                )

            if ContentType.PROMPT in content_selections:
                self._collect_prompts(
                    content_selections[ContentType.PROMPT],
                    work_dir, manifest, content
                )

            if ContentType.EVALUATION in content_selections:
                self._collect_evaluations(
                    content_selections[ContentType.EVALUATION],
                    work_dir, manifest, content
                )

            if ContentType.EMBEDDING in content_selections:
                self._note_todo(
                    "Explicit embedding exports are pending; embeddings are currently derived from media when include_embeddings=true."
                )

            if include_generated_content and ContentType.GENERATED_DOCUMENT in content_selections:
                self._collect_generated_documents(
                    content_selections[ContentType.GENERATED_DOCUMENT],
                    work_dir, manifest, content
                )

            # Update statistics
            manifest.total_conversations = len(content.conversations)
            manifest.total_notes = len(content.notes)
            manifest.total_characters = len(content.characters)
            manifest.total_media_items = len(content.media)
            manifest.total_prompts = len(content.prompts)
            manifest.total_evaluations = len(content.evaluations)
            manifest.total_embeddings = len(content.embeddings)
            manifest.total_world_books = len(content.world_books)
            manifest.total_dictionaries = len(content.dictionaries)
            manifest.total_documents = len(content.generated_documents)

            # Write manifest asynchronously
            manifest_path = work_dir / "manifest.json"
            async with aiofiles.open(manifest_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))

            # Create README asynchronously
            await self._create_readme_async(work_dir, manifest)

            # Create archive in secure export directory
            safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
            output_filename = f"{safe_name}_{timestamp}_{uuid4().hex[:8]}.zip"
            output_path = self.export_dir / output_filename
            await self._create_zip_archive_async(work_dir, output_path)

            # Update manifest with file size
            manifest.total_size_bytes = output_path.stat().st_size
            success = True

            # Store file path in job record (will be retrieved by job_id)
            # No direct filename access for security
            download_url = None  # Will be generated from job_id

            return True, f"Chatbook created successfully", str(output_path)

        except Exception as e:
            logger.error(f"Error creating chatbook: {e}")
            if output_path and output_path.exists():
                try:
                    await asyncio.to_thread(output_path.unlink)
                except Exception as cleanup_err:
                    logger.debug(f"Failed to remove partial archive {output_path}: {cleanup_err}")
            return False, f"Error creating chatbook: {str(e)}", None
        finally:
            if work_dir and work_dir.exists():
                try:
                    await asyncio.to_thread(shutil.rmtree, work_dir)
                except Exception as cleanup_err:
                    logger.debug(f"Failed to remove work directory {work_dir}: {cleanup_err}")

    async def _create_chatbook_job_async(
        self,
        job_id: str,
        name: str,
        description: str,
        content_selections: Dict[ContentType, List[str]],
        author: Optional[str],
        include_media: bool,
        media_quality: str,
        include_embeddings: bool,
        include_generated_content: bool,
        tags: List[str],
        categories: List[str]
    ):
        """
        Asynchronously create a chatbook with job tracking.
        """
        # Get job from database
        job = self._get_export_job(job_id)
        if not job:
            return

        try:
            # Update job status
            job.status = ExportStatus.IN_PROGRESS
            job.started_at = datetime.utcnow()
            self._save_export_job(job)
            # PS backend: reflect processing
            if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                try:
                    self._ps_job_adapter.update_status(int(job.job_id), "in_progress")
                except Exception:
                    pass

            # Create chatbook using the sync wrapper (could be made truly async)
            success, message, file_path = await self._create_chatbook_sync_wrapper(
                name, description, content_selections,
                author, include_media, media_quality, include_embeddings,
                include_generated_content, tags, categories
            )

            if success:
                # Update job with success; respect cancellation
                latest = self._get_export_job(job.job_id)
                if latest and latest.status == ExportStatus.CANCELLED:
                    # PS backend: reflect cancellation terminal state
                    if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                        try:
                            self._ps_job_adapter.update_status(int(job.job_id), "cancelled")
                        except Exception:
                            pass
                    return
                job.status = ExportStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                job.output_path = file_path
                job.file_size_bytes = Path(file_path).stat().st_size if file_path else None
                # Build (optionally signed) download URL and expiry
                ttl_seconds = int(os.getenv("CHATBOOKS_URL_TTL_SECONDS", "86400") or "86400")
                job.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
                job.download_url = self._build_download_url(job.job_id, job.expires_at)
            else:
                # Update job with failure
                job.status = ExportStatus.FAILED
                job.completed_at = datetime.utcnow()
                job.error_message = message
            # PS backend: reflect terminal state
            if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                try:
                    if job.status == ExportStatus.COMPLETED:
                        self._ps_job_adapter.update_status(int(job.job_id), "completed", result={"path": job.output_path})
                    elif job.status == ExportStatus.FAILED:
                        self._ps_job_adapter.update_status(int(job.job_id), "failed", error_message=job.error_message)
                except Exception:
                    pass
            self._save_export_job(job)

        except Exception as e:
            # Update job with error
            job.status = ExportStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            self._save_export_job(job)
            if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                try:
                    self._ps_job_adapter.update_status(int(job.job_id), "failed", error_message=str(e))
                except Exception:
                    pass

    async def import_chatbook(
        self,
        file_path: str,
        content_selections: Optional[Dict[ContentType, List[str]]] = None,
        conflict_resolution: Optional[Union[ConflictResolution, str]] = None,
        conflict_strategy: Optional[str] = None,  # Alias for conflict_resolution (for test compatibility)
        prefix_imported: bool = False,
        import_media: bool = True,
        import_embeddings: bool = False,
        async_mode: bool = False,
        request_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Import a chatbook.

        Args:
            file_path: Path to chatbook file
            content_selections: Specific content to import
            conflict_resolution: How to handle conflicts
            prefix_imported: Add prefix to imported items
            import_media: Import media files
            import_embeddings: Import embeddings
            async_mode: Run as background job

        Returns:
            Tuple of (success, message, job_id or None)
        """
        # Handle both conflict_resolution and conflict_strategy (for test compatibility)
        if conflict_strategy and not conflict_resolution:
            conflict_resolution = conflict_strategy

        # Convert string to enum if needed
        if isinstance(conflict_resolution, str):
            try:
                conflict_resolution = ConflictResolution(conflict_resolution)
            except (ValueError, KeyError):
                # Default to skip if invalid value provided
                conflict_resolution = ConflictResolution.SKIP
        elif conflict_resolution is None:
            # Default to skip if not specified
            conflict_resolution = ConflictResolution.SKIP

        if async_mode:
            # Create job and run asynchronously
            job_id = None
            if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                payload = {
                    "domain": "chatbooks",
                    "job_type": "import",
                    "user_id": self.user_id,
                    "path": file_path,
                    "import_media": import_media,
                    "import_embeddings": import_embeddings,
                    "conflict_resolution": str(conflict_resolution.value if hasattr(conflict_resolution, 'value') else conflict_resolution),
                }
                try:
                    ps_job = self._ps_job_adapter.create_import_job(payload, request_id=request_id)
                    if ps_job and ps_job.get("id") is not None:
                        job_id = str(ps_job["id"])  # mirror PS id
                except Exception:
                    job_id = None
            if job_id is None:
                job_id = str(uuid4())
            job = ImportJob(
                job_id=job_id,
                user_id=self.user_id,
                status=ImportStatus.PENDING,
                chatbook_path=file_path
            )

            # Store job in database
            self._save_import_job(job)

            # Start async task
            if self._jobs_backend == "core":
                try:
                    from tldw_Server_API.app.core.Jobs.manager import JobManager
                    if not hasattr(self, "_core_jobs"):
                        self._core_jobs = JobManager()
                    payload = {
                        "action": "import",
                        "chatbooks_job_id": job_id,
                        "file_path": file_path,
                        "content_selections": {k.value if hasattr(k, 'value') else str(k): v for k, v in (content_selections or {}).items()},
                        "conflict_resolution": conflict_resolution.value if hasattr(conflict_resolution, 'value') else str(conflict_resolution),
                        "prefix_imported": bool(prefix_imported),
                        "import_media": bool(import_media),
                        "import_embeddings": bool(import_embeddings),
                    }
                    self._core_jobs.create_job(
                        domain="chatbooks",
                        queue="default",
                        job_type="import",
                        payload=payload,
                        owner_user_id=self.user_id,
                        priority=5,
                        max_retries=3,
                        request_id=request_id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to enqueue import job into core Jobs: {e}")
            else:
                task = asyncio.create_task(self._import_chatbook_async(
                    job_id, file_path, content_selections,
                    conflict_resolution, prefix_imported,
                    import_media, import_embeddings
                ))
                self._tasks[job_id] = task
                task.add_done_callback(lambda _t: self._tasks.pop(job_id, None))

            return True, f"Import job started: {job_id}", job_id
        else:
            # Run synchronously (wrapped in executor for async compatibility)
            return await asyncio.to_thread(
                self._import_chatbook_sync,
                file_path, content_selections,
                conflict_resolution, prefix_imported,
                import_media, import_embeddings
            )

    def _import_chatbook_sync(
        self,
        file_path: str,
        content_selections: Optional[Dict[ContentType, List[str]]],
        conflict_resolution: ConflictResolution,
        prefix_imported: bool,
        import_media: bool,
        import_embeddings: bool
    ) -> Tuple[bool, str, None]:
        """
        Synchronously import a chatbook.
        """
        extract_dir: Optional[Path] = None
        try:
            # Validate file first via centralized validator
            from .chatbook_validators import ChatbookValidator
            ok, err = ChatbookValidator.validate_zip_file(file_path)
            if not ok:
                # Surface specific validator detail while keeping consistent prefix
                detail = err or "Invalid or potentially malicious archive file"
                if isinstance(detail, str) and detail.lower().startswith("file does not exist"):
                    detail = "Invalid or potentially malicious archive file"
                return False, f"Error: {detail}", None

            # Extract chatbook to secure temp location
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extract_dir = self.temp_dir / f"import_{timestamp}_{uuid4().hex[:8]}"
            extract_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

            # Extract archive with size limits
            with zipfile.ZipFile(file_path, 'r') as zf:
                # Check total uncompressed size
                total_size = sum(zinfo.file_size for zinfo in zf.filelist)
                if total_size > 500 * 1024 * 1024:  # 500MB limit
                    return False, "Archive too large (>500MB uncompressed)", None

                # Extract with path validation
                for member in zf.namelist():
                    # Normalize and validate the path
                    normalized_path = os.path.normpath(member)
                    if os.path.isabs(normalized_path) or ".." in normalized_path or normalized_path.startswith("/"):
                        return False, f"Unsafe path in archive: {member}", None

                    # Additional check: ensure the path stays within extract_dir
                    target_path = os.path.join(extract_dir, member)
                    real_extract_dir = os.path.realpath(extract_dir)
                    real_target = os.path.realpath(os.path.dirname(target_path))
                    if not real_target.startswith(real_extract_dir):
                        return False, f"Path traversal attempt detected: {member}", None

                    # Extract individual file safely
                    zf.extract(member, extract_dir)

            # Load manifest
            manifest_path = extract_dir / "manifest.json"
            if not manifest_path.exists():
                return False, "Error: Invalid chatbook - manifest.json not found", None

            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)

            manifest = ChatbookManifest.from_dict(manifest_data)

            # Check version compatibility
            if manifest.version != ChatbookVersion.V1:
                logger.warning(f"Chatbook version {manifest.version.value} may not be fully compatible")

            # Set up content selections if not provided
            if content_selections is None:
                content_selections = {}
                for item in manifest.content_items:
                    if item.type not in content_selections:
                        content_selections[item.type] = []
                    content_selections[item.type].append(item.id)

            # Import each content type
            import_status = ImportJob(
                job_id="temp",
                user_id=self.user_id,
                status=ImportStatus.IN_PROGRESS,
                chatbook_path=file_path
            )

            import_status.total_items = sum(len(ids) for ids in content_selections.values())

            # Import characters first (they may be dependencies)
            if ContentType.CHARACTER in content_selections:
                self._import_characters(
                    extract_dir, manifest,
                    content_selections[ContentType.CHARACTER],
                    conflict_resolution, prefix_imported,
                    import_status
                )

            # Import world books
            if ContentType.WORLD_BOOK in content_selections:
                self._import_world_books(
                    extract_dir, manifest,
                    content_selections[ContentType.WORLD_BOOK],
                    conflict_resolution, prefix_imported,
                    import_status
                )

            # Import dictionaries
            if ContentType.DICTIONARY in content_selections:
                self._import_dictionaries(
                    extract_dir, manifest,
                    content_selections[ContentType.DICTIONARY],
                    conflict_resolution, prefix_imported,
                    import_status
                )

            # Import conversations
            if ContentType.CONVERSATION in content_selections:
                self._import_conversations(
                    extract_dir, manifest,
                    content_selections[ContentType.CONVERSATION],
                    conflict_resolution, prefix_imported,
                    import_status
                )

            # Import notes
            if ContentType.NOTE in content_selections:
                self._import_notes(
                    extract_dir, manifest,
                    content_selections[ContentType.NOTE],
                    conflict_resolution, prefix_imported,
                    import_status
                )

            # Note: We do NOT delete the original import file - the caller owns it

            # Build result message
            logger.debug(f"Import status: total={import_status.total_items}, successful={import_status.successful_items}, skipped={import_status.skipped_items}, failed={import_status.failed_items}")

            if import_status.successful_items > 0:
                message = f"Successfully imported {import_status.successful_items}/{import_status.total_items} items"
                if import_status.skipped_items > 0:
                    message += f" ({import_status.skipped_items} skipped)"
                return True, message, None
            elif import_status.total_items == 0:
                # No items to import is not an error
                return True, "Import completed: No items to import", None
            elif import_status.skipped_items > 0:
                # All items were skipped (e.g., due to conflicts)
                return True, f"Import completed: All {import_status.skipped_items} items were skipped", None
            else:
                logger.debug(f"Import failed: No items were successfully imported or skipped")
                return False, "No items were imported", None

        except Exception as e:
            logger.error(f"Error importing chatbook: {e}")
            return False, f"Error importing chatbook: {str(e)}", None
        finally:
            if extract_dir and extract_dir.exists():
                shutil.rmtree(extract_dir, ignore_errors=True)

    async def _import_chatbook_async(
        self,
        job_id: str,
        file_path: str,
        content_selections: Optional[Dict[ContentType, List[str]]],
        conflict_resolution: ConflictResolution,
        prefix_imported: bool,
        import_media: bool,
        import_embeddings: bool
    ):
        """
        Asynchronously import a chatbook.
        """
        # Get job from database
        job = self._get_import_job(job_id)
        if not job:
            return

        try:
            # Update job status
            job.status = ImportStatus.IN_PROGRESS
            job.started_at = datetime.utcnow()
            self._save_import_job(job)
            if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                try:
                    self._ps_job_adapter.update_status(int(job.job_id), "in_progress")
                except Exception:
                    pass

            # Import chatbook synchronously using thread pool
            success, message, _ = await asyncio.to_thread(
                self._import_chatbook_sync,
                file_path, content_selections,
                conflict_resolution, prefix_imported,
                import_media, import_embeddings
            )

            if success:
                latest = self._get_import_job(job.job_id)
                if latest and latest.status == ImportStatus.CANCELLED:
                    if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                        try:
                            self._ps_job_adapter.update_status(int(job.job_id), "cancelled")
                        except Exception:
                            pass
                    return
                job.status = ImportStatus.COMPLETED
            else:
                job.status = ImportStatus.FAILED
                job.error_message = message

            job.completed_at = datetime.utcnow()
            self._save_import_job(job)
            if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                try:
                    if job.status == ImportStatus.COMPLETED:
                        self._ps_job_adapter.update_status(int(job.job_id), "completed")
                    elif job.status == ImportStatus.FAILED:
                        self._ps_job_adapter.update_status(int(job.job_id), "failed", error_message=job.error_message)
                except Exception:
                    pass

        except Exception as e:
            job.status = ImportStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            self._save_import_job(job)
            if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                try:
                    self._ps_job_adapter.update_status(int(job.job_id), "failed", error_message=str(e))
                except Exception:
                    pass
        finally:
            # Ensure original import archive is removed for async mode
            try:
                fp = Path(file_path)
                if fp.exists() and fp.is_file():
                    fp.unlink()
            except Exception as _e:
                logger.debug(f"Could not remove import archive (async) {file_path}: {_e}")

    def preview_chatbook(self, file_path: str) -> Tuple[Optional[ChatbookManifest], Optional[str]]:
        """
        Preview a chatbook without importing it.

        Args:
            file_path: Path to chatbook file

        Returns:
            Tuple of (manifest, error_message)
        """
        extract_dir: Optional[Path] = None
        try:
            # Defense-in-depth: validate the archive before extraction
            try:
                from .chatbook_validators import ChatbookValidator
                ok, err = ChatbookValidator.validate_zip_file(file_path)
                if not ok:
                    return None, err or "Invalid archive"
            except Exception:
                # If validator import fails, continue with cautious extraction guards
                pass
            # Extract to temporary directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extract_dir = self.temp_dir / f"preview_{timestamp}"

            # Extract archive with path validation
            with zipfile.ZipFile(file_path, 'r') as zf:
                # Validate all paths before extraction to prevent path traversal
                for member in zf.namelist():
                    # Normalize and validate the path
                    normalized_path = os.path.normpath(member)
                    if os.path.isabs(normalized_path) or ".." in normalized_path or normalized_path.startswith("/"):
                        return None, f"Unsafe path in archive: {member}"

                    # Additional check: ensure the path stays within extract_dir
                    target_path = os.path.join(extract_dir, member)
                    real_extract_dir = os.path.realpath(extract_dir)
                    real_target = os.path.realpath(os.path.dirname(target_path))
                    if not real_target.startswith(real_extract_dir):
                        return None, f"Path traversal attempt detected: {member}"

                # Safe to extract after validation
                zf.extractall(extract_dir)

            # Load manifest
            manifest_path = extract_dir / "manifest.json"
            if not manifest_path.exists():
                return None, "Invalid chatbook: manifest.json not found"

            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)

            manifest = ChatbookManifest.from_dict(manifest_data)

            return manifest, None

        except Exception as e:
            logger.error(f"Error previewing chatbook: {e}")
            return None, f"Error previewing chatbook: {str(e)}"
        finally:
            if extract_dir and extract_dir.exists():
                shutil.rmtree(extract_dir, ignore_errors=True)

    def _build_download_url(self, job_id: str, expires_at: Optional[datetime]) -> str:
        """Build a (possibly signed) download URL for a job."""
        base = f"/api/v1/chatbooks/download/{job_id}"
        use_signed = str(os.getenv("CHATBOOKS_SIGNED_URLS", "false")).lower() in {"1","true","yes"}
        secret = os.getenv("CHATBOOKS_SIGNING_SECRET", "")
        if use_signed and secret and expires_at:
            import hmac, hashlib
            exp = int(expires_at.timestamp())
            msg = f"{job_id}:{exp}".encode("utf-8")
            sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
            return f"{base}?exp={exp}&token={sig}"
        return base

    async def _core_worker_loop(self):
        """Background loop to process Chatbooks jobs from core Jobs manager for this user."""
        try:
            from tldw_Server_API.app.core.Jobs.manager import JobManager
        except Exception:
            logger.debug("Core Jobs manager unavailable; worker not started")
            return
        jm = getattr(self, "_core_jobs", None)
        if jm is None:
            jm = JobManager()
            self._core_jobs = jm
        worker_id = f"cb-worker-{self.user_id}"
        while True:
            try:
                job = jm.acquire_next_job(
                    domain="chatbooks", queue="default", lease_seconds=60, worker_id=worker_id, owner_user_id=self.user_id
                )
                if not job:
                    await asyncio.sleep(1)
                    continue
                lease_id = str(job.get("lease_id")) if job.get("lease_id") else None
                payload = job.get("payload") or {}
                action = payload.get("action")
                chatbooks_job_id = payload.get("chatbooks_job_id")
                if action == "export":
                    # Update Chatbooks job row to in_progress
                    ej = self._get_export_job(chatbooks_job_id)
                    if ej:
                        ej.status = ExportStatus.IN_PROGRESS
                        ej.started_at = datetime.utcnow()
                        self._save_export_job(ej)
                    # run export
                    cs = {}
                    for k, v in (payload.get("content_selections") or {}).items():
                        try:
                            cs[ContentType(k)] = v
                        except Exception:
                            pass
                    ok, msg, file_path = await self._create_chatbook_sync_wrapper(
                        name=payload.get("name"),
                        description=payload.get("description"),
                        content_selections=cs,
                        author=payload.get("author"),
                        include_media=bool(payload.get("include_media")),
                        media_quality=str(payload.get("media_quality", "compressed")),
                        include_embeddings=bool(payload.get("include_embeddings")),
                        include_generated_content=bool(payload.get("include_generated_content", True)),
                        tags=payload.get("tags") or [],
                        categories=payload.get("categories") or [],
                    )
                    if ok:
                        ej = self._get_export_job(chatbooks_job_id)
                        if ej and ej.status != ExportStatus.CANCELLED:
                            ej.status = ExportStatus.COMPLETED
                            ej.completed_at = datetime.utcnow()
                            ej.output_path = file_path
                            try:
                                ej.file_size_bytes = Path(file_path).stat().st_size if file_path else None
                            except Exception:
                                pass
                            ttl_seconds = int(os.getenv("CHATBOOKS_URL_TTL_SECONDS", "86400") or "86400")
                            ej.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
                            ej.download_url = self._build_download_url(ej.job_id, ej.expires_at)
                            self._save_export_job(ej)
                        jm.complete_job(
                            int(job["id"]),
                            result={"path": file_path},
                            worker_id=worker_id,
                            lease_id=lease_id,
                            completion_token=lease_id,
                        )
                    else:
                        ej = self._get_export_job(chatbooks_job_id)
                        if ej:
                            ej.status = ExportStatus.FAILED
                            ej.completed_at = datetime.utcnow()
                            ej.error_message = msg
                            self._save_export_job(ej)
                        jm.fail_job(
                            int(job["id"]),
                            error=str(msg),
                            retryable=False,
                            worker_id=worker_id,
                            lease_id=lease_id,
                            completion_token=lease_id,
                        )
                elif action == "import":
                    ij = self._get_import_job(chatbooks_job_id)
                    if ij:
                        ij.status = ImportStatus.IN_PROGRESS
                        ij.started_at = datetime.utcnow()
                        self._save_import_job(ij)
                    # reconstruct selections
                    cs = {}
                    for k, v in (payload.get("content_selections") or {}).items():
                        try:
                            cs[ContentType(k)] = v
                        except Exception:
                            pass
                    ok, msg, _ = await asyncio.to_thread(
                        self._import_chatbook_sync,
                        payload.get("file_path"), cs,
                        ConflictResolution(payload.get("conflict_resolution", "skip")),
                        bool(payload.get("prefix_imported", False)),
                        bool(payload.get("import_media", True)),
                        bool(payload.get("import_embeddings", False)),
                    )
                    ij = self._get_import_job(chatbooks_job_id)
                    if ok:
                        if ij and ij.status != ImportStatus.CANCELLED:
                            ij.status = ImportStatus.COMPLETED
                            ij.completed_at = datetime.utcnow()
                            self._save_import_job(ij)
                        jm.complete_job(
                            int(job["id"]),
                            worker_id=worker_id,
                            lease_id=lease_id,
                            completion_token=lease_id,
                        )
                    else:
                        if ij:
                            ij.status = ImportStatus.FAILED
                            ij.completed_at = datetime.utcnow()
                            ij.error_message = msg
                            self._save_import_job(ij)
                        jm.fail_job(
                            int(job["id"]),
                            error=str(msg),
                            retryable=False,
                            worker_id=worker_id,
                            lease_id=lease_id,
                            completion_token=lease_id,
                        )
                else:
                    jm.fail_job(
                        int(job["id"]),
                        error="unknown action",
                        retryable=False,
                        worker_id=worker_id,
                        lease_id=lease_id,
                        completion_token=lease_id,
                    )
            except Exception as e:
                logger.error(f"Core worker error: {e}")
                await asyncio.sleep(1)

    def get_export_job(self, job_id: str) -> Optional[ExportJob]:
        """Get export job status."""
        job = self._get_export_job(job_id)
        # If using PS backend, reflect PS status for live view
        if job and getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
            try:
                ps_id = int(job_id)
                ps_job = self._ps_job_adapter.get(ps_id)
                if ps_job and isinstance(ps_job, dict):
                    ps_status = str(ps_job.get("status", "")).lower()
                    status_map = {
                        "queued": ExportStatus.PENDING,
                        "processing": ExportStatus.IN_PROGRESS,
                        "completed": ExportStatus.COMPLETED,
                        "failed": ExportStatus.FAILED,
                        "cancelled": ExportStatus.CANCELLED,
                    }
                    mapped = status_map.get(ps_status)
                    if mapped and job.status not in {ExportStatus.COMPLETED, ExportStatus.FAILED}:
                        job.status = mapped
            except Exception:
                pass
        return job

    def get_import_job(self, job_id: str) -> Optional[ImportJob]:
        """Get import job status."""
        job = self._get_import_job(job_id)
        if job and getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
            try:
                ps_id = int(job_id)
                ps_job = self._ps_job_adapter.get(ps_id)
                if ps_job and isinstance(ps_job, dict):
                    ps_status = str(ps_job.get("status", "")).lower()
                    status_map = {
                        "queued": ImportStatus.PENDING,
                        "processing": ImportStatus.IN_PROGRESS,
                        "completed": ImportStatus.COMPLETED,
                        "failed": ImportStatus.FAILED,
                        "cancelled": ImportStatus.CANCELLED,
                    }
                    mapped = status_map.get(ps_status)
                    if mapped and job.status not in {ImportStatus.COMPLETED, ImportStatus.FAILED}:
                        job.status = mapped
            except Exception:
                pass
        return job

    def list_export_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[ExportJob]:
        """List all export jobs for this user."""
        try:
            cursor = self.db.execute_query(
                "SELECT * FROM export_jobs WHERE user_id = ? ORDER BY created_at DESC",
                (self.user_id,)
            )

            # Fetch results from cursor
            results = self._fetch_results(cursor)

            if not results:
                return []

            jobs: List[ExportJob] = []
            for row in results:
                # Handle both dict and tuple formats (for test compatibility)
                if isinstance(row, dict):
                    # Parse timestamps if they're strings
                    def parse_ts(ts):
                        if ts is None:
                            return None
                        if isinstance(ts, datetime):
                            return ts
                        if isinstance(ts, str):
                            if 'T' in ts:
                                return datetime.fromisoformat(ts)
                            else:
                                return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S.%f')
                        return ts

                    job = ExportJob(
                        job_id=row['job_id'],
                        user_id=row['user_id'],
                        status=ExportStatus(row['status']),
                        chatbook_name=row['chatbook_name'],
                        output_path=row['output_path'],
                        created_at=parse_ts(row['created_at']),
                        started_at=parse_ts(row['started_at']),
                        completed_at=parse_ts(row['completed_at']),
                        error_message=row['error_message'],
                        progress_percentage=row['progress_percentage'] or 0,
                        total_items=row['total_items'] or 0,
                        processed_items=row['processed_items'] or 0,
                        file_size_bytes=row['file_size_bytes'],
                        download_url=row['download_url'],
                        expires_at=parse_ts(row['expires_at']),
                        metadata={}  # Initialize empty metadata
                    )
                else:
                    # Handle tuple format from mocked tests
                    # (job_id, user_id, status, chatbook_name, output_path, created_at,
                    #  started_at, completed_at, error_message, progress_percentage,
                    #  total_items, processed_items, file_size_bytes, download_url, expires_at)
                    job = ExportJob(
                        job_id=row[0],
                        user_id=row[1],
                        status=ExportStatus(row[2]),
                        chatbook_name=row[3],
                        output_path=row[4],
                        created_at=datetime.fromisoformat(row[5]) if row[5] else None,
                        started_at=datetime.fromisoformat(row[6]) if row[6] else None,
                        completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                        error_message=row[8] if len(row) > 8 else None,
                        progress_percentage=row[9] if len(row) > 9 else 0,
                        total_items=row[10] if len(row) > 10 else 0,
                        processed_items=row[11] if len(row) > 11 else 0,
                        file_size_bytes=row[12] if len(row) > 12 else 0,
                        download_url=row[13] if len(row) > 13 else None,
                        expires_at=datetime.fromisoformat(row[14]) if len(row) > 14 and row[14] else None,
                        metadata={}  # Initialize empty metadata
                    )
                # Reflect PS status if applicable
                if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                    try:
                        ps_id = int(job.job_id)
                        ps_job = self._ps_job_adapter.get(ps_id)
                        if ps_job and isinstance(ps_job, dict):
                            ps_status = str(ps_job.get("status", "")).lower()
                            status_map = {
                                "queued": ExportStatus.PENDING,
                                "processing": ExportStatus.IN_PROGRESS,
                                "completed": ExportStatus.COMPLETED,
                                "failed": ExportStatus.FAILED,
                                "cancelled": ExportStatus.CANCELLED,
                            }
                            mapped = status_map.get(ps_status)
                            if mapped and job.status not in {ExportStatus.COMPLETED, ExportStatus.FAILED}:
                                job.status = mapped
                    except Exception:
                        pass
                jobs.append(job)

            return jobs
        except Exception as e:
            logger.error(f"Error listing export jobs: {e}")
            return []
    def list_import_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[ImportJob]:
        """List all import jobs for this user."""
        try:
            cursor = self.db.execute_query(
                "SELECT * FROM import_jobs WHERE user_id = ? ORDER BY created_at DESC",
                (self.user_id,)
            )

            # Fetch results from cursor
            results = self._fetch_results(cursor)

            if not results:
                return []

            jobs: List[ImportJob] = []
            for row in results:
                # Handle both dict and tuple formats (for test compatibility)
                if isinstance(row, dict):
                    # Parse timestamps if they're strings
                    def parse_ts(ts):
                        if ts is None:
                            return None
                        if isinstance(ts, datetime):
                            return ts
                        if isinstance(ts, str):
                            if 'T' in ts:
                                return datetime.fromisoformat(ts)
                            else:
                                return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S.%f')
                        return ts

                    job = ImportJob(
                        job_id=row['job_id'],
                        user_id=row['user_id'],
                        status=ImportStatus(row['status']),
                        chatbook_path=row['chatbook_path'],
                        created_at=parse_ts(row['created_at']),
                        started_at=parse_ts(row['started_at']),
                        completed_at=parse_ts(row['completed_at']),
                        error_message=row['error_message'],
                        progress_percentage=row['progress_percentage'] or 0,
                        total_items=row['total_items'] or 0,
                        processed_items=row['processed_items'] or 0,
                        successful_items=row['successful_items'] or 0,
                        failed_items=row['failed_items'] or 0,
                        skipped_items=row['skipped_items'] or 0,
                        conflicts=json.loads(row['conflicts']) if row['conflicts'] else [],
                        warnings=json.loads(row['warnings']) if row['warnings'] else []
                    )
                else:
                    # Handle tuple format from mocked tests
                    # (job_id, user_id, status, chatbook_path, created_at, started_at,
                    #  completed_at, error_message, progress_percentage, total_items,
                    #  processed_items, successful_items, failed_items, skipped_items,
                    #  conflicts, warnings)
                    job = ImportJob(
                        job_id=row[0],
                        user_id=row[1],
                        status=ImportStatus(row[2]),
                        chatbook_path=row[3],
                        created_at=datetime.fromisoformat(row[4]) if row[4] else None,
                        started_at=datetime.fromisoformat(row[5]) if row[5] else None,
                        completed_at=datetime.fromisoformat(row[6]) if row[6] else None,
                        error_message=row[7] if len(row) > 7 else None,
                        progress_percentage=row[8] if len(row) > 8 else 0,
                        total_items=row[9] if len(row) > 9 else 0,
                        processed_items=row[10] if len(row) > 10 else 0,
                        successful_items=row[11] if len(row) > 11 else 0,
                        failed_items=row[12] if len(row) > 12 else 0,
                        skipped_items=row[13] if len(row) > 13 else 0,
                        conflicts=json.loads(row[14]) if len(row) > 14 and row[14] else [],
                        warnings=json.loads(row[15]) if len(row) > 15 and row[15] else []
                    )
                if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
                    try:
                        ps_id = int(job.job_id)
                        ps_job = self._ps_job_adapter.get(ps_id)
                        if ps_job and isinstance(ps_job, dict):
                            ps_status = str(ps_job.get("status", "")).lower()
                            status_map = {
                                "queued": ImportStatus.PENDING,
                                "processing": ImportStatus.IN_PROGRESS,
                                "completed": ImportStatus.COMPLETED,
                                "failed": ImportStatus.FAILED,
                                "cancelled": ImportStatus.CANCELLED,
                            }
                            mapped = status_map.get(ps_status)
                            if mapped and job.status not in {ImportStatus.COMPLETED, ImportStatus.FAILED}:
                                job.status = mapped
                    except Exception:
                        pass
                jobs.append(job)

            return jobs
        except Exception as e:
            logger.error(f"Error listing import jobs: {e}")
            return []

    def cleanup_expired_exports(self) -> int:
        """Clean up expired export files. Returns number of files deleted."""
        try:
            # Get expired jobs
            now = datetime.utcnow()
            cursor = self.db.execute_query(
                "SELECT * FROM export_jobs WHERE user_id = ? AND expires_at < ? AND status = ?",
                (self.user_id, now.isoformat(), ExportStatus.COMPLETED.value)
            )
            results = self._fetch_results(cursor)

            if not results:
                return 0

            deleted_count = 0
            for row in results:
                # Support both dict and tuple rows
                if isinstance(row, dict):
                    output_path = row.get('output_path')
                    job_id = row.get('job_id')
                else:
                    # tuple field order: job_id, user_id, status, chatbook_name, output_path, ...
                    output_path = row[4] if len(row) > 4 else None
                    job_id = row[0]

                if output_path and Path(output_path).exists():
                    try:
                        Path(output_path).unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Error deleting expired export: {e}")

                # Update job status
                try:
                    self.db.execute_query(
                        "UPDATE export_jobs SET status = ? WHERE job_id = ?",
                        ('expired', job_id)
                    )
                except Exception as _e:
                    logger.debug(f"Failed to mark job {job_id} expired: {_e}")

            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up expired exports: {e}")
            return 0

    def _collect_prompts(
        self,
        prompt_ids: List[str],
        work_dir: Path,
        manifest: ChatbookManifest,
        content: ChatbookContent
    ) -> None:
        """Collect Prompt Studio prompts for export."""
        if not prompt_ids:
            return
        prompts_db = self._get_prompts_db()
        if prompts_db is None:
            logger.debug("Skipping prompt export because prompts DB is unavailable.")
            return
        prompts_dir = work_dir / "content" / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        for prompt_identifier in prompt_ids:
            prompt_record: Optional[Dict[str, Any]] = None
            # Attempt ID lookup (int) first, then UUID
            try:
                prompt_record = prompts_db.get_prompt_by_id(int(prompt_identifier))
            except Exception:
                prompt_record = None
            if not prompt_record:
                try:
                    prompt_record = prompts_db.get_prompt_by_uuid(str(prompt_identifier))
                except Exception:
                    prompt_record = None
            if not prompt_record:
                logger.debug(f"Prompt {prompt_identifier} not found; skipping.")
                continue

            prompt_payload = self._normalize_prompt_record(dict(prompt_record))
            prompt_id = str(prompt_payload.get("id", prompt_identifier))
            file_name = f"prompt_{prompt_id}.json"
            file_path = prompts_dir / file_name
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(prompt_payload, f, indent=2, ensure_ascii=False)

            content.prompts[prompt_id] = prompt_payload
            manifest.content_items.append(ContentItem(
                id=prompt_id,
                type=ContentType.PROMPT,
                title=prompt_payload.get("name", f"Prompt {prompt_id}"),
                description=prompt_payload.get("details"),
                file_path=f"content/prompts/{file_name}"
            ))

    def _collect_media_items(
        self,
        media_ids: List[str],
        work_dir: Path,
        manifest: ChatbookManifest,
        content: ChatbookContent,
        include_media: bool,
        include_embeddings: bool
    ) -> None:
        """Collect media items (metadata + transcripts) for export."""
        if not media_ids:
            return
        media_db = self._get_media_db()
        if media_db is None:
            logger.debug("Skipping media export because media DB is unavailable.")
            return
        media_dir = work_dir / "content" / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        embeddings_dir: Optional[Path] = None

        if include_media:
            self._note_todo("Binary media asset export is not yet implemented; exporting metadata only.")

        for media_identifier in media_ids:
            media_record = self._fetch_media_record(media_db, str(media_identifier))
            if not media_record:
                logger.debug(f"Media {media_identifier} not found; skipping.")
                continue

            normalized = self._normalize_media_record(media_record)
            media_id = str(normalized.get("id", media_identifier))

            # Attach transcripts when helper is available
            transcripts: List[Dict[str, Any]] = []
            if get_media_transcripts is not None:
                try:
                    transcripts_raw = get_media_transcripts(media_db, int(media_record["id"]))
                    transcripts = [self._normalize_transcript_row(row) for row in transcripts_raw]
                except Exception as exc:
                    logger.debug(f"Failed to fetch transcripts for media {media_id}: {exc}")
                    self._note_todo("Media transcripts export failed for some items; inspect logs.")
            normalized["transcripts"] = transcripts

            # Attach prompts linked to media when helper available
            media_prompts: List[Dict[str, Any]] = []
            if get_media_prompts is not None:
                try:
                    media_prompts = get_media_prompts(media_db, int(media_record["id"]))
                except Exception as exc:
                    logger.debug(f"Failed to fetch media prompts for media {media_id}: {exc}")
                    self._note_todo("Media prompts export encountered failures; inspect logs.")
            normalized["related_prompts"] = media_prompts

            # Handle embeddings when requested and available
            vector_payload = None
            vector_blob = media_record.get("vector_embedding")
            if include_embeddings and vector_blob:
                if isinstance(vector_blob, memoryview):
                    vector_blob = vector_blob.tobytes()
                elif isinstance(vector_blob, bytearray):
                    vector_blob = bytes(vector_blob)
                if isinstance(vector_blob, (bytes, bytearray)):
                    embeddings_dir = embeddings_dir or (work_dir / "content" / "embeddings")
                    embeddings_dir.mkdir(parents=True, exist_ok=True)
                    embedding_id = f"media:{media_id}"
                    vector_payload = {
                        "id": embedding_id,
                        "source": {
                            "media_id": media_id,
                            "media_uuid": normalized.get("uuid")
                        },
                        "encoding": "base64",
                        "vector": base64.b64encode(vector_blob).decode("ascii")
                    }
                    embed_file = embeddings_dir / f"embedding_media_{media_id}.json"
                    with open(embed_file, "w", encoding="utf-8") as ef:
                        json.dump(vector_payload, ef, indent=2, ensure_ascii=False)
                    content.embeddings[embedding_id] = vector_payload
                    manifest.content_items.append(ContentItem(
                        id=embedding_id,
                        type=ContentType.EMBEDDING,
                        title=f"Embedding for media {normalized.get('title', media_id)}",
                        file_path=f"content/embeddings/{embed_file.name}"
                    ))
                else:
                    self._note_todo("Encountered non-binary media vector embedding; skipping serialization.")

            media_file = media_dir / f"media_{media_id}.json"
            with open(media_file, "w", encoding="utf-8") as mf:
                json.dump(normalized, mf, indent=2, ensure_ascii=False)
            content.media[media_id] = normalized

            manifest.content_items.append(ContentItem(
                id=media_id,
                type=ContentType.MEDIA,
                title=normalized.get("title", f"Media {media_id}"),
                description=normalized.get("description"),
                file_path=f"content/media/{media_file.name}"
            ))

        if include_embeddings and not content.embeddings:
            self._note_todo("Embeddings export requested but no vector data found in media records.")

    def _collect_evaluations(
        self,
        evaluation_ids: List[str],
        work_dir: Path,
        manifest: ChatbookManifest,
        content: ChatbookContent
    ) -> None:
        """Collect evaluation definitions and runs for export."""
        if not evaluation_ids:
            return
        evals_db = self._get_evaluations_db()
        if evals_db is None:
            logger.debug("Skipping evaluation export because evaluations DB is unavailable.")
            return
        eval_dir = work_dir / "content" / "evaluations"
        eval_dir.mkdir(parents=True, exist_ok=True)

        for eval_id in evaluation_ids:
            record = None
            try:
                record = evals_db.get_evaluation(str(eval_id))
            except Exception as exc:
                logger.debug(f"Failed to fetch evaluation {eval_id}: {exc}")
                record = None
            if not record:
                continue

            normalized = self._normalize_evaluation_record(record)
            runs_payload: List[Dict[str, Any]] = []
            try:
                runs, has_more = evals_db.list_runs(eval_id=str(eval_id), limit=200, return_has_more=True)
                runs_payload = [self._normalize_evaluation_run(run) for run in runs]
                if has_more:
                    self._note_todo("Evaluation export limited to first 200 runs; add pagination support.")
            except Exception as exc:
                logger.debug(f"Failed to list evaluation runs for {eval_id}: {exc}")
                self._note_todo("Evaluation runs export failed for some items; inspect logs.")
            normalized["runs"] = runs_payload

            eval_file = eval_dir / f"evaluation_{eval_id}.json"
            with open(eval_file, "w", encoding="utf-8") as ef:
                json.dump(normalized, ef, indent=2, ensure_ascii=False)
            content.evaluations[str(eval_id)] = normalized

            manifest.content_items.append(ContentItem(
                id=str(eval_id),
                type=ContentType.EVALUATION,
                title=normalized.get("name", f"Evaluation {eval_id}"),
                description=normalized.get("description"),
                file_path=f"content/evaluations/{eval_file.name}"
            ))

    # Helper methods for collecting content

    def _collect_conversations(
        self,
        conversation_ids: List[str],
        work_dir: Path,
        manifest: ChatbookManifest,
        content: ChatbookContent
    ):
        """Collect conversations for export."""
        conv_dir = work_dir / "content" / "conversations"
        conv_dir.mkdir(parents=True, exist_ok=True)

        for conv_id in conversation_ids:
            try:
                # Get conversation
                conv = self.db.get_conversation_by_id(conv_id)
                if not conv:
                    continue

                # Get messages
                messages = self.db.get_messages_for_conversation(conv_id)

                attachments_dir: Optional[Path] = None
                conversation_messages: List[Dict[str, Any]] = []
                for msg in (messages or []):
                    message_payload: Dict[str, Any] = {
                        "id": msg['id'],
                        "role": msg['sender'],
                        "content": msg.get('message', msg.get('content', '')),
                        "timestamp": msg['timestamp'].isoformat() if hasattr(msg['timestamp'], 'isoformat') else msg['timestamp'],
                        "attachments": [],
                        "citations": []
                    }

                    # Persist inline images as attachments
                    for idx, image in enumerate(msg.get("images") or []):
                        image_bytes = image.get("image_data")
                        if isinstance(image_bytes, memoryview):
                            image_bytes = image_bytes.tobytes()
                        if not image_bytes:
                            continue
                        if attachments_dir is None:
                            attachments_dir = conv_dir / f"conversation_{conv_id}_assets"
                            attachments_dir.mkdir(parents=True, exist_ok=True)
                        ext = self._extension_from_mime(image.get("image_mime_type"))
                        attachment_name = f"{msg['id']}_image_{idx}{ext}"
                        attachment_path = attachments_dir / attachment_name
                        try:
                            with open(attachment_path, "wb") as af:
                                af.write(bytes(image_bytes))
                        except Exception as exc:
                            logger.debug(f"Failed to persist image attachment for message {msg['id']}: {exc}")
                            self._note_todo("Failed to export some conversation image attachments; inspect logs.")
                            continue
                        rel_path = f"content/conversations/{attachments_dir.name}/{attachment_name}"
                        message_payload["attachments"].append({
                            "type": "image",
                            "mime_type": image.get("image_mime_type"),
                            "file_path": rel_path
                        })

                    # Placeholder for future citation export support
                    if not message_payload["citations"]:
                        self._note_todo("Conversation export lacks citation metadata; awaiting upstream storage.")

                    conversation_messages.append(message_payload)

                conv_data = {
                    "id": conv['id'],
                    "name": conv.get('title', 'Untitled'),
                    "created_at": conv['created_at'].isoformat() if hasattr(conv['created_at'], 'isoformat') else conv['created_at'],
                    "character_id": conv.get('character_id'),
                    "attachments_path": f"content/conversations/{attachments_dir.name}" if attachments_dir else None,
                    "messages": conversation_messages
                }

                # Write to file
                conv_file = conv_dir / f"conversation_{conv_id}.json"
                with open(conv_file, 'w', encoding='utf-8') as f:
                    json.dump(conv_data, f, indent=2, ensure_ascii=False)

                # Add to content
                content.conversations[conv_id] = conv_data

                # Add to manifest
                manifest.content_items.append(ContentItem(
                    id=conv_id,
                    type=ContentType.CONVERSATION,
                    title=conv_data['name'],
                    file_path=f"content/conversations/conversation_{conv_id}.json"
                ))

            except Exception as e:
                logger.error(f"Error collecting conversation {conv_id}: {e}")

    def _collect_notes(
        self,
        note_ids: List[str],
        work_dir: Path,
        manifest: ChatbookManifest,
        content: ChatbookContent
    ):
        """Collect notes for export."""
        notes_dir = work_dir / "content" / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)

        for note_id in note_ids:
            try:
                # Get note
                note = self.db.get_note_by_id(note_id)
                if not note:
                    continue

                # Create note data
                note_data = {
                    "id": note['id'],
                    "title": note['title'],
                    "content": note['content'],
                    "created_at": note['created_at'].isoformat() if hasattr(note['created_at'], 'isoformat') else note['created_at']
                }

                # Write markdown file
                note_file = notes_dir / f"note_{note_id}.md"
                with open(note_file, 'w', encoding='utf-8') as f:
                    # Write frontmatter
                    f.write("---\n")
                    f.write(f"id: {note['id']}\n")
                    f.write(f"title: {note['title']}\n")
                    f.write(f"created_at: {note_data['created_at']}\n")
                    f.write("---\n\n")
                    f.write(note['content'])

                # Add to content
                content.notes[note_id] = note_data

                # Add to manifest
                manifest.content_items.append(ContentItem(
                    id=note_id,
                    type=ContentType.NOTE,
                    title=note['title'],
                    file_path=f"content/notes/note_{note_id}.md"
                ))

            except Exception as e:
                logger.error(f"Error collecting note {note_id}: {e}")

    def _collect_characters(
        self,
        character_ids: List[str],
        work_dir: Path,
        manifest: ChatbookManifest,
        content: ChatbookContent
    ):
        """Collect character cards for export."""
        chars_dir = work_dir / "content" / "characters"
        chars_dir.mkdir(parents=True, exist_ok=True)

        for char_id in character_ids:
            try:
                # Get character
                char = self.db.get_character_card_by_id(int(char_id))
                if not char:
                    continue

                # Write character file
                char_file = chars_dir / f"character_{char_id}.json"
                with open(char_file, 'w', encoding='utf-8') as f:
                    json.dump(char, f, indent=2, ensure_ascii=False)

                # Add to content
                content.characters[char_id] = char

                # Add to manifest
                manifest.content_items.append(ContentItem(
                    id=char_id,
                    type=ContentType.CHARACTER,
                    title=char.get('name', 'Unnamed'),
                    file_path=f"content/characters/character_{char_id}.json"
                ))

            except Exception as e:
                logger.error(f"Error collecting character {char_id}: {e}")

    def _collect_world_books(
        self,
        world_book_ids: List[str],
        work_dir: Path,
        manifest: ChatbookManifest,
        content: ChatbookContent
    ):
        """Collect world books for export."""
        wb_dir = work_dir / "content" / "world_books"
        wb_dir.mkdir(parents=True, exist_ok=True)

        # Import the world book service
        from ..Character_Chat.world_book_manager import WorldBookService

        wb_service = WorldBookService(self.db)

        for wb_id in world_book_ids:
            try:
                # Get world book with entries
                wb_data = wb_service.get_world_book(int(wb_id))
                if not wb_data:
                    continue

                # Convert datetime objects to strings for JSON serialization
                def convert_datetimes(obj):
                    if isinstance(obj, dict):
                        return {k: convert_datetimes(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_datetimes(item) for item in obj]
                    elif isinstance(obj, datetime):
                        return obj.isoformat()
                    return obj

                wb_data_serializable = convert_datetimes(wb_data)

                # Write world book file
                wb_file = wb_dir / f"world_book_{wb_id}.json"
                with open(wb_file, 'w', encoding='utf-8') as f:
                    json.dump(wb_data_serializable, f, indent=2, ensure_ascii=False)

                # Add to content
                content.world_books[wb_id] = wb_data

                # Add to manifest
                manifest.content_items.append(ContentItem(
                    id=wb_id,
                    type=ContentType.WORLD_BOOK,
                    title=wb_data.get('name', 'Unnamed'),
                    file_path=f"content/world_books/world_book_{wb_id}.json"
                ))

            except Exception as e:
                logger.error(f"Error collecting world book {wb_id}: {e}")

    def _collect_dictionaries(
        self,
        dictionary_ids: List[str],
        work_dir: Path,
        manifest: ChatbookManifest,
        content: ChatbookContent
    ):
        """Collect chat dictionaries for export."""
        dict_dir = work_dir / "content" / "dictionaries"
        dict_dir.mkdir(parents=True, exist_ok=True)

        # Import the dictionary service
        from ..Character_Chat.chat_dictionary import ChatDictionaryService

        dict_service = ChatDictionaryService(self.db)

        for dict_id in dictionary_ids:
            try:
                # Get dictionary with entries
                dict_data = dict_service.get_dictionary(int(dict_id))
                if not dict_data:
                    continue

                # Convert datetime objects to strings for JSON serialization
                def convert_datetimes(obj):
                    if isinstance(obj, dict):
                        return {k: convert_datetimes(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_datetimes(item) for item in obj]
                    elif isinstance(obj, datetime):
                        return obj.isoformat()
                    return obj

                dict_data_serializable = convert_datetimes(dict_data)

                # Write dictionary file
                dict_file = dict_dir / f"dictionary_{dict_id}.json"
                with open(dict_file, 'w', encoding='utf-8') as f:
                    json.dump(dict_data_serializable, f, indent=2, ensure_ascii=False)

                # Add to content
                content.dictionaries[dict_id] = dict_data

                # Add to manifest
                manifest.content_items.append(ContentItem(
                    id=dict_id,
                    type=ContentType.DICTIONARY,
                    title=dict_data.get('name', 'Unnamed'),
                    file_path=f"content/dictionaries/dictionary_{dict_id}.json"
                ))

            except Exception as e:
                logger.error(f"Error collecting dictionary {dict_id}: {e}")

    def _collect_generated_documents(
        self,
        document_ids: List[str],
        work_dir: Path,
        manifest: ChatbookManifest,
        content: ChatbookContent
    ):
        """Collect generated documents for export."""
        docs_dir = work_dir / "content" / "generated_documents"
        docs_dir.mkdir(parents=True, exist_ok=True)

        # Import the document generator service
        from ..Chat.document_generator import DocumentGeneratorService

        doc_service = DocumentGeneratorService(self.db, self.user_id)

        for doc_id in document_ids:
            try:
                # Get document
                doc = doc_service.get_document(doc_id)
                if not doc:
                    continue

                # Write document file
                doc_file = docs_dir / f"document_{doc_id}.json"
                with open(doc_file, 'w', encoding='utf-8') as f:
                    json.dump(doc, f, indent=2, ensure_ascii=False)

                # Add to content
                content.generated_documents[doc_id] = doc

                # Add to manifest
                manifest.content_items.append(ContentItem(
                    id=doc_id,
                    type=ContentType.GENERATED_DOCUMENT,
                    title=doc.get('title', 'Untitled'),
                    file_path=f"content/generated_documents/document_{doc_id}.json"
                ))

            except Exception as e:
                logger.error(f"Error collecting document {doc_id}: {e}")

    # Helper methods for importing content

    def _import_conversations(
        self,
        extract_dir: Path,
        manifest: ChatbookManifest,
        conversation_ids: List[str],
        conflict_resolution: ConflictResolution,
        prefix_imported: bool,
        status: ImportJob
    ):
        """Import conversations from chatbook."""
        conv_dir = extract_dir / "content" / "conversations"

        for conv_id in conversation_ids:
            status.processed_items += 1

            try:
                # Load conversation file
                conv_file = conv_dir / f"conversation_{conv_id}.json"
                if not conv_file.exists():
                    status.failed_items += 1
                    status.warnings.append(f"Conversation file not found: {conv_file.name}")
                    continue

                with open(conv_file, 'r', encoding='utf-8') as f:
                    conv_data = json.load(f)

                # Check for existing conversation
                conv_name = conv_data['name']
                if prefix_imported:
                    conv_name = f"[Imported] {conv_name}"

                existing = self._get_conversation_by_name(conv_name)
                if existing and conflict_resolution == ConflictResolution.SKIP:
                    status.skipped_items += 1
                    continue
                elif existing and conflict_resolution == ConflictResolution.RENAME:
                    conv_name = self._generate_unique_name(conv_name, "conversation")

                # Create conversation
                conv_dict = {
                    'title': conv_name,
                    'created_at': conv_data.get('created_at'),
                    'character_id': conv_data.get('character_id')
                }
                new_conv_id = self.db.add_conversation(conv_dict)

                if new_conv_id:
                    # Import messages
                    base_path = extract_dir.resolve()
                    for msg in conv_data.get('messages', []):
                        msg_dict = {
                            'conversation_id': new_conv_id,
                            'sender': msg['role'],
                            'content': msg['content'],
                            'timestamp': msg.get('timestamp')
                        }

                        attachments = msg.get('attachments') or []
                        images_payload: List[Dict[str, Any]] = []
                        for attachment in attachments:
                            if not isinstance(attachment, dict):
                                continue
                            if str(attachment.get("type", "")).lower() != "image":
                                continue
                            rel_path = attachment.get("file_path")
                            if not rel_path:
                                continue
                            try:
                                attachment_rel = Path(rel_path)
                            except Exception:
                                continue
                            candidate_path = (base_path / attachment_rel).resolve()
                            try:
                                candidate_path.relative_to(base_path)
                            except Exception:
                                status.warnings.append(f"Skipped attachment outside extract dir: {rel_path}")
                                continue
                            try:
                                image_bytes = candidate_path.read_bytes()
                            except Exception as read_exc:
                                status.warnings.append(f"Failed to read attachment {rel_path}: {read_exc}")
                                continue
                            mime_type = attachment.get("mime_type") or "application/octet-stream"
                            images_payload.append({
                                "image_data": image_bytes,
                                "image_mime_type": mime_type
                            })
                        if images_payload:
                            msg_dict['images'] = images_payload

                        self.db.add_message(msg_dict)

                    status.successful_items += 1
                else:
                    # If add failed, it might be a duplicate not caught by search
                    # Count as skipped if we're in skip mode
                    if conflict_resolution == ConflictResolution.SKIP:
                        status.skipped_items += 1
                    else:
                        status.failed_items += 1

            except Exception as e:
                status.failed_items += 1
                status.warnings.append(f"Error importing conversation {conv_id}: {str(e)}")

    def _import_notes(
        self,
        extract_dir: Path,
        manifest: ChatbookManifest,
        note_ids: List[str],
        conflict_resolution: ConflictResolution,
        prefix_imported: bool,
        status: ImportJob
    ):
        """Import notes from chatbook."""
        notes_dir = extract_dir / "content" / "notes"

        for note_id in note_ids:
            status.processed_items += 1

            try:
                # Find note file
                note_file = notes_dir / f"note_{note_id}.md"
                if not note_file.exists():
                    status.failed_items += 1
                    status.warnings.append(f"Note file not found: {note_file.name}")
                    continue

                # Parse markdown with frontmatter
                with open(note_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract frontmatter
                note_content = content
                note_title = f"Imported Note {note_id}"

                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        # Parse frontmatter for title
                        frontmatter = parts[1].strip()
                        for line in frontmatter.split('\n'):
                            if line.startswith('title:'):
                                note_title = line.replace('title:', '').strip()
                        note_content = parts[2].strip()

                if prefix_imported:
                    note_title = f"[Imported] {note_title}"

                # Check for existing note
                existing = self._get_note_by_title(note_title)
                if existing and conflict_resolution == ConflictResolution.SKIP:
                    status.skipped_items += 1
                    continue
                elif existing and conflict_resolution == ConflictResolution.RENAME:
                    note_title = self._generate_unique_name(note_title, "note")

                # Create note
                new_note_id = self.db.add_note(title=note_title, content=note_content)

                if new_note_id:
                    status.successful_items += 1
                else:
                    # If add failed, it might be a duplicate not caught by search
                    # Count as skipped if we're in skip mode
                    if conflict_resolution == ConflictResolution.SKIP:
                        status.skipped_items += 1
                    else:
                        status.failed_items += 1

            except Exception as e:
                status.failed_items += 1
                status.warnings.append(f"Error importing note {note_id}: {str(e)}")

    def _import_characters(
        self,
        extract_dir: Path,
        manifest: ChatbookManifest,
        character_ids: List[str],
        conflict_resolution: ConflictResolution,
        prefix_imported: bool,
        status: ImportJob
    ):
        """Import character cards from chatbook."""
        chars_dir = extract_dir / "content" / "characters"

        for char_id in character_ids:
            status.processed_items += 1

            try:
                # Load character file
                char_file = chars_dir / f"character_{char_id}.json"
                if not char_file.exists():
                    status.failed_items += 1
                    status.warnings.append(f"Character file not found: {char_file.name}")
                    continue

                with open(char_file, 'r', encoding='utf-8') as f:
                    char_data = json.load(f)

                # Check for existing character
                char_name = char_data.get('name', 'Unnamed')
                if prefix_imported:
                    char_name = f"[Imported] {char_name}"
                    char_data['name'] = char_name

                existing = self.db.get_character_card_by_name(char_name)
                if existing and conflict_resolution == ConflictResolution.SKIP:
                    status.skipped_items += 1
                    continue
                elif existing and conflict_resolution == ConflictResolution.RENAME:
                    char_name = self._generate_unique_name(char_name, "character")
                    char_data['name'] = char_name

                # Create character
                new_char_id = self.db.add_character_card(char_data)

                if new_char_id:
                    status.successful_items += 1
                else:
                    # If add failed, it might be a duplicate not caught by search
                    # Count as skipped if we're in skip mode
                    if conflict_resolution == ConflictResolution.SKIP:
                        status.skipped_items += 1
                    else:
                        status.failed_items += 1

            except Exception as e:
                status.failed_items += 1
                status.warnings.append(f"Error importing character {char_id}: {str(e)}")

    def _import_world_books(
        self,
        extract_dir: Path,
        manifest: ChatbookManifest,
        world_book_ids: List[str],
        conflict_resolution: ConflictResolution,
        prefix_imported: bool,
        status: ImportJob
    ):
        """Import world books from chatbook."""
        wb_dir = extract_dir / "content" / "world_books"

        # Import the world book service
        from ..Character_Chat.world_book_manager import WorldBookService
        wb_service = WorldBookService(self.db)

        for wb_id in world_book_ids:
            status.processed_items += 1

            try:
                # Load world book file
                wb_file = wb_dir / f"world_book_{wb_id}.json"
                if not wb_file.exists():
                    status.failed_items += 1
                    status.warnings.append(f"World book file not found: {wb_file.name}")
                    continue

                with open(wb_file, 'r', encoding='utf-8') as f:
                    wb_data = json.load(f)

                # Handle import with conflict resolution
                wb_name = wb_data.get('name', 'Unnamed')
                if prefix_imported:
                    wb_name = f"[Imported] {wb_name}"
                    wb_data['name'] = wb_name

                # Check for existing world book
                existing = wb_service.get_world_book_by_name(wb_name)
                if existing and conflict_resolution == ConflictResolution.SKIP:
                    status.skipped_items += 1
                    continue
                elif existing and conflict_resolution == ConflictResolution.RENAME:
                    wb_name = self._generate_unique_name(wb_name, "world_book")
                    wb_data['name'] = wb_name

                # Import world book
                success = wb_service.import_world_book(wb_data)

                if success:
                    status.successful_items += 1
                else:
                    status.failed_items += 1

            except Exception as e:
                status.failed_items += 1
                status.warnings.append(f"Error importing world book {wb_id}: {str(e)}")

    def _import_dictionaries(
        self,
        extract_dir: Path,
        manifest: ChatbookManifest,
        dictionary_ids: List[str],
        conflict_resolution: ConflictResolution,
        prefix_imported: bool,
        status: ImportJob
    ):
        """Import chat dictionaries from chatbook."""
        dict_dir = extract_dir / "content" / "dictionaries"

        # Import the dictionary service
        from ..Character_Chat.chat_dictionary import ChatDictionaryService
        dict_service = ChatDictionaryService(self.db)

        for dict_id in dictionary_ids:
            status.processed_items += 1

            try:
                # Load dictionary file
                dict_file = dict_dir / f"dictionary_{dict_id}.json"
                if not dict_file.exists():
                    status.failed_items += 1
                    status.warnings.append(f"Dictionary file not found: {dict_file.name}")
                    continue

                with open(dict_file, 'r', encoding='utf-8') as f:
                    dict_data = json.load(f)

                # Handle import with conflict resolution
                dict_name = dict_data.get('name', 'Unnamed')
                if prefix_imported:
                    dict_name = f"[Imported] {dict_name}"
                    dict_data['name'] = dict_name

                # Check for existing dictionary
                existing = dict_service.get_dictionary_by_name(dict_name)
                if existing and conflict_resolution == ConflictResolution.SKIP:
                    status.skipped_items += 1
                    continue
                elif existing and conflict_resolution == ConflictResolution.RENAME:
                    dict_name = self._generate_unique_name(dict_name, "dictionary")
                    dict_data['name'] = dict_name

                # Create dictionary
                new_dict_id = dict_service.create_dictionary(
                    dict_name,
                    dict_data.get('description', ''),
                    dict_data.get('is_active', True)
                )

                if new_dict_id:
                    # Import entries
                    for entry in dict_data.get('entries', []):
                        dict_service.add_entry(
                            new_dict_id,
                            entry['key_pattern'],
                            entry['replacement'],
                            entry.get('is_regex', False),
                            entry.get('probability', 100),
                            entry.get('max_replacements', 1)
                        )
                    status.successful_items += 1
                else:
                    status.failed_items += 1

            except Exception as e:
                status.failed_items += 1
                status.warnings.append(f"Error importing dictionary {dict_id}: {str(e)}")

    # Database helper methods

    def _save_export_job(self, job: ExportJob):
        """Save export job to database with transaction."""
        def _save():
            self.db.execute_query("""
                INSERT OR REPLACE INTO export_jobs (
                    job_id, user_id, status, chatbook_name, output_path,
                    created_at, started_at, completed_at, error_message,
                    progress_percentage, total_items, processed_items,
                    file_size_bytes, download_url, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id, job.user_id, job.status.value, job.chatbook_name,
                job.output_path,
                job.created_at.strftime('%Y-%m-%d %H:%M:%S.%f') if job.created_at else None,
                job.started_at.strftime('%Y-%m-%d %H:%M:%S.%f') if job.started_at else None,
                job.completed_at.strftime('%Y-%m-%d %H:%M:%S.%f') if job.completed_at else None,
                job.error_message, job.progress_percentage, job.total_items,
                job.processed_items, job.file_size_bytes, job.download_url,
                job.expires_at.strftime('%Y-%m-%d %H:%M:%S.%f') if job.expires_at else None
            ), commit=True)

        try:
            self._with_transaction(_save)
        except Exception as e:
            logger.error(f"Error saving export job: {e}")
            raise

    def _get_export_job(self, job_id: str) -> Optional[ExportJob]:
        """Get export job from database."""
        try:
            cursor = self.db.execute_query(
                "SELECT * FROM export_jobs WHERE job_id = ? AND user_id = ?",
                (job_id, self.user_id)
            )

            # Fetch results from cursor
            results = self._fetch_results(cursor)

            if not results:
                return None

            row = results[0]
            logger.debug(f"Retrieved row type: {type(row)}, content: {row}")

            # Handle both dict (from real DB) and tuple (from mocked tests)
            if isinstance(row, tuple):
                # Convert tuple to dict using expected field order.
                # Column 13 in tests may be legacy metadata JSON; in DB it's download_url.
                col13 = row[13] if len(row) > 13 else None
                is_json_like = isinstance(col13, str) and col13.strip().startswith('{')
                row = {
                    'job_id': row[0],
                    'user_id': row[1],
                    'status': row[2],
                    'chatbook_name': row[3],
                    'output_path': row[4],
                    'created_at': row[5],
                    'started_at': row[6],
                    'completed_at': row[7],
                    'error_message': row[8] if len(row) > 8 else None,
                    'progress_percentage': row[9] if len(row) > 9 else 0,
                    'total_items': row[10] if len(row) > 10 else 0,
                    'processed_items': row[11] if len(row) > 11 else 0,
                    'file_size_bytes': row[12] if len(row) > 12 else None,
                    'download_url': None if is_json_like else (col13 if len(row) > 13 else None),
                    'metadata': col13 if is_json_like else None,
                    'expires_at': row[14] if len(row) > 14 else None
                }

            # Parse metadata if it's a JSON string
            metadata = {}
            if 'metadata' in row and row['metadata']:
                if isinstance(row['metadata'], str):
                    try:
                        metadata = json.loads(row['metadata'])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse metadata JSON: {row['metadata']}")
                elif isinstance(row['metadata'], dict):
                    metadata = row['metadata']

            return ExportJob(
                job_id=row['job_id'],
                user_id=row['user_id'],
                status=ExportStatus(row['status']),
                chatbook_name=row['chatbook_name'],
                output_path=row['output_path'],
                created_at=self._parse_timestamp(row['created_at']),
                started_at=self._parse_timestamp(row['started_at']),
                completed_at=self._parse_timestamp(row['completed_at']),
                error_message=row['error_message'],
                progress_percentage=row['progress_percentage'] or 0,
                total_items=row['total_items'] or 0,
                processed_items=row['processed_items'] or 0,
                file_size_bytes=row['file_size_bytes'],
                download_url=row.get('download_url'),
                expires_at=self._parse_timestamp(row.get('expires_at')),
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Error getting export job: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _save_import_job(self, job: ImportJob):
        """Save import job to database with transaction."""
        def _save():
            self.db.execute_query("""
                INSERT OR REPLACE INTO import_jobs (
                    job_id, user_id, status, chatbook_path,
                    created_at, started_at, completed_at, error_message,
                    progress_percentage, total_items, processed_items,
                    successful_items, failed_items, skipped_items,
                    conflicts, warnings
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id, job.user_id, job.status.value, job.chatbook_path,
                job.created_at.strftime('%Y-%m-%d %H:%M:%S.%f') if job.created_at else None,
                job.started_at.strftime('%Y-%m-%d %H:%M:%S.%f') if job.started_at else None,
                job.completed_at.strftime('%Y-%m-%d %H:%M:%S.%f') if job.completed_at else None,
                job.error_message, job.progress_percentage, job.total_items,
                job.processed_items, job.successful_items, job.failed_items,
                job.skipped_items, json.dumps(job.conflicts), json.dumps(job.warnings)
            ), commit=True)

        try:
            self._with_transaction(_save)
        except Exception as e:
            logger.error(f"Error saving import job: {e}")
            raise

    def _get_import_job(self, job_id: str) -> Optional[ImportJob]:
        """Get import job from database."""
        try:
            cursor = self.db.execute_query(
                "SELECT * FROM import_jobs WHERE job_id = ? AND user_id = ?",
                (job_id, self.user_id)
            )

            # Fetch results from cursor
            results = self._fetch_results(cursor)

            if not results:
                return None

            row = results[0]

            # Handle both dict (from real DB) and tuple (from mocked tests)
            if isinstance(row, tuple):
                # Convert tuple to dict using expected field order
                row = {
                    'job_id': row[0],
                    'user_id': row[1],
                    'status': row[2],
                    'chatbook_path': row[3],
                    'created_at': row[4],
                    'started_at': row[5],
                    'completed_at': row[6],
                    'error_message': row[7] if len(row) > 7 else None,
                    'progress_percentage': row[8] if len(row) > 8 else 0,
                    'total_items': row[9] if len(row) > 9 else 0,
                    'processed_items': row[10] if len(row) > 10 else 0,
                    'successful_items': row[11] if len(row) > 11 else 0,
                    'failed_items': row[12] if len(row) > 12 else 0,
                    'skipped_items': row[13] if len(row) > 13 else 0,
                    'conflicts': row[14] if len(row) > 14 else '[]',
                    'warnings': row[15] if len(row) > 15 else '[]'
                }

            return ImportJob(
                job_id=row['job_id'],
                user_id=row['user_id'],
                status=ImportStatus(row['status']),
                chatbook_path=row['chatbook_path'],
                created_at=self._parse_timestamp(row['created_at']),
                started_at=self._parse_timestamp(row['started_at']),
                completed_at=self._parse_timestamp(row['completed_at']),
                error_message=row['error_message'],
                progress_percentage=row['progress_percentage'] or 0,
                total_items=row['total_items'] or 0,
                processed_items=row['processed_items'] or 0,
                successful_items=row['successful_items'] or 0,
                failed_items=row['failed_items'] or 0,
                skipped_items=row['skipped_items'] or 0,
                conflicts=json.loads(row['conflicts']) if row['conflicts'] else [],
                warnings=json.loads(row['warnings']) if row['warnings'] else []
            )
        except Exception as e:
            logger.error(f"Error getting import job: {e}")
            return None

    def _generate_unique_name(self, base_name: str, item_type: str) -> str:
        """Generate a unique name for an item."""
        counter = 1
        while True:
            new_name = f"{base_name} ({counter})"

            # Check if name exists based on item type
            if item_type == "conversation":
                if not self.db.get_conversation_by_name(new_name):
                    return new_name
            elif item_type == "note":
                if not self.db.get_note_by_title(new_name):
                    return new_name
            elif item_type == "character":
                if not self.db.get_character_card_by_name(new_name):
                    return new_name
            elif item_type == "world_book":
                # Check in world books table
                result = self.db.execute_query(
                    "SELECT id FROM world_books WHERE name = ?",
                    (new_name,)
                )
                rows = self._fetch_results(result) if result is not None else []
                if not rows:
                    return new_name
            elif item_type == "dictionary":
                # Check in dictionaries table
                result = self.db.execute_query(
                    "SELECT id FROM chat_dictionaries WHERE name = ?",
                    (new_name,)
                )
                rows = self._fetch_results(result) if result is not None else []
                if not rows:
                    return new_name

            counter += 1

    # Additional methods for test compatibility

    def create_export_job(self, name: str, description: str, content_types: List[str]) -> Dict[str, Any]:
        """
        Create an export job (synchronous wrapper for tests).

        Args:
            name: Export name
            description: Export description
            content_types: Content types to export

        Returns:
            Job information dictionary
        """
        try:
            job_id = str(uuid4())
            job = ExportJob(
                job_id=job_id,
                user_id=self.user_id,
                status=ExportStatus.PENDING,
                chatbook_name=name,
                created_at=datetime.utcnow()
            )

            self._save_export_job(job)

            # Audit is performed at the API layer.

            return {
                "job_id": job_id,
                "status": "pending",
                "name": name,
                "description": description
            }
        except Exception as e:
            raise JobError(f"Failed to create export job: {e}", job_type="export", cause=e)

    def get_export_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get export job status."""
        job = self._get_export_job(job_id)
        if not job:
            raise JobError(f"Export job {job_id} not found", job_id=job_id)

        result = job.to_dict()
        # Ensure status is a string value
        if hasattr(job.status, 'value'):
            result["status"] = job.status.value

        # Add computed fields
        result["file_path"] = job.output_path
        result["chatbook_name"] = job.chatbook_name

        # Add content summary if available
        if job.metadata:
            result["content_summary"] = job.metadata.get("content_summary", {})
            # Handle legacy format - if content counts are at root level
            if "conversation_count" in job.metadata:
                result["content_summary"]["conversations"] = job.metadata.get("conversation_count", 0)
            if "note_count" in job.metadata:
                result["content_summary"]["notes"] = job.metadata.get("note_count", 0)
            if "character_count" in job.metadata:
                result["content_summary"]["characters"] = job.metadata.get("character_count", 0)
        else:
            result["content_summary"] = {}

        return result

    def cancel_export_job(self, job_id: str) -> bool:
        """Cancel an export job."""
        job = self._get_export_job(job_id)
        if not job:
            raise JobError(f"Export job {job_id} not found", job_id=job_id)

        if job.status in [ExportStatus.COMPLETED, ExportStatus.FAILED]:
            return False

        job.status = ExportStatus.CANCELLED
        self._save_export_job(job)
        # Best-effort cancel of in-process task
        task = self._tasks.pop(job_id, None)
        if task:
            try:
                task.cancel()
            except Exception:
                pass
        # PS backend cancel
        if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
            try:
                self._ps_job_adapter.cancel(int(job_id))
            except Exception:
                pass
        # Core backend: cancel queued or request cancel for processing in core Jobs
        if getattr(self, "_jobs_backend", "core") == "core":
            try:
                from tldw_Server_API.app.core.Jobs.manager import JobManager
                jm = getattr(self, "_core_jobs", None) or JobManager()
                # scan recent jobs for this user and domain
                for st in ("queued", "processing"):
                    jobs = jm.list_jobs(domain="chatbooks", queue="default", status=st, owner_user_id=self.user_id, limit=50)
                    for j in jobs:
                        try:
                            payload = j.get("payload") or {}
                            if payload.get("chatbooks_job_id") == job_id:
                                jm.cancel_job(int(j["id"]))
                        except Exception:
                            pass
            except Exception:
                pass

        # Audit is performed at the API layer.

        return True

    def cancel_import_job(self, job_id: str) -> bool:
        """Cancel an import job."""
        job = self._get_import_job(job_id)
        if not job:
            raise JobError(f"Import job {job_id} not found", job_id=job_id)
        if job.status in [ImportStatus.COMPLETED, ImportStatus.FAILED]:
            return False
        job.status = ImportStatus.CANCELLED
        self._save_import_job(job)
        task = self._tasks.pop(job_id, None)
        if task:
            try:
                task.cancel()
            except Exception:
                pass
        if getattr(self, "_jobs_backend", "core") == "prompt_studio" and getattr(self, "_ps_job_adapter", None) is not None:
            try:
                self._ps_job_adapter.cancel(int(job_id))
            except Exception:
                pass
        if getattr(self, "_jobs_backend", "core") == "core":
            try:
                from tldw_Server_API.app.core.Jobs.manager import JobManager
                jm = getattr(self, "_core_jobs", None) or JobManager()
                for st in ("queued", "processing"):
                    jobs = jm.list_jobs(domain="chatbooks", queue="default", status=st, owner_user_id=self.user_id, limit=50)
                    for j in jobs:
                        try:
                            payload = j.get("payload") or {}
                            if payload.get("chatbooks_job_id") == job_id:
                                jm.cancel_job(int(j["id"]))
                        except Exception:
                            pass
            except Exception:
                pass
        return True

    def create_import_job(self, file_path: str, conflict_strategy: str = "skip") -> Dict[str, Any]:
        """
        Create an import job (synchronous wrapper for tests).

        Args:
            file_path: Path to import file
            conflict_strategy: How to handle conflicts

        Returns:
            Job information dictionary
        """
        try:
            job_id = str(uuid4())
            job = ImportJob(
                job_id=job_id,
                user_id=self.user_id,
                status=ImportStatus.PENDING,
                chatbook_path=file_path,
                created_at=datetime.utcnow()
            )

            self._save_import_job(job)

            return {
                "job_id": job_id,
                "status": "pending",
                "file_path": file_path
            }
        except Exception as e:
            raise JobError(f"Failed to create import job: {e}", job_type="import", cause=e)

    def get_import_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get import job status."""
        job = self._get_import_job(job_id)
        if not job:
            raise JobError(f"Import job {job_id} not found", job_id=job_id)

        result = job.to_dict()
        # Ensure status is a string value
        if hasattr(job.status, 'value'):
            result["status"] = job.status.value

        # Add compatibility fields
        result["items_imported"] = job.successful_items
        result["error"] = job.error_message
        result["progress"] = job.progress_percentage
        result["conflicts_found"] = job.skipped_items  # Assuming skipped items are conflicts
        result["conflicts_resolved"] = {
            "skipped": job.skipped_items,
            "replaced": 0,
            "renamed": 0
        }

        return result

    def preview_export(self, content_types: List[str]) -> Dict[str, Any]:
        """
        Preview what would be exported.

        Args:
            content_types: Types of content to preview

        Returns:
            Preview information with counts
        """
        try:
            result = {}

            # Initialize all content types to 0
            for ct in ["conversations", "characters", "world_books", "dictionaries", "notes", "prompts"]:
                result[ct] = 0

            # Get actual counts for requested types
            for content_type in content_types:
                try:
                    if content_type == "conversations":
                        cursor = self.db.execute_query(
                            "SELECT id FROM conversations WHERE deleted = 0",
                            ()
                        )
                        items = self._fetch_results(cursor)
                        result["conversations"] = len(items) if items else 0
                    elif content_type == "characters":
                        cursor = self.db.execute_query(
                            "SELECT id FROM character_cards WHERE deleted = 0",
                            ()
                        )
                        items = self._fetch_results(cursor)
                        result["characters"] = len(items) if items else 0
                    elif content_type == "notes":
                        cursor = self.db.execute_query(
                            "SELECT id FROM notes WHERE deleted = 0",
                            ()
                        )
                        items = self._fetch_results(cursor)
                        result["notes"] = len(items) if items else 0
                    elif content_type == "world_books":
                        # Try without user_id first
                        try:
                            cursor = self.db.execute_query(
                                "SELECT id FROM world_books WHERE deleted = 0",
                                ()
                            )
                            items = self._fetch_results(cursor)
                        except Exception as q_err:
                            # Table might not exist or have different schema
                            logger.debug(f"world_books count query failed (no user filter): error={q_err}")
                            items = []
                        result["world_books"] = len(items) if items else 0
                    elif content_type == "dictionaries":
                        # Try to get dictionaries
                        try:
                            cursor = self.db.execute_query(
                                "SELECT id FROM dictionaries WHERE deleted = 0",
                                ()
                            )
                            items = self._fetch_results(cursor)
                        except Exception as q_err:
                            # Table might not exist
                            logger.debug(f"dictionaries count query failed: error={q_err}")
                            items = []
                        result["dictionaries"] = len(items) if items else 0
                    elif content_type == "prompts":
                        # Try to get prompts
                        try:
                            cursor = self.db.execute_query(
                                "SELECT id FROM prompts WHERE deleted = 0",
                                ()
                            )
                            items = self._fetch_results(cursor)
                        except Exception as q_err:
                            # Table might not exist
                            logger.debug(f"prompts count query failed: error={q_err}")
                            items = []
                        result["prompts"] = len(items) if items else 0
                except Exception as e:
                    # If query fails for any type, just set to 0
                    logger.debug(f"Query failed for {content_type}: {e}")
                    result[content_type] = 0

            return result
        except Exception as e:
            raise DatabaseError(f"Failed to preview export: {e}", cause=e)

    def clean_old_exports(self, days_old: int = 7) -> int:
        """
        Clean up old export files.

        Args:
            days_old: Delete exports older than this many days

        Returns:
            Number of files deleted
        """
        try:
            deleted_count = 0
            cutoff_date = datetime.now() - timedelta(days=days_old)

            # Query database for old exports
            cursor = self.db.execute_query(
                "SELECT job_id, output_path FROM export_jobs WHERE user_id = ? AND created_at < ?",
                (self.user_id, cutoff_date.isoformat())
            )

            # Fetch results from cursor
            results = self._fetch_results(cursor)

            if results:
                for row in results:
                    # Handle both tuple and dict formats
                    if isinstance(row, dict):
                        job_id = row['job_id']
                        output_path = row['output_path']
                    else:
                        job_id = row[0] if len(row) > 0 else None
                        output_path = row[1] if len(row) > 1 else None

                    if output_path and os.path.exists(output_path):
                        try:
                            os.unlink(output_path)
                            deleted_count += 1
                            logger.info(f"Deleted old export: {output_path}")
                        except Exception as e:
                            logger.error(f"Failed to delete {output_path}: {e}")

                    # Delete from database
                    try:
                        self.db.execute_query(
                            "DELETE FROM export_jobs WHERE job_id = ?",
                            (job_id,)
                        )
                    except Exception as e:
                        logger.error(f"Failed to delete job record {job_id}: {e}")

            # Audit is performed at the API layer.

            return deleted_count
        except Exception as e:
            raise FileOperationError(f"Failed to clean old exports: {e}", operation="cleanup", cause=e)

    def validate_chatbook(self, file_path: str) -> bool:
        """
        Validate a chatbook file.

        Args:
            file_path: Path to chatbook file

        Returns:
            True if valid
        """
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # Check for manifest
                if 'manifest.json' not in zf.namelist():
                    raise ValidationError("Missing manifest.json", field="manifest")

                # Validate manifest structure
                manifest_data = zf.read('manifest.json')
                manifest = json.loads(manifest_data)

                # Check required fields
                required_fields = ['version', 'name', 'description']
                for field in required_fields:
                    if field not in manifest:
                        raise ValidationError(f"Missing required field: {field}", field=field)

                return True
        except zipfile.BadZipFile:
            raise ArchiveError("Invalid ZIP file", archive_path=file_path)
        except Exception as e:
            if isinstance(e, (ValidationError, ArchiveError)):
                raise
            raise ValidationError(f"Validation failed: {e}", cause=e)

    def validate_chatbook_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate a chatbook file (test compatibility method).

        Args:
            file_path: Path to chatbook file

        Returns:
            Dict with validation results
        """
        try:
            # Try to validate using the main method
            is_valid = self.validate_chatbook(file_path)

            # If valid, try to get manifest
            manifest = None
            if is_valid:
                try:
                    with zipfile.ZipFile(file_path, 'r') as zf:
                        manifest_data = zf.read('manifest.json')
                        manifest = json.loads(manifest_data)
                except Exception as mf_err:
                    logger.debug(f"Failed to read chatbook manifest.json: path={file_path}, error={mf_err}")

            return {
                "is_valid": is_valid,
                "manifest": manifest,
                "error": None
            }
        except Exception as e:
            return {
                "is_valid": False,
                "manifest": None,
                "error": str(e)
            }

    def get_statistics(self) -> Dict[str, Any]:
        """Get import/export statistics."""
        try:
            # Get export stats
            export_cursor = self.db.execute_query(
                "SELECT status, COUNT(*) as count FROM export_jobs WHERE user_id = ? GROUP BY status",
                (self.user_id,)
            )
            export_results = self._fetch_results(export_cursor)

            # Get import stats
            import_cursor = self.db.execute_query(
                "SELECT status, COUNT(*) as count FROM import_jobs WHERE user_id = ? GROUP BY status",
                (self.user_id,)
            )
            import_results = self._fetch_results(import_cursor)

            # Build stats dict - handle both dict and tuple formats
            export_stats = {}
            for row in (export_results or []):
                if isinstance(row, dict):
                    export_stats[row["status"]] = row["count"]
                else:
                    # Tuple format (status, count)
                    export_stats[row[0]] = row[1]

            import_stats = {}
            for row in (import_results or []):
                if isinstance(row, dict):
                    import_stats[row["status"]] = row["count"]
                else:
                    # Tuple format (status, count)
                    import_stats[row[0]] = row[1]

            return {
                "exports": export_stats,
                "imports": import_stats,
                "total_exports": sum(export_stats.values()),
                "total_imports": sum(import_stats.values())
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {
                "exports": {},
                "imports": {},
                "total_exports": 0,
                "total_imports": 0
            }

    # Removed legacy JobQueueShim handlers; Chatbooks uses in-process tasks (core) or PS adapter (prompt_studio).

    def _create_chatbook_archive(self, work_dir: Path, output_path: Path) -> bool:
        """Create ZIP archive from work directory."""
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_path in work_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(work_dir)
                        zf.write(file_path, arcname)
            return True
        except Exception as e:
            logger.error(f"Failed to create archive: {e}")
            return False

    def _write_content_to_archive(self, zf: zipfile.ZipFile, content_items: List[ContentItem], base_dir: str = "content"):
        """Write content items to archive."""
        for item in content_items:
            # Create item directory
            item_dir = f"{base_dir}/{item.type.value}/{item.id}"

            # Write item metadata
            metadata = item.to_dict()
            zf.writestr(f"{item_dir}/metadata.json", json.dumps(metadata, indent=2))

            # Write content if available
            if item.metadata:
                zf.writestr(f"{item_dir}/content.json", json.dumps(item.metadata, indent=2))

    def _process_import_items(self, items: List[ContentItem], conflict_resolution: str = "skip") -> ImportStatusData:
        """Process import items with conflict resolution."""
        status = ImportStatusData()
        status.total_items = len(items)

        for item in items:
            try:
                # Check for conflicts
                existing = None
                if item.type == ContentType.CONVERSATION:
                    existing = self.db.execute_query(
                        "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                        (item.id, self.user_id)
                    )

                if existing and conflict_resolution == "skip":
                    status.skipped_items += 1
                    status.conflicts.append({"item_id": item.id, "action": "skipped"})
                elif existing and conflict_resolution == "overwrite":
                    # Overwrite existing
                    status.successful_items += 1
                    status.conflicts.append({"item_id": item.id, "action": "overwritten"})
                else:
                    # Import new item
                    status.successful_items += 1
            except Exception as e:
                status.failed_items += 1
                status.warnings.append(f"Failed to import {item.id}: {str(e)}")

        return status

    async def _create_readme_async(self, work_dir: Path, manifest: ChatbookManifest):
        """Create README file for the chatbook asynchronously."""
        readme_path = work_dir / "README.md"

        content = []
        content.append(f"# {manifest.name}\n\n")
        content.append(f"{manifest.description}\n\n")

        if manifest.author:
            content.append(f"**Author:** {manifest.author}\n\n")

        content.append(f"**Created:** {manifest.created_at.strftime('%Y-%m-%d %H:%M')}\n\n")
        content.append("## Contents\n\n")

        if manifest.total_conversations > 0:
            content.append(f"- **Conversations:** {manifest.total_conversations}\n")
        if manifest.total_notes > 0:
            content.append(f"- **Notes:** {manifest.total_notes}\n")
        if manifest.total_characters > 0:
            content.append(f"- **Characters:** {manifest.total_characters}\n")
        if manifest.total_world_books > 0:
            content.append(f"- **World Books:** {manifest.total_world_books}\n")
        if manifest.total_dictionaries > 0:
            content.append(f"- **Dictionaries:** {manifest.total_dictionaries}\n")
        if manifest.total_documents > 0:
            content.append(f"- **Generated Documents:** {manifest.total_documents}\n")

        if manifest.tags:
            content.append(f"\n## Tags\n\n{', '.join(manifest.tags)}\n")

        content.append("\n## License\n\n")
        content.append(manifest.license or "See individual content files for licensing information.")

        async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
            await f.write(''.join(content))

    def _create_readme(self, work_dir: Path, manifest: ChatbookManifest):
        """Create README file for the chatbook (sync version for backwards compatibility)."""
        readme_path = work_dir / "README.md"

        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(f"# {manifest.name}\n\n")
            f.write(f"{manifest.description}\n\n")

            if manifest.author:
                f.write(f"**Author:** {manifest.author}\n\n")

            f.write(f"**Created:** {manifest.created_at.strftime('%Y-%m-%d %H:%M')}\n\n")

            f.write("## Contents\n\n")

            if manifest.total_conversations > 0:
                f.write(f"- **Conversations:** {manifest.total_conversations}\n")
            if manifest.total_notes > 0:
                f.write(f"- **Notes:** {manifest.total_notes}\n")
            if manifest.total_characters > 0:
                f.write(f"- **Characters:** {manifest.total_characters}\n")
            if manifest.total_world_books > 0:
                f.write(f"- **World Books:** {manifest.total_world_books}\n")
            if manifest.total_dictionaries > 0:
                f.write(f"- **Dictionaries:** {manifest.total_dictionaries}\n")
            if manifest.total_documents > 0:
                f.write(f"- **Generated Documents:** {manifest.total_documents}\n")

            if manifest.tags:
                f.write(f"\n## Tags\n\n{', '.join(manifest.tags)}\n")

            f.write("\n## License\n\n")
            f.write(manifest.license or "See individual content files for licensing information.")

    def _validate_zip_file(self, file_path: str) -> bool:
        """Delegate to ChatbookValidator for ZIP validation (compatibility shim)."""
        try:
            from .chatbook_validators import ChatbookValidator
            ok, _ = ChatbookValidator.validate_zip_file(file_path)
            return bool(ok)
        except Exception:
            return False

    async def _create_zip_archive_async(self, work_dir: Path, output_path: Path):
        """Create ZIP archive of the chatbook asynchronously with compression limits."""
        def _create_archive():
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                total_size = 0
                for file_path in work_dir.rglob('*'):
                    if file_path.is_file():
                        # Check individual file size
                        file_size = file_path.stat().st_size
                        if file_size > 50 * 1024 * 1024:  # 50MB per file limit
                            logger.warning(f"Skipping large file: {file_path} ({file_size} bytes)")
                            continue

                        total_size += file_size
                        if total_size > 500 * 1024 * 1024:  # 500MB total limit
                            raise ValueError("Archive size exceeds 500MB limit")

                        arcname = file_path.relative_to(work_dir)
                        zf.write(file_path, arcname)

        # Run in thread pool to avoid blocking
        await asyncio.to_thread(_create_archive)

    def _create_zip_archive(self, work_dir: Path, output_path: Path):
        """Create ZIP archive of the chatbook with compression limits (sync version)."""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            total_size = 0
            for file_path in work_dir.rglob('*'):
                if file_path.is_file():
                    # Check individual file size
                    file_size = file_path.stat().st_size
                    if file_size > 50 * 1024 * 1024:  # 50MB per file limit
                        logger.warning(f"Skipping large file: {file_path} ({file_size} bytes)")
                        continue

                    total_size += file_size
                    if total_size > 500 * 1024 * 1024:  # 500MB total limit
                        raise ValueError("Archive size exceeds 500MB limit")

                    arcname = file_path.relative_to(work_dir)
                    zf.write(file_path, arcname)
