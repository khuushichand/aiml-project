# character_chat_sessions.py
"""
API endpoints for character chat session management.
Provides CRUD operations for chat sessions and character-specific completions.
"""

import asyncio
import json
import os
import random
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from loguru import logger

# Database and authentication dependencies
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user

# Schemas
from tldw_Server_API.app.api.v1.schemas.chat_session_schemas import (
    CharacterChatCompletionPrepRequest,
    CharacterChatCompletionPrepResponse,
    CharacterChatCompletionV2Request,
    CharacterChatCompletionV2Response,
    CharacterChatStreamPersistRequest,
    CharacterChatStreamPersistResponse,
    ChatSettingsResponse,
    ChatSettingsUpdate,
    ChatSessionCreate,
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatSessionUpdate,
    MessageResponse,
)
from tldw_Server_API.app.core.AuthNZ.byok_runtime import (
    record_byok_missing_credentials,
    resolve_byok_credentials,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

# Character chat helpers
from tldw_Server_API.app.core.Character_Chat.Character_Chat_Lib_facade import (
    map_sender_to_role,
    post_message_to_conversation,
    replace_placeholders,
)
from tldw_Server_API.app.core.Character_Chat.modules.character_prompt_presets import (
    build_character_system_prompt,
)
from tldw_Server_API.app.core.Character_Chat.modules.character_generation_presets import (
    resolve_character_generation_settings,
)
from tldw_Server_API.app.core.Character_Chat.modules.character_utils import (
    sanitize_sender_name,
)

# Rate limiting
from tldw_Server_API.app.core.Character_Chat.character_rate_limiter import (
    get_character_rate_limiter,
)

# Import shared constants
from tldw_Server_API.app.core.Character_Chat.constants import (
    MAX_STREAMING_BYTES,
    MAX_STREAMING_CHUNKS,
    MAX_TOOL_CALLS_COUNT,
    MAX_TOOL_CALLS_SIZE,
    THROTTLE_CACHE_MAX_KEYS,
    THROTTLE_STALE_SECONDS,
)

# Chat helpers and utilities
# For chat completions
from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)
from tldw_Server_API.app.core.LLM_Calls.provider_metadata import provider_requires_api_key
from tldw_Server_API.app.core.LLM_Calls.sse import ensure_sse_line, normalize_provider_line, sse_done

# Completion schemas centralized in schemas/chat_session_schemas.py
from tldw_Server_API.app.core.Streaming.streams import SSEStream
from tldw_Server_API.app.core.Utils.common import parse_boolean

_CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS = (
    asyncio.CancelledError,
    asyncio.TimeoutError,
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    HTTPException,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)

THROTTLE_WINDOW_SIZE = 100
MAX_CHAT_SETTINGS_BYTES = 200_000
MAX_AUTHOR_NOTE_CHARS = 20_000
DEFAULT_AUTO_SUMMARY_THRESHOLD_MESSAGES = 40
DEFAULT_AUTO_SUMMARY_WINDOW_MESSAGES = 12
MAX_AUTO_SUMMARY_LINES = 24
MAX_AUTO_SUMMARY_LINE_CHARS = 220
MAX_AUTO_SUMMARY_CONTENT_CHARS = 8_000

def _safe_replace_placeholders(value: Any, char_name: str, user_name: str) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if not text:
        return ""
    try:
        return replace_placeholders(text, char_name, user_name)
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug("Placeholder replacement failed: {}", exc)
        return text

def _validate_and_truncate_tool_calls(tool_calls: Any) -> Optional[list]:
    """
    Validate and truncate tool_calls to prevent unbounded storage.

    Args:
        tool_calls: Tool calls data from LLM response

    Returns:
        Validated and potentially truncated tool_calls, or None if invalid
    """
    if tool_calls is None:
        return None

    if not isinstance(tool_calls, list):
        logger.warning("tool_calls is not a list, discarding")
        return None

    # Limit number of tool calls
    if len(tool_calls) > MAX_TOOL_CALLS_COUNT:
        logger.warning(f"Truncating tool_calls from {len(tool_calls)} to {MAX_TOOL_CALLS_COUNT}")
        tool_calls = tool_calls[:MAX_TOOL_CALLS_COUNT]

    # Check total serialized size
    try:
        serialized = json.dumps(tool_calls)
        if len(serialized) > MAX_TOOL_CALLS_SIZE:
            logger.warning(f"tool_calls exceeds size limit ({len(serialized)} > {MAX_TOOL_CALLS_SIZE}), truncating")
            # Progressively remove tool calls until within size limit
            while tool_calls and len(serialized) > MAX_TOOL_CALLS_SIZE:
                tool_calls = tool_calls[:-1]
                serialized = json.dumps(tool_calls)
            if not tool_calls:
                return None
    except (TypeError, ValueError) as e:
        logger.warning(f"tool_calls not JSON serializable: {e}")
        return None

    return tool_calls

# Legacy local SSE helpers removed — unified streams handle normalization


def _verify_chat_ownership(
    conversation: Optional[dict[str, Any]],
    user_id: Any,
    chat_id: str
) -> None:
    """Verify that the user owns the chat session.

    Args:
        conversation: The conversation dict from database (may be None)
        user_id: The current user's ID
        chat_id: The chat session ID (for error messages)

    Raises:
        HTTPException: 404 if conversation not found, 403 if not owner
    """
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session {chat_id} not found"
        )

    # Normalize both IDs to strings and strip whitespace for consistent comparison
    # This handles cases where client_id might have different formatting
    stored_client_id = str(conversation.get('client_id', '')).strip()
    request_user_id = str(user_id).strip()

    if stored_client_id != request_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this chat session"
        )


router = APIRouter()

# Simple per-chat throttle used for legacy /complete endpoint in tests (TEST_MODE only)
# Bounded to prevent unbounded memory growth - uses constants from Character_Chat.constants
class _BoundedThrottleCache:
    """Bounded cache for throttle windows with automatic stale entry cleanup.

    Concurrency-safe implementation using asyncio.Lock for async context protection.
    """

    def __init__(self):
        self._data: dict[str, deque] = {}
        self._last_access: dict[str, float] = {}
        self._lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None

    async def get(self, key: str) -> deque:
        """Concurrency-safe access to throttle window for a given key."""
        current_loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not current_loop:
            self._lock = asyncio.Lock()
            self._lock_loop = current_loop
        async with self._lock:
            now = time.time()
            # Cleanup if too many keys
            if len(self._data) > THROTTLE_CACHE_MAX_KEYS:
                self._cleanup(now)
            # Create or get entry
            if key not in self._data:
                self._data[key] = deque(maxlen=THROTTLE_WINDOW_SIZE)
            self._last_access[key] = now
            return self._data[key]

    async def check_and_record(self, key: str, max_hits: int, window_seconds: float) -> bool:
        """Atomically enforce windowed limit and record a hit if allowed."""
        current_loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not current_loop:
            self._lock = asyncio.Lock()
            self._lock_loop = current_loop
        async with self._lock:
            now = time.time()
            if len(self._data) > THROTTLE_CACHE_MAX_KEYS:
                self._cleanup(now)
            window = self._data.get(key)
            if window is None:
                window = deque(maxlen=THROTTLE_WINDOW_SIZE)
                self._data[key] = window
            while window and (now - window[0]) > window_seconds:
                window.popleft()
            if len(window) >= max_hits:
                self._last_access[key] = now
                return False
            window.append(now)
            self._last_access[key] = now
            return True

    def _cleanup(self, now: float) -> None:
        """Remove entries not accessed recently."""
        stale_keys = [
            k for k, last in self._last_access.items()
            if (now - last) > THROTTLE_STALE_SECONDS
        ]
        for k in stale_keys:
            self._data.pop(k, None)
            self._last_access.pop(k, None)
        # If still over limit, evict oldest-accessed entries.
        if len(self._data) > THROTTLE_CACHE_MAX_KEYS:
            sorted_by_access = sorted(self._last_access.items(), key=lambda item: item[1])
            excess = len(self._data) - THROTTLE_CACHE_MAX_KEYS
            for k, _ in sorted_by_access[:excess]:
                self._data.pop(k, None)
                self._last_access.pop(k, None)

_complete_windows = _BoundedThrottleCache()


def reset_complete_windows() -> None:
    """Reset legacy /complete throttle cache (useful in tests)."""
    global _complete_windows
    _complete_windows = _BoundedThrottleCache()

# ========================================================================
# Helper Functions
# ========================================================================

def _convert_db_conversation_to_response(
    conv_data: dict[str, Any],
    *,
    settings: Optional[dict[str, Any]] = None,
) -> ChatSessionResponse:
    """Convert database conversation to response model."""
    return ChatSessionResponse(
        id=conv_data.get('id', ''),
        character_id=conv_data.get('character_id', 0),
        title=conv_data.get('title'),
        rating=conv_data.get('rating'),
        state=conv_data.get('state', 'in-progress'),
        topic_label=conv_data.get('topic_label'),
        cluster_id=conv_data.get('cluster_id'),
        source=conv_data.get('source'),
        external_ref=conv_data.get('external_ref'),
        created_at=conv_data.get('created_at', datetime.now(timezone.utc)),
        last_modified=conv_data.get('last_modified', datetime.now(timezone.utc)),
        message_count=conv_data.get('message_count', 0),
        version=conv_data.get('version', 1),
        settings=settings,
    )

def _convert_db_message_to_response(msg_data: dict[str, Any]) -> MessageResponse:
    """Convert database message to response model."""
    return MessageResponse(
        id=msg_data.get('id', ''),
        conversation_id=msg_data.get('conversation_id', ''),
        parent_message_id=msg_data.get('parent_message_id'),
        sender=msg_data.get('sender', ''),
        content=msg_data.get('content') or '',
        timestamp=msg_data.get('timestamp', datetime.now(timezone.utc)),
        ranking=msg_data.get('ranking'),
        has_image=bool(msg_data.get('image_data')),
        version=msg_data.get('version', 1)
    )

def _touch_conversation_metadata(db: CharactersRAGDB, conversation_id: str) -> bool:
    """Best-effort bump last_modified/version after settings updates."""
    for _ in range(2):
        conversation = db.get_conversation_by_id(conversation_id)
        if not conversation:
            return False
        try:
            db.update_conversation(conversation_id, {}, conversation.get("version", 1))
            return True
        except ConflictError:
            continue
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
            return False
    return False

def _validate_chat_settings_payload(settings: dict[str, Any]) -> None:
    """Validate settings payload size, shape, and known enum fields."""
    try:
        encoded = json.dumps(settings).encode("utf-8")
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid settings payload: {exc}"
        ) from exc

    if len(encoded) > MAX_CHAT_SETTINGS_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Settings payload exceeds {MAX_CHAT_SETTINGS_BYTES} bytes"
        )

    author_note = settings.get("authorNote")
    if isinstance(author_note, str) and len(author_note) > MAX_AUTHOR_NOTE_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"authorNote exceeds {MAX_AUTHOR_NOTE_CHARS} characters"
        )

    known_enum_fields = {
        "greetingScope": {"chat", "character"},
        "presetScope": {"chat", "character"},
        "memoryScope": {"shared", "character", "both"},
    }
    for key, allowed_values in known_enum_fields.items():
        value = settings.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or value.strip().lower() not in allowed_values:
            allowed_display = ", ".join(sorted(allowed_values))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid {key}. Allowed values: {allowed_display}"
            )

    schema_version = settings.get("schemaVersion")
    if schema_version is not None and (not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version < 1):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid schemaVersion. Expected integer >= 1"
        )

    updated_at = settings.get("updatedAt")
    if updated_at is not None and _parse_iso_timestamp(updated_at) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid updatedAt. Expected ISO timestamp string"
        )

    memory_by_id = settings.get("characterMemoryById")
    if memory_by_id is not None:
        if not isinstance(memory_by_id, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid characterMemoryById. Expected object map"
            )
        for character_id, entry in memory_by_id.items():
            if isinstance(entry, dict):
                note = entry.get("note")
                if note is not None and not isinstance(note, str):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Invalid characterMemoryById.{character_id}.note. Expected string"
                    )
                if isinstance(note, str) and len(note) > MAX_AUTHOR_NOTE_CHARS:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"characterMemoryById.{character_id}.note exceeds {MAX_AUTHOR_NOTE_CHARS} characters"
                    )
                entry_updated_at = entry.get("updatedAt")
                if entry_updated_at is not None and _parse_iso_timestamp(entry_updated_at) is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Invalid characterMemoryById.{character_id}.updatedAt. Expected ISO timestamp string"
                    )
                continue
            if isinstance(entry, str):
                if len(entry) > MAX_AUTHOR_NOTE_CHARS:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"characterMemoryById.{character_id} exceeds {MAX_AUTHOR_NOTE_CHARS} characters"
                    )
                continue
            if entry is None:
                continue
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid characterMemoryById.{character_id}. Expected object, string, or null"
            )

    generation_override = settings.get("chatGenerationOverride")
    if generation_override is not None:
        if not isinstance(generation_override, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid chatGenerationOverride. Expected object"
            )
        stop = generation_override.get("stop")
        if stop is not None:
            if not isinstance(stop, list) or any(not isinstance(item, str) for item in stop):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid chatGenerationOverride.stop. Expected array of strings"
                )
        override_updated_at = generation_override.get("updatedAt")
        if override_updated_at is not None and _parse_iso_timestamp(override_updated_at) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid chatGenerationOverride.updatedAt. Expected ISO timestamp string"
            )

    summary_settings = settings.get("summary")
    if summary_settings is not None:
        if not isinstance(summary_settings, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid summary. Expected object"
            )
        source_range = summary_settings.get("sourceRange")
        if source_range is not None and not isinstance(source_range, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid summary.sourceRange. Expected object"
            )
        summary_updated_at = summary_settings.get("updatedAt")
        if summary_updated_at is not None and _parse_iso_timestamp(summary_updated_at) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid summary.updatedAt. Expected ISO timestamp string"
            )


def _parse_iso_timestamp(value: Any) -> Optional[float]:
    """Parse ISO timestamp and return epoch seconds, or None when invalid."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _normalize_memory_entry(entry: Any) -> Optional[dict[str, Any]]:
    """Normalize a characterMemoryById entry while preserving extra fields."""
    if entry is None:
        return None
    if isinstance(entry, dict):
        normalized = dict(entry)
        note = normalized.get("note")
        if note is None:
            normalized["note"] = ""
        elif not isinstance(note, str):
            normalized["note"] = str(note)
        return normalized
    if isinstance(entry, str):
        return {"note": entry}
    return None


def _merge_character_memory_by_id(
    server_map_raw: Any,
    incoming_map_raw: Any,
    *,
    server_updated_at_epoch: float,
    incoming_updated_at_epoch: float,
) -> Optional[dict[str, Any]]:
    """Merge memory map by entry updatedAt with server-wins tie-breaks."""
    if not isinstance(server_map_raw, dict) and not isinstance(incoming_map_raw, dict):
        return None

    server_map = server_map_raw if isinstance(server_map_raw, dict) else {}
    incoming_map = incoming_map_raw if isinstance(incoming_map_raw, dict) else {}

    merged: dict[str, Any] = {}
    keys = set(server_map.keys()) | set(incoming_map.keys())
    for key in keys:
        server_entry = _normalize_memory_entry(server_map.get(key))
        incoming_entry = _normalize_memory_entry(incoming_map.get(key))

        if server_entry is None and incoming_entry is None:
            continue
        if server_entry is None:
            merged[str(key)] = incoming_entry
            continue
        if incoming_entry is None:
            merged[str(key)] = server_entry
            continue

        server_entry_updated_at = _parse_iso_timestamp(server_entry.get("updatedAt")) or server_updated_at_epoch
        incoming_entry_updated_at = _parse_iso_timestamp(incoming_entry.get("updatedAt")) or incoming_updated_at_epoch
        if incoming_entry_updated_at > server_entry_updated_at:
            merged[str(key)] = incoming_entry
        else:
            merged[str(key)] = server_entry

    return merged


def _merge_conversation_settings(
    server_settings_raw: Any,
    incoming_settings_raw: Any,
) -> dict[str, Any]:
    """Merge settings with top-level LWW and per-entry memory map reconciliation."""
    server_settings = server_settings_raw if isinstance(server_settings_raw, dict) else {}
    incoming_settings = incoming_settings_raw if isinstance(incoming_settings_raw, dict) else {}

    server_updated_at_epoch = _parse_iso_timestamp(server_settings.get("updatedAt")) or 0.0
    incoming_updated_at_epoch = _parse_iso_timestamp(incoming_settings.get("updatedAt")) or 0.0

    incoming_wins = incoming_updated_at_epoch > server_updated_at_epoch
    if incoming_wins:
        merged = {**server_settings, **incoming_settings}
    else:
        # Server-backed ties resolve to server settings.
        merged = {**incoming_settings, **server_settings}

    merged_memory = _merge_character_memory_by_id(
        server_settings.get("characterMemoryById"),
        incoming_settings.get("characterMemoryById"),
        server_updated_at_epoch=server_updated_at_epoch,
        incoming_updated_at_epoch=incoming_updated_at_epoch,
    )
    if merged_memory is not None:
        merged["characterMemoryById"] = merged_memory

    schema_version = merged.get("schemaVersion")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version < 1:
        merged["schemaVersion"] = 2

    if incoming_wins and isinstance(incoming_settings.get("updatedAt"), str):
        merged["updatedAt"] = incoming_settings["updatedAt"]
    elif isinstance(server_settings.get("updatedAt"), str):
        merged["updatedAt"] = server_settings["updatedAt"]
    else:
        merged["updatedAt"] = datetime.now(timezone.utc).isoformat()

    return merged


def _normalize_note_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _extract_character_default_author_note(character: dict[str, Any]) -> str:
    if not isinstance(character, dict):
        return ""

    # Support direct fields and extension-based storage.
    for key in ("author_note", "authorNote", "memory_note", "memoryNote"):
        direct = _normalize_note_text(character.get(key))
        if direct:
            return direct

    extensions = character.get("extensions")
    if isinstance(extensions, str):
        try:
            extensions = json.loads(extensions)
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
            extensions = {}
    if not isinstance(extensions, dict):
        return ""

    for key in (
        "author_note",
        "authorNote",
        "default_author_note",
        "defaultAuthorNote",
        "memory_note",
        "memoryNote",
    ):
        ext_value = _normalize_note_text(extensions.get(key))
        if ext_value:
            return ext_value
    return ""


def _extract_character_memory_note(settings: dict[str, Any], character_id: Any) -> str:
    memory_by_id = settings.get("characterMemoryById")
    if not isinstance(memory_by_id, dict):
        return ""

    # Accept both raw and stringified keys for robustness across clients.
    lookup_keys = [character_id]
    if character_id is not None:
        lookup_keys.append(str(character_id))

    for key in lookup_keys:
        if key not in memory_by_id:
            continue
        entry = memory_by_id.get(key)
        if isinstance(entry, dict):
            note = _normalize_note_text(entry.get("note"))
            if note:
                return note
        else:
            note = _normalize_note_text(entry)
            if note:
                return note
    return ""


def _normalize_greeting_scope(settings: dict[str, Any]) -> str:
    scope_raw = settings.get("greetingScope")
    if isinstance(scope_raw, str) and scope_raw.strip().lower() == "character":
        return "character"
    return "chat"


def _normalize_preset_scope(settings: dict[str, Any]) -> str:
    scope_raw = settings.get("presetScope")
    if isinstance(scope_raw, str) and scope_raw.strip().lower() == "chat":
        return "chat"
    return "character"


def _normalize_memory_scope(settings: dict[str, Any]) -> str:
    scope_raw = settings.get("memoryScope")
    scope = str(scope_raw).strip().lower() if isinstance(scope_raw, str) else ""
    if scope in {"shared", "character", "both"}:
        return scope
    return "shared"


def _normalize_turn_taking_mode(settings: dict[str, Any]) -> str:
    mode_raw = settings.get("turnTakingMode")
    mode = str(mode_raw).strip().lower() if isinstance(mode_raw, str) else ""
    if mode in {"round_robin", "round-robin", "round robin"}:
        return "round_robin"
    return "single"


def _normalize_character_id(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        normalized = int(str(value).strip())
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
        return None
    if normalized <= 0:
        return None
    return normalized


def _normalize_participant_character_ids(
    settings: dict[str, Any],
    primary_character_id: Any,
) -> list[int]:
    raw_ids = settings.get("participantCharacterIds")
    if raw_ids is None:
        raw_ids = settings.get("participant_character_ids")

    parsed_ids: list[Any]
    if isinstance(raw_ids, list):
        parsed_ids = raw_ids
    elif isinstance(raw_ids, str):
        text = raw_ids.strip()
        parsed_ids = []
        if text:
            try:
                loaded = json.loads(text)
                parsed_ids = loaded if isinstance(loaded, list) else []
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                parsed_ids = [part.strip() for part in text.split(",")]
    else:
        parsed_ids = []

    ordered_ids: list[int] = []
    seen_ids: set[int] = set()

    primary_id = _normalize_character_id(primary_character_id)
    if primary_id is not None:
        ordered_ids.append(primary_id)
        seen_ids.add(primary_id)

    for value in parsed_ids:
        normalized = _normalize_character_id(value)
        if normalized is None or normalized in seen_ids:
            continue
        ordered_ids.append(normalized)
        seen_ids.add(normalized)

    return ordered_ids


def _extract_settings(settings_row: Any) -> dict[str, Any]:
    if isinstance(settings_row, dict):
        settings = settings_row.get("settings")
        if isinstance(settings, dict):
            return settings
    return {}


def _normalize_sender_aliases(names: list[str]) -> set[str]:
    aliases: set[str] = set()
    for name in names:
        if not isinstance(name, str):
            continue
        raw = name.strip().lower()
        if raw:
            aliases.add(raw)
        try:
            sanitized = sanitize_sender_name(name).strip().lower()
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
            sanitized = ""
        if sanitized:
            aliases.add(sanitized)
    return aliases


def _map_sender_to_role_with_participants(
    sender: Any,
    primary_character_name: Optional[str],
    participant_aliases: set[str],
) -> str:
    role = map_sender_to_role(
        sender if isinstance(sender, str) else None,
        primary_character_name,
        default_role="user",
    )
    if role != "user":
        return role

    if not isinstance(sender, str):
        return "user"
    sender_raw = sender.strip().lower()
    if sender_raw in participant_aliases:
        return "assistant"
    try:
        sender_sanitized = sanitize_sender_name(sender).strip().lower()
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
        sender_sanitized = ""
    if sender_sanitized and sender_sanitized in participant_aliases:
        return "assistant"
    return "user"


def _resolve_chat_turn_context(
    db: CharactersRAGDB,
    conversation: dict[str, Any],
    settings_row: Any,
    history_messages: list[dict[str, Any]],
    directed_character_id: Any = None,
) -> dict[str, Any]:
    settings = _extract_settings(settings_row)
    primary_character_id = conversation.get("character_id")
    participant_ids = _normalize_participant_character_ids(settings, primary_character_id)
    participants: list[dict[str, Any]] = []
    for participant_id in participant_ids:
        card = db.get_character_card_by_id(participant_id)
        if not isinstance(card, dict):
            continue
        name = str(card.get("name") or f"Character {participant_id}").strip()
        if not name:
            name = f"Character {participant_id}"
        participants.append(
            {"id": participant_id, "character": card, "name": name}
        )

    if not participants:
        fallback_card = db.get_character_card_by_id(primary_character_id) or {}
        fallback_id = _normalize_character_id(
            fallback_card.get("id") or primary_character_id
        ) or 0
        fallback_name = str(fallback_card.get("name") or "Assistant").strip() or "Assistant"
        participants = [
            {"id": fallback_id, "character": fallback_card, "name": fallback_name}
        ]

    turn_taking_mode = _normalize_turn_taking_mode(settings)
    if len(participants) <= 1:
        turn_taking_mode = "single"

    participant_aliases = _normalize_sender_aliases(
        [participant.get("name", "") for participant in participants]
    )
    participant_alias_to_index: dict[str, int] = {}
    for idx, participant in enumerate(participants):
        aliases = _normalize_sender_aliases([participant.get("name", "")])
        for alias in aliases:
            participant_alias_to_index.setdefault(alias, idx)
    primary_name = str(participants[0].get("name") or "Assistant")
    active_participant = participants[0]
    directed_id = _normalize_character_id(directed_character_id)
    directed_applied = False
    if directed_id is not None:
        directed_participant = next(
            (participant for participant in participants if participant.get("id") == directed_id),
            None,
        )
        if directed_participant is not None:
            active_participant = directed_participant
            directed_applied = True

    if turn_taking_mode == "round_robin" and not directed_applied:
        last_assistant_index: Optional[int] = None
        for message in reversed(history_messages):
            role = _map_sender_to_role_with_participants(
                message.get("sender"),
                primary_name,
                participant_aliases,
            )
            if role != "assistant":
                continue
            sender = message.get("sender")
            if isinstance(sender, str):
                sender_raw = sender.strip().lower()
                if sender_raw == "assistant":
                    last_assistant_index = 0
                else:
                    sender_sanitized = ""
                    try:
                        sender_sanitized = sanitize_sender_name(sender).strip().lower()
                    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                        sender_sanitized = ""
                    last_assistant_index = participant_alias_to_index.get(sender_raw)
                    if last_assistant_index is None and sender_sanitized:
                        last_assistant_index = participant_alias_to_index.get(sender_sanitized)
            if last_assistant_index is None:
                # Legacy messages may only store "assistant"; default to primary.
                last_assistant_index = 0
            break
        if last_assistant_index is not None:
            active_participant = participants[(last_assistant_index + 1) % len(participants)]

    return {
        "settings": settings,
        "participants": participants,
        "participant_aliases": participant_aliases,
        "primary_character_name": primary_name,
        "active_character_id": active_participant.get("id"),
        "active_character_name": str(active_participant.get("name") or "Assistant"),
        "active_character": active_participant.get("character") or {},
        "turn_taking_mode": turn_taking_mode,
        "directed_character_applied": directed_applied,
        "directed_character_id": directed_id if directed_applied else None,
    }


def _normalize_greeting_values(value: Any) -> list[str]:
    if isinstance(value, str):
        trimmed = value.strip()
        return [trimmed] if trimmed else []
    if isinstance(value, list):
        normalized: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                continue
            trimmed = entry.strip()
            if trimmed:
                normalized.append(trimmed)
        return normalized
    return []


def _collect_character_greeting_texts(character: dict[str, Any]) -> list[str]:
    greeting_fields = (
        "greeting",
        "first_message",
        "firstMessage",
        "greet",
        "alternate_greetings",
        "alternateGreetings",
    )
    greetings: list[str] = []
    seen: set[str] = set()
    for field_name in greeting_fields:
        values = _normalize_greeting_values(character.get(field_name))
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            greetings.append(value)
    return greetings


def _parse_greeting_selection_index(selection_id: Any) -> Optional[int]:
    if not isinstance(selection_id, str):
        return None
    parts = selection_id.strip().split(":")
    if len(parts) < 3 or parts[0] != "greeting":
        return None
    try:
        index = int(parts[1])
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
        return None
    if index < 0:
        return None
    return index


def _resolve_character_scoped_greeting(
    settings: dict[str, Any],
    character: dict[str, Any],
    char_name: str,
    user_name: str,
) -> str:
    greetings = _collect_character_greeting_texts(character)
    if not greetings:
        return ""

    selected_index = _parse_greeting_selection_index(settings.get("greetingSelectionId"))
    use_character_default = bool(settings.get("useCharacterDefault"))

    selected_greeting = ""
    if selected_index is not None and selected_index < len(greetings):
        selected_greeting = greetings[selected_index]
    elif use_character_default:
        selected_greeting = greetings[0]
    else:
        # Deterministic fallback to avoid per-request prompt drift.
        selected_greeting = greetings[0]

    return _safe_replace_placeholders(selected_greeting, char_name, user_name).strip()


def _message_sender_matches_character(
    sender: Any,
    active_character_name: str,
    primary_character_name: str,
) -> bool:
    if not isinstance(sender, str):
        return False

    active_aliases = _normalize_sender_aliases([active_character_name])
    sender_raw = sender.strip().lower()

    if sender_raw == "assistant":
        # Legacy assistant sender maps to the primary character.
        primary_aliases = _normalize_sender_aliases([primary_character_name])
        return bool(active_aliases.intersection(primary_aliases))

    if sender_raw in active_aliases:
        return True

    try:
        sender_sanitized = sanitize_sender_name(sender).strip().lower()
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
        sender_sanitized = ""
    if sender_sanitized and sender_sanitized in active_aliases:
        return True

    return False


def _has_prior_assistant_reply(
    history_messages: list[dict[str, Any]],
    primary_character_name: str,
    participant_aliases: set[str],
) -> bool:
    for message in history_messages:
        role = _map_sender_to_role_with_participants(
            message.get("sender"),
            primary_character_name,
            participant_aliases,
        )
        if role == "assistant":
            return True
    return False


def _has_prior_assistant_reply_for_character(
    history_messages: list[dict[str, Any]],
    active_character_name: str,
    primary_character_name: str,
    participant_aliases: set[str],
) -> bool:
    for message in history_messages:
        role = _map_sender_to_role_with_participants(
            message.get("sender"),
            primary_character_name,
            participant_aliases,
        )
        if role != "assistant":
            continue
        if _message_sender_matches_character(
            message.get("sender"),
            active_character_name,
            primary_character_name,
        ):
            return True
    return False


def _should_inject_character_scoped_greeting(
    settings: dict[str, Any],
    turn_context: dict[str, Any],
    history_messages: list[dict[str, Any]],
) -> bool:
    if settings.get("greetingEnabled") is False:
        return False

    greeting_scope = _normalize_greeting_scope(settings)
    if greeting_scope != "character":
        return False

    participants = turn_context.get("participants") or []
    primary_character_name = str(turn_context.get("primary_character_name") or "")
    active_character_name = str(turn_context.get("active_character_name") or "")
    participant_aliases = turn_context.get("participant_aliases") or set()

    if len(participants) <= 1:
        # Edge-case rule: one participant should behave like chat-first.
        return not _has_prior_assistant_reply(
            history_messages=history_messages,
            primary_character_name=primary_character_name,
            participant_aliases=participant_aliases,
        )

    return not _has_prior_assistant_reply_for_character(
        history_messages=history_messages,
        active_character_name=active_character_name,
        primary_character_name=primary_character_name,
        participant_aliases=participant_aliases,
    )


def _inject_character_scoped_greeting_from_settings(
    messages: list[dict[str, Any]],
    settings_row: Any,
    turn_context: dict[str, Any],
    history_messages: list[dict[str, Any]],
    user_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(settings_row, dict):
        return messages

    settings = _extract_settings(settings_row)
    if not settings:
        return messages

    if not _should_inject_character_scoped_greeting(
        settings=settings,
        turn_context=turn_context,
        history_messages=history_messages,
    ):
        return messages

    character = turn_context.get("active_character") or {}
    char_name = str(turn_context.get("active_character_name") or "Assistant")
    greeting_text = _resolve_character_scoped_greeting(
        settings=settings,
        character=character,
        char_name=char_name,
        user_name=user_name,
    )
    if not greeting_text:
        return messages

    insert_idx = len(messages)
    for idx in range(len(messages) - 1, -1, -1):
        role = str(messages[idx].get("role", "")).strip().lower()
        if role == "user":
            insert_idx = idx
            break

    if insert_idx == len(messages):
        insert_idx = 0
        while insert_idx < len(messages):
            role = str(messages[insert_idx].get("role", "")).strip().lower()
            if role != "system":
                break
            insert_idx += 1

    if insert_idx > 0:
        prev_message = messages[insert_idx - 1]
        prev_role = str(prev_message.get("role", "")).strip().lower()
        prev_content = str(prev_message.get("content", "")).strip()
        if prev_role == "assistant" and prev_content == greeting_text:
            return messages

    greeting_message = {
        "role": "assistant",
        "content": greeting_text,
    }
    return [*messages[:insert_idx], greeting_message, *messages[insert_idx:]]


def _resolve_author_note_text(settings: dict[str, Any], character: dict[str, Any]) -> str:
    # Optional toggles reserved for Stage D2 behavior; defaults keep note enabled.
    if settings.get("authorNoteEnabled") is False:
        return ""
    if settings.get("authorNoteGmOnly") is True:
        return ""
    if settings.get("authorNoteExcludeFromPrompt") is True:
        return ""

    shared_note = _normalize_note_text(settings.get("authorNote"))
    character_note = _extract_character_memory_note(settings, character.get("id"))
    if not character_note:
        character_note = _extract_character_default_author_note(character)

    scope = _normalize_memory_scope(settings)

    if scope == "character":
        note = character_note
    elif scope == "both":
        note = "\n\n".join(part for part in (shared_note, character_note) if part)
    else:
        # Shared scope: keep chat note precedence, fallback to character default.
        note = shared_note or character_note

    return note.strip()


def _resolve_author_note_position(settings: dict[str, Any]) -> Any:
    for key in (
        "authorNotePosition",
        "authorNotePlacement",
        "authorNoteInjectionPosition",
    ):
        if key in settings:
            return settings.get(key)
    return "before_system"


def _insert_author_note_at_depth(
    messages: list[dict[str, Any]],
    author_note_message: dict[str, Any],
    depth: int,
) -> list[dict[str, Any]]:
    if depth <= 0:
        return [author_note_message, *messages]

    non_system_count = 0
    for idx, message in enumerate(messages):
        role = str(message.get("role", "")).strip().lower()
        if role == "system":
            continue
        if non_system_count >= depth:
            return [*messages[:idx], author_note_message, *messages[idx:]]
        non_system_count += 1
    return [*messages, author_note_message]


def _insert_author_note_message(
    messages: list[dict[str, Any]],
    author_note_message: dict[str, Any],
    position: Any,
) -> list[dict[str, Any]]:
    if isinstance(position, int):
        return _insert_author_note_at_depth(messages, author_note_message, position)

    if isinstance(position, dict):
        mode = str(position.get("mode", "")).strip().lower()
        if mode in {"depth", "at_depth"}:
            depth = position.get("depth")
            if isinstance(depth, int):
                return _insert_author_note_at_depth(messages, author_note_message, depth)
        if mode in {"before_system", "before-system", "before"}:
            return [author_note_message, *messages]

    if isinstance(position, str):
        normalized = position.strip().lower()
        if normalized in {"before_system", "before-system", "before system", "before"}:
            return [author_note_message, *messages]
        if normalized.startswith("depth"):
            suffix = normalized.replace("depth", "", 1).strip()
            if suffix.startswith(":"):
                suffix = suffix[1:].strip()
            if suffix.isdigit():
                return _insert_author_note_at_depth(messages, author_note_message, int(suffix))

    return [author_note_message, *messages]


def _inject_author_note_from_settings(
    messages: list[dict[str, Any]],
    settings_row: Any,
    character: dict[str, Any],
    char_name: str,
    user_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(settings_row, dict):
        return messages
    settings = settings_row.get("settings")
    if not isinstance(settings, dict):
        return messages

    note_text = _resolve_author_note_text(settings, character)
    if not note_text:
        return messages

    resolved_note = _safe_replace_placeholders(note_text, char_name, user_name).strip()
    if not resolved_note:
        return messages

    author_note_message = {
        "role": "system",
        "content": f"Author's note:\n{resolved_note}",
    }
    position = _resolve_author_note_position(settings)
    return _insert_author_note_message(messages, author_note_message, position)


def _coerce_truthy_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_positive_int(
    value: Any,
    default: int,
    *,
    min_value: int = 1,
    max_value: int = 10_000,
) -> int:
    try:
        parsed = int(value)
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
        return default
    if parsed < min_value:
        return min_value
    if parsed > max_value:
        return max_value
    return parsed


def _resolve_auto_summary_config(settings: dict[str, Any]) -> tuple[bool, int, int]:
    summary_block = settings.get("summary")
    summary_block = summary_block if isinstance(summary_block, dict) else {}

    enabled = _coerce_truthy_bool(
        settings.get(
            "autoSummaryEnabled",
            summary_block.get("enabled", False),
        ),
        default=False,
    )

    threshold_raw = settings.get("autoSummaryThresholdMessages")
    if threshold_raw is None:
        threshold_raw = settings.get("autoSummaryMessageThreshold")
    if threshold_raw is None:
        threshold_raw = summary_block.get("thresholdMessages")
    if threshold_raw is None:
        threshold_raw = summary_block.get("messageThreshold")
    threshold = _coerce_positive_int(
        threshold_raw if threshold_raw is not None else DEFAULT_AUTO_SUMMARY_THRESHOLD_MESSAGES,
        DEFAULT_AUTO_SUMMARY_THRESHOLD_MESSAGES,
        min_value=2,
        max_value=5_000,
    )

    window_raw = settings.get("autoSummaryWindowMessages")
    if window_raw is None:
        window_raw = settings.get("autoSummaryRecentWindow")
    if window_raw is None:
        window_raw = summary_block.get("windowMessages")
    if window_raw is None:
        window_raw = summary_block.get("recentWindowMessages")
    window = _coerce_positive_int(
        window_raw if window_raw is not None else DEFAULT_AUTO_SUMMARY_WINDOW_MESSAGES,
        DEFAULT_AUTO_SUMMARY_WINDOW_MESSAGES,
        min_value=1,
        max_value=2_000,
    )

    if window >= threshold:
        window = max(1, threshold - 1)

    return enabled, threshold, window


def _collect_pinned_message_ids(
    db: CharactersRAGDB,
    settings: dict[str, Any],
    prompt_messages: list[dict[str, Any]],
) -> set[str]:
    pinned_ids: set[str] = set()

    raw_pinned_ids = settings.get("pinnedMessageIds")
    if isinstance(raw_pinned_ids, list):
        for entry in raw_pinned_ids:
            if entry is None:
                continue
            text = str(entry).strip()
            if text:
                pinned_ids.add(text)

    for message in prompt_messages:
        message_id_raw = message.get("id")
        if message_id_raw is None:
            continue
        message_id = str(message_id_raw).strip()
        if not message_id:
            continue
        try:
            metadata = db.get_message_metadata(message_id) or {}
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
            continue
        extra = metadata.get("extra")
        if not isinstance(extra, dict):
            continue
        if _coerce_truthy_bool(extra.get("pinned"), default=False):
            pinned_ids.add(message_id)
    return pinned_ids


def _build_deterministic_conversation_summary(
    messages_to_summarize: list[dict[str, Any]],
    primary_character_name: str,
    participant_aliases: set[str],
    char_name: str,
    user_name: str,
) -> str:
    lines: list[str] = []
    for message in messages_to_summarize:
        role = _map_sender_to_role_with_participants(
            message.get("sender"),
            primary_character_name,
            participant_aliases,
        )
        content = _safe_replace_placeholders(
            message.get("content"),
            char_name,
            user_name,
        )
        content = " ".join(content.split()).strip()
        if not content:
            continue
        if len(content) > MAX_AUTO_SUMMARY_LINE_CHARS:
            content = f"{content[: MAX_AUTO_SUMMARY_LINE_CHARS - 3].rstrip()}..."
        lines.append(f"- {role}: {content}")
        if len(lines) >= MAX_AUTO_SUMMARY_LINES:
            break

    if not lines:
        return ""

    summary_content = "\n".join(lines)
    if len(summary_content) > MAX_AUTO_SUMMARY_CONTENT_CHARS:
        summary_content = summary_content[:MAX_AUTO_SUMMARY_CONTENT_CHARS].rstrip()
    return summary_content


def _summary_matches_existing(
    existing_summary: Any,
    content: str,
    source_from_id: str,
    source_to_id: str,
    threshold: int,
    window: int,
    compressed_count: int,
) -> bool:
    if not isinstance(existing_summary, dict):
        return False
    if existing_summary.get("content") != content:
        return False
    source_range = existing_summary.get("sourceRange")
    if not isinstance(source_range, dict):
        return False
    if str(source_range.get("fromMessageId") or "") != source_from_id:
        return False
    if str(source_range.get("toMessageId") or "") != source_to_id:
        return False
    if int(existing_summary.get("thresholdMessages") or -1) != threshold:
        return False
    if int(existing_summary.get("windowMessages") or -1) != window:
        return False
    if int(existing_summary.get("compressedCount") or -1) != compressed_count:
        return False
    return True


def _persist_auto_summary_to_settings(
    db: CharactersRAGDB,
    chat_id: str,
    settings: dict[str, Any],
    content: str,
    source_from_id: str,
    source_to_id: str,
    threshold: int,
    window: int,
    compressed_count: int,
) -> None:
    existing_summary = settings.get("summary")
    if _summary_matches_existing(
        existing_summary,
        content=content,
        source_from_id=source_from_id,
        source_to_id=source_to_id,
        threshold=threshold,
        window=window,
        compressed_count=compressed_count,
    ):
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    merged_settings = dict(settings)
    merged_settings["summary"] = {
        "enabled": True,
        "content": content,
        "sourceRange": {
            "fromMessageId": source_from_id,
            "toMessageId": source_to_id,
        },
        "thresholdMessages": threshold,
        "windowMessages": window,
        "compressedCount": compressed_count,
        "updatedAt": now_iso,
    }
    merged_settings["schemaVersion"] = int(merged_settings.get("schemaVersion") or 2)
    merged_settings["updatedAt"] = now_iso

    try:
        _validate_chat_settings_payload(merged_settings)
        if db.upsert_conversation_settings(chat_id, merged_settings):
            _touch_conversation_metadata(db, chat_id)
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(
            "Non-fatal: failed to persist auto-summary settings for chat {}: {}",
            chat_id,
            exc,
        )


def _apply_auto_summary_to_prompt_messages(
    db: CharactersRAGDB,
    chat_id: str,
    settings_row: Any,
    prompt_messages: list[dict[str, Any]],
    *,
    offset: int,
    primary_character_name: str,
    participant_aliases: set[str],
    char_name: str,
    user_name: str,
) -> tuple[list[dict[str, Any]], str]:
    if offset != 0 or not prompt_messages:
        return prompt_messages, ""
    settings = _extract_settings(settings_row)
    if not settings:
        return prompt_messages, ""

    enabled, threshold, window = _resolve_auto_summary_config(settings)
    if not enabled:
        return prompt_messages, ""
    if len(prompt_messages) <= threshold:
        return prompt_messages, ""
    if len(prompt_messages) <= window:
        return prompt_messages, ""

    older_messages = prompt_messages[:-window]
    if not older_messages:
        return prompt_messages, ""

    pinned_ids = _collect_pinned_message_ids(
        db=db,
        settings=settings,
        prompt_messages=prompt_messages,
    )

    compressible: list[dict[str, Any]] = []
    compressible_ids: set[str] = set()
    compressible_object_ids: set[int] = set()
    for message in older_messages:
        message_id_raw = message.get("id")
        message_id = str(message_id_raw).strip() if message_id_raw is not None else ""
        if message_id and message_id in pinned_ids:
            continue
        compressible.append(message)
        if message_id:
            compressible_ids.add(message_id)
        else:
            compressible_object_ids.add(id(message))

    if not compressible:
        return prompt_messages, ""

    summary_content = _build_deterministic_conversation_summary(
        messages_to_summarize=compressible,
        primary_character_name=primary_character_name,
        participant_aliases=participant_aliases,
        char_name=char_name,
        user_name=user_name,
    )
    if not summary_content:
        return prompt_messages, ""

    summarized_messages: list[dict[str, Any]] = []
    for message in prompt_messages:
        message_id_raw = message.get("id")
        message_id = str(message_id_raw).strip() if message_id_raw is not None else ""
        if message_id and message_id in compressible_ids:
            continue
        if not message_id and id(message) in compressible_object_ids:
            continue
        summarized_messages.append(message)

    first_id_raw = compressible[0].get("id")
    last_id_raw = compressible[-1].get("id")
    source_from_id = str(first_id_raw).strip() if first_id_raw is not None else ""
    source_to_id = str(last_id_raw).strip() if last_id_raw is not None else ""
    if source_from_id and source_to_id:
        _persist_auto_summary_to_settings(
            db=db,
            chat_id=chat_id,
            settings=settings,
            content=summary_content,
            source_from_id=source_from_id,
            source_to_id=source_to_id,
            threshold=threshold,
            window=window,
            compressed_count=len(compressible),
        )

    return summarized_messages, summary_content


def _resolve_message_steering_flags(
    continue_as_user: Any,
    impersonate_user: Any,
    force_narrate: Any,
) -> tuple[bool, bool, bool, bool]:
    continue_flag = bool(continue_as_user)
    impersonate_flag = bool(impersonate_user)
    narrate_flag = bool(force_narrate)
    had_conflict = continue_flag and impersonate_flag
    if had_conflict:
        # PRD precedence: impersonate wins when both are selected.
        continue_flag = False
        impersonate_flag = True
    return continue_flag, impersonate_flag, narrate_flag, had_conflict


def _build_message_steering_instruction(
    continue_as_user: bool,
    impersonate_user: bool,
    force_narrate: bool,
) -> str:
    instructions: list[str] = []
    if impersonate_user:
        instructions.append(
            "Write this reply as if it is authored by the user, in first person, while preserving the user's intent."
        )
    elif continue_as_user:
        instructions.append(
            "Continue the user's current thought in the same voice and perspective."
        )
    if force_narrate:
        instructions.append("Use narrative prose style for this reply.")
    if not instructions:
        return ""
    return f"Steering instruction (single response): {' '.join(instructions)}"


def _inject_message_steering_instruction(
    messages: list[dict[str, Any]],
    continue_as_user: Any,
    impersonate_user: Any,
    force_narrate: Any,
) -> tuple[list[dict[str, Any]], bool]:
    continue_flag, impersonate_flag, narrate_flag, had_conflict = (
        _resolve_message_steering_flags(
            continue_as_user=continue_as_user,
            impersonate_user=impersonate_user,
            force_narrate=force_narrate,
        )
    )
    instruction = _build_message_steering_instruction(
        continue_as_user=continue_flag,
        impersonate_user=impersonate_flag,
        force_narrate=narrate_flag,
    )
    if not instruction:
        return messages, had_conflict

    steering_message = {"role": "system", "content": instruction}

    # Keep steering scoped to the upcoming turn by inserting before the latest user message.
    for idx in range(len(messages) - 1, -1, -1):
        role = str(messages[idx].get("role", "")).strip().lower()
        if role == "user":
            return [*messages[:idx], steering_message, *messages[idx:]], had_conflict

    return [*messages, steering_message], had_conflict

"""Role mapping provided by Character_Chat utility: map_sender_to_role"""

# ========================================================================
# Chat Session Endpoints
# ========================================================================

@router.post("/", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED,
             summary="Create a new chat session", tags=["Chat Sessions"])
async def create_chat_session(
    session_data: ChatSessionCreate,
    response: Response,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
    seed_first_message: bool = Query(False, description="If true, seed the chat with an initial assistant greeting"),
    greeting_strategy: Literal["default", "alternate_random", "alternate_index"] = Query("default", description="How to choose the initial assistant greeting when seeding"),
    alternate_index: Optional[int] = Query(None, ge=0, description="Index for alternate greeting when greeting_strategy=alternate_index"),
):
    """
    Create a new chat session with a character.

    Args:
        session_data: Chat session creation data
        db: Database instance
        current_user: Authenticated user

    Notes:
        This API does not automatically create a first assistant message. Clients
        should POST a first user/assistant message after chat creation. The library
        helper `start_new_chat_session` can seed a first message when used directly.

    Returns:
        Created chat session details

    Raises:
        HTTPException: 404 if character not found, 429 if rate limited
    """
    try:
        # Check rate limits
        rate_limiter = get_character_rate_limiter()
        await rate_limiter.check_rate_limit(current_user.id, "chat_create")
        # Enforce per-user chat count limit (approximate by scanning conversations per character)
        try:
            # Use DB-layer count for efficiency/accuracy. The helper expects
            # the current count (before this create) and rejects when
            # current_chat_count >= max_chats_per_user.
            user_chat_count = db.count_conversations_for_user(str(current_user.id))
            await rate_limiter.check_chat_limit(current_user.id, user_chat_count)
        except HTTPException:
            # Propagate enforcement failures
            raise
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
            # Fail closed: quota enforcement must work to prevent resource exhaustion
            logger.error("Chat limit enforcement failed, denying request: {}", e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Quota enforcement unavailable. Please try again later."
            ) from e

        # Verify character exists
        character = db.get_character_card_by_id(session_data.character_id)
        if not character:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character with ID {session_data.character_id} not found"
            )

        # Validate parent conversation (if any) for ownership and root lineage
        parent_conversation = None
        validated_parent_id: Optional[str] = None
        parent_root_id: Optional[str] = None
        if session_data.parent_conversation_id:
            parent_conversation = db.get_conversation_by_id(session_data.parent_conversation_id)
            _verify_chat_ownership(parent_conversation, current_user.id, session_data.parent_conversation_id)
            if parent_conversation:
                validated_parent_id = parent_conversation.get("id") or session_data.parent_conversation_id
                parent_root_id = parent_conversation.get("root_id") or parent_conversation.get("id")
            # Cross-character forks are intentionally supported; do not enforce a character_id match.

        # Generate chat ID and title
        chat_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        title = session_data.title or f"{character['name']} Chat ({timestamp})"

        # Create conversation data
        conv_data = {
            'id': chat_id,
            'character_id': session_data.character_id,
            'title': title,
            'root_id': parent_root_id or chat_id,  # Inherit root for forks
            'parent_conversation_id': validated_parent_id,
            'client_id': str(current_user.id),
            'version': 1,
            'state': session_data.state,
            'topic_label': session_data.topic_label,
            'cluster_id': session_data.cluster_id,
            'source': session_data.source,
            'external_ref': session_data.external_ref,
        }

        # Add to database
        created_id = db.add_conversation(conv_data)
        if not created_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create chat session"
            )

        # Retrieve created conversation
        created_conv = db.get_conversation_by_id(created_id)
        if not created_conv:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created chat session"
            )

        # Optionally seed the chat with a greeting (first_message or alternate)
        seed_status: Optional[str] = None
        if seed_first_message:
            try:
                raw_name = character.get('name') or 'Assistant'
                choice_text: Optional[str] = None
                if greeting_strategy in {"alternate_random", "alternate_index"}:
                    ag = character.get('alternate_greetings')
                    if isinstance(ag, list) and ag:
                        if greeting_strategy == "alternate_random":
                            choice_text = random.choice(ag)
                        elif greeting_strategy == "alternate_index" and isinstance(alternate_index, int) and 0 <= alternate_index < len(ag):
                            choice_text = ag[alternate_index]
                if not choice_text:
                    fm = character.get('first_message')
                    if isinstance(fm, str) and fm.strip():
                        choice_text = fm
                if isinstance(choice_text, str) and choice_text.strip():
                    content = choice_text
                    post_message_to_conversation(
                        db=db,
                        conversation_id=created_id,
                        character_name=raw_name,
                        message_content=content,
                        is_user_message=False,
                    )
                    # Update in-memory message count (best-effort)
                    try:
                        created_conv['message_count'] = (created_conv.get('message_count') or 0) + 1
                    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                        pass
                    seed_status = "ok"
                else:
                    seed_status = "no_greeting"
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as _seed_err:
                seed_status = "failed"
                logger.warning(f"Failed to seed first message for chat {created_id}: {_seed_err}")

        if response is not None and seed_status is not None:
            try:
                response.headers["X-Chat-Seed-Status"] = seed_status
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug("Failed to set X-Chat-Seed-Status header: {}", exc)

        # Log creation
        logger.info(f"Created chat session {created_id} for character {session_data.character_id} by user {current_user.id}")

        return _convert_db_conversation_to_response(created_conv)

    except HTTPException:
        raise
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error creating chat session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating chat session"
        )


@router.get("/{chat_id}", response_model=ChatSessionResponse,
            summary="Get chat session details", tags=["Chat Sessions"])
async def get_chat_session(
    chat_id: str = Path(..., description="Chat session ID"),
    include_settings: bool = Query(
        False,
        description="Include per-chat settings payload in the response.",
    ),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    Get details of a specific chat session.

    Args:
        chat_id: Chat session ID
        db: Database instance
        current_user: Authenticated user

    Returns:
        Chat session details

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized
    """
    try:
        conversation = db.get_conversation_by_id(chat_id)
        _verify_chat_ownership(conversation, current_user.id, chat_id)

        # Get message count efficiently
        try:
            conversation['message_count'] = db.count_messages_for_conversation(chat_id)
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
            messages = db.get_messages_for_conversation(chat_id, limit=1000)
            conversation['message_count'] = len(messages) if messages else 0

        settings_payload: Optional[dict[str, Any]] = None
        if include_settings:
            settings_row = db.get_conversation_settings(chat_id)
            settings_payload = (settings_row or {}).get("settings") or {}

        return _convert_db_conversation_to_response(
            conversation,
            settings=settings_payload,
        )

    except HTTPException:
        raise
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error getting chat session {chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving chat session"
        )


@router.get("/{chat_id}/context", summary="Get chat context for completions", tags=["Chat Sessions"])
async def get_chat_context(
    chat_id: str = Path(..., description="Chat session ID"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """Return chat context formatted for chat completions."""
    try:
        conversation = db.get_conversation_by_id(chat_id)
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat session {chat_id} not found")

        _verify_chat_ownership(conversation, current_user.id, chat_id)

        settings_row = db.get_conversation_settings(chat_id)
        history_messages = db.get_messages_for_conversation(chat_id, limit=1000, offset=0) or []
        history_messages = [m for m in history_messages if not m.get('deleted')]
        turn_context = _resolve_chat_turn_context(
            db=db,
            conversation=conversation,
            settings_row=settings_row,
            history_messages=history_messages,
        )
        character = turn_context.get("active_character") or {}
        char_name = turn_context.get("active_character_name") or "Unknown"
        participant_aliases = turn_context.get("participant_aliases") or set()
        primary_character_name = turn_context.get("primary_character_name")
        user_name = conversation.get('user_name', 'User')

        messages = history_messages
        # Map DB messages to chat-completions messages with normalized roles
        formatted = []
        for m in messages:
            role = _map_sender_to_role_with_participants(
                m.get('sender'),
                primary_character_name,
                participant_aliases,
            )
            content = _safe_replace_placeholders(m.get('content'), char_name, user_name)
            formatted.append({"role": role, "content": content})

        # If no messages, include first_message as an initial assistant message (with placeholders resolved)
        if not formatted and character.get('first_message'):
            fm = _safe_replace_placeholders(character.get('first_message'), char_name, user_name)
            formatted.append({"role": "assistant", "content": fm})

        return {"character_name": char_name, "messages": formatted}

    except HTTPException:
        raise
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error getting chat context for {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while retrieving chat context")


@router.post(
    "/{chat_id}/complete",
    summary="Legacy completion endpoint with simple rate limit",
    tags=["Chat Sessions"],
    deprecated=True,
    description=(
        "DEPRECATED: The request body for this endpoint is ignored and will be rejected in a future release. "
        "Call this endpoint without a body. Prefer /{chat_id}/completions or /{chat_id}/complete-v2."
    ),
)
async def complete_chat_legacy(
    chat_id: str = Path(..., description="Chat session ID"),
    body: Optional[dict[str, Any]] = Body(
        default=None,
        description=(
            "DEPRECATED: Request body is ignored. This parameter will be removed and non-empty bodies will be rejected (422) in a future release."
        ),
    ),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
    response: Response = None,
):
    """Legacy completion endpoint used by tests to validate rate limiting.

    Applies a very small per-conversation throttle when TEST_MODE=true so that
    burst requests trigger HTTP 429 as expected by tests.
    """
    try:
        # Validate chat ownership
        conversation = db.get_conversation_by_id(chat_id)
        _verify_chat_ownership(conversation, current_user.id, chat_id)

        # Per-minute completion limiter (global per-user)
        rate_limiter = get_character_rate_limiter()
        await rate_limiter.check_chat_completion_rate(current_user.id)

        # Deprecation headers for clients; also used if we reject a non-empty body
        # Sunset date is configurable via DEPRECATION_SUNSET_DAYS env var (default 90 days)
        try:
            from datetime import datetime, timedelta
            from datetime import timezone as _tz
            sunset_days = int(os.getenv("DEPRECATION_SUNSET_DAYS", "90"))
            sunset = (datetime.now(_tz.utc) + timedelta(days=sunset_days)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
            sunset = "Tue, 31 Dec 2025 00:00:00 GMT"
        dep_headers = {
            "Deprecation": "true",
            "Sunset": sunset,
            "Link": f"</api/v1/chats/{chat_id}/complete-v2>; rel=successor-version",
        }
        try:
            if response is not None:
                for k, v in dep_headers.items():
                    response.headers[k] = v
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(
                "Non-fatal: failed to set deprecation headers for chat {}: {}",
                chat_id,
                exc,
            )

        # If a non-empty body was provided, reject with 422 and include deprecation headers
        if isinstance(body, dict) and body:
            logger.warning("Legacy /complete rejected non-empty body; clients must omit the request body.")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Request body is deprecated and must be omitted. Use /{chat_id}/complete-v2 or /{chat_id}/completions.",
                headers=dep_headers,
            )

        # Test-mode throttle: 5 requests per second per (user, chat)
        key = f"{current_user.id}:{chat_id}"
        allowed = await _complete_windows.check_and_record(
            key,
            max_hits=5,
            window_seconds=1.0,
        )
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded for chat completion")

        # Return a minimal success payload
        return {"status": "ok", "chat_id": chat_id}

    except HTTPException:
        raise
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error in legacy complete for {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during completion")


@router.post("/{chat_id}/completions", response_model=CharacterChatCompletionPrepResponse,
             summary="Prepare messages for chat completion (rate-limited)", tags=["Chat Sessions"])
async def prepare_chat_completion(
    chat_id: str = Path(..., description="Chat session ID"),
    body: CharacterChatCompletionPrepRequest = None,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """Prepare chat messages for use with the main Chat API, enforcing per-minute completion limits.

    This endpoint does not call an LLM. It returns messages formatted for
    POST /api/v1/chat/completions and applies the per-minute completion limiter.
    """
    try:
        body = body or CharacterChatCompletionPrepRequest()

        # Validate chat ownership
        conversation = db.get_conversation_by_id(chat_id)
        _verify_chat_ownership(conversation, current_user.id, chat_id)

        # Per-minute completion limiter (global per-user)
        rate_limiter = get_character_rate_limiter()
        await rate_limiter.check_chat_completion_rate(current_user.id)

        # Build messages
        user_name = conversation.get('user_name', 'User')
        include_ctx = bool(body.include_character_context)
        # Fields are validated by Pydantic; avoid redundant int() casting
        limit = body.limit
        offset = body.offset
        settings_row = db.get_conversation_settings(chat_id)

        messages = db.get_messages_for_conversation(chat_id, limit=limit, offset=offset) or []
        # Filter deleted
        messages = [m for m in messages if not m.get('deleted')]
        paginated = messages
        history_messages = db.get_messages_for_conversation(chat_id, limit=1000, offset=0) or []
        history_messages = [m for m in history_messages if not m.get('deleted')]

        turn_context = _resolve_chat_turn_context(
            db=db,
            conversation=conversation,
            settings_row=settings_row,
            history_messages=history_messages,
            directed_character_id=body.directed_character_id,
        )
        if (
            body.directed_character_id is not None
            and not turn_context.get("directed_character_applied")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="directed_character_id must reference a selected participant in this chat",
            )
        character = turn_context.get("active_character") or {}
        character_name = turn_context.get("active_character_name")
        char_label = character_name or "Assistant"
        participant_aliases = turn_context.get("participant_aliases") or set()
        primary_character_name = turn_context.get("primary_character_name")
        summary_content = ""
        paginated, summary_content = _apply_auto_summary_to_prompt_messages(
            db=db,
            chat_id=chat_id,
            settings_row=settings_row,
            prompt_messages=paginated,
            offset=offset,
            primary_character_name=primary_character_name or "",
            participant_aliases=participant_aliases,
            char_name=char_label,
            user_name=user_name,
        )

        formatted: list[dict[str, Any]] = []
        if include_ctx and character and offset == 0:
            sys_text = build_character_system_prompt(character, char_label, user_name)
            if sys_text.strip():
                formatted.append({"role": "system", "content": sys_text.strip()})
        if summary_content:
            formatted.append(
                {"role": "system", "content": f"Conversation summary:\n{summary_content}"}
            )

        for msg in paginated:
            formatted.append({
                "role": _map_sender_to_role_with_participants(
                    msg.get('sender'),
                    primary_character_name,
                    participant_aliases,
                ),
                "content": _safe_replace_placeholders(msg.get('content'), char_label, user_name)
            })

        if body.append_user_message:
            formatted.append({"role": "user", "content": body.append_user_message})

        formatted = _inject_character_scoped_greeting_from_settings(
            formatted,
            settings_row=settings_row,
            turn_context=turn_context,
            history_messages=history_messages,
            user_name=user_name,
        )
        formatted = _inject_author_note_from_settings(
            formatted,
            settings_row=settings_row,
            character=character,
            char_name=char_label,
            user_name=user_name,
        )
        formatted, steering_conflict = _inject_message_steering_instruction(
            formatted,
            continue_as_user=body.continue_as_user,
            impersonate_user=body.impersonate_user,
            force_narrate=body.force_narrate,
        )
        if steering_conflict:
            logger.debug(
                "Steering conflict resolved for chat {} in /completions prep: impersonate_user overrides continue_as_user",
                chat_id,
            )

        return CharacterChatCompletionPrepResponse(
            chat_id=chat_id,
            character_id=turn_context.get("active_character_id") or conversation['character_id'],
            character_name=character_name,
            messages=formatted,
            total=len(messages)
        )

    except HTTPException:
        raise
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error preparing completion for {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while preparing completion")


@router.post(
    "/{chat_id}/complete-v2",
    response_model=CharacterChatCompletionV2Response,
    summary="Character Chat completion (operational, rate-limited)",
    description=(
        "Builds context from the chat and calls a provider.\n\n"
        "Streaming: when stream=true, response is sent as SSE and assistant content is NOT persisted,"
        " even if save_to_db=true. Use non-streaming to persist, or persist manually after streaming."
    ),
    tags=["Chat Sessions"],
)
async def character_chat_completion(
    chat_id: str = Path(..., description="Chat session ID"),
    body: CharacterChatCompletionV2Request = None,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """Perform a character chat completion using configured providers and persist results optionally.

    Behavior:
    - Enforces per-minute completion limiter (per-user)
    - Builds message context from the chat (and optional appended user message)
    - Calls provider via unified chat function
    - Persists appended user message and assistant reply when save_to_db is true

    Streaming behavior:
    - When `stream=True`, the response is returned as SSE and the assistant
      content is not persisted even if `save_to_db=True`. Use non-streaming
      mode to persist or persist separately after streaming completes.
    """
    try:
        import os
        body = body or CharacterChatCompletionV2Request()

        # Validate and ownership
        conversation = db.get_conversation_by_id(chat_id)
        _verify_chat_ownership(conversation, current_user.id, chat_id)

        # Prepare rate limiter
        rate_limiter = get_character_rate_limiter()

        # Gather character and context
        user_name = conversation.get('user_name', 'User')
        include_ctx = bool(body.include_character_context)
        limit = body.limit
        offset = body.offset
        stream_requested = bool(body.stream)
        save_to_db = body.save_to_db
        settings_row = db.get_conversation_settings(chat_id)
        history_messages = db.get_messages_for_conversation(chat_id, limit=1000, offset=0) or []
        history_messages = [m for m in history_messages if not m.get('deleted')]
        turn_context = _resolve_chat_turn_context(
            db=db,
            conversation=conversation,
            settings_row=settings_row,
            history_messages=history_messages,
            directed_character_id=body.directed_character_id,
        )
        if (
            body.directed_character_id is not None
            and not turn_context.get("directed_character_applied")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="directed_character_id must reference a selected participant in this chat",
            )
        character = turn_context.get("active_character") or {}
        active_character_id = turn_context.get("active_character_id")
        active_character_name = turn_context.get("active_character_name")
        char_label = active_character_name or "Assistant"
        participant_aliases = turn_context.get("participant_aliases") or set()
        primary_character_name = turn_context.get("primary_character_name")
        character_generation_settings = resolve_character_generation_settings(character)
        resolved_temperature = (
            body.temperature
            if body.temperature is not None
            else character_generation_settings.get("temperature")
        )
        resolved_top_p = (
            body.top_p
            if body.top_p is not None
            else character_generation_settings.get("top_p")
        )
        resolved_repetition_penalty = (
            body.repetition_penalty
            if body.repetition_penalty is not None
            else character_generation_settings.get("repetition_penalty")
        )
        resolved_stop = (
            body.stop
            if body.stop is not None
            else character_generation_settings.get("stop")
        )
        if save_to_db is None:
            # Default from Chat API settings when not specified explicitly.
            try:
                from tldw_Server_API.app.api.v1.endpoints.chat import DEFAULT_SAVE_TO_DB as CHAT_DEFAULT_SAVE
                save_to_db = CHAT_DEFAULT_SAVE
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                save_to_db = False
        will_persist = bool(save_to_db) and not stream_requested

        messages = db.get_messages_for_conversation(chat_id, limit=limit, offset=offset) or []
        messages = [m for m in messages if not m.get('deleted')]
        paginated = messages
        summary_content = ""
        paginated, summary_content = _apply_auto_summary_to_prompt_messages(
            db=db,
            chat_id=chat_id,
            settings_row=settings_row,
            prompt_messages=paginated,
            offset=offset,
            primary_character_name=primary_character_name or "",
            participant_aliases=participant_aliases,
            char_name=char_label,
            user_name=user_name,
        )

        formatted: list[dict[str, Any]] = []
        if include_ctx and character and offset == 0:
            sys_text = build_character_system_prompt(character, char_label, user_name)
            if sys_text.strip():
                formatted.append({"role": "system", "content": sys_text.strip()})
        if summary_content:
            formatted.append(
                {"role": "system", "content": f"Conversation summary:\n{summary_content}"}
            )

        for msg in paginated:
            formatted.append({
                "role": _map_sender_to_role_with_participants(
                    msg.get('sender'),
                    primary_character_name,
                    participant_aliases,
                ),
                "content": _safe_replace_placeholders(msg.get('content'), char_label, user_name)
            })

        # Optional appended user message
        appended_user_id: Optional[str] = None
        if body.append_user_message:
            formatted.append({"role": "user", "content": body.append_user_message})

        formatted = _inject_character_scoped_greeting_from_settings(
            formatted,
            settings_row=settings_row,
            turn_context=turn_context,
            history_messages=history_messages,
            user_name=user_name,
        )
        formatted = _inject_author_note_from_settings(
            formatted,
            settings_row=settings_row,
            character=character,
            char_name=char_label,
            user_name=user_name,
        )
        formatted, steering_conflict = _inject_message_steering_instruction(
            formatted,
            continue_as_user=body.continue_as_user,
            impersonate_user=body.impersonate_user,
            force_narrate=body.force_narrate,
        )
        if steering_conflict:
            logger.debug(
                "Steering conflict resolved for chat {} in /complete-v2: impersonate_user overrides continue_as_user",
                chat_id,
            )

        # Determine provider/model with safe defaults for test/offline
        provider = (body.provider or os.getenv("CHAR_CHAT_PROVIDER") or "local-llm").strip()
        model = (body.model or os.getenv("CHAR_CHAT_MODEL") or "local-test").strip()

        # If we will persist, ensure message cap won't be exceeded.
        # Otherwise enforce a soft cap for non-persisted completions.
        try:
            current_count = db.count_messages_for_conversation(chat_id)
            if will_persist:
                will_add = 1 if body.append_user_message else 0
                will_add += 1  # assistant reply
                await rate_limiter.check_message_limit(chat_id, current_count + will_add)
            else:
                await rate_limiter.check_soft_message_limit(chat_id, current_count)
        except HTTPException:
            raise
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
            logger.debug("Non-fatal: message cap pre-check skipped")

        # Resolve BYOK credentials (fall back to env/config)
        def _fallback_resolver(name: str) -> Optional[str]:
            try:
                from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import get_api_keys
                return get_api_keys().get(name)
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                return None

        user_id_int: Optional[int] = None
        if hasattr(current_user, "id_int"):
            user_id_int = current_user.id_int
        elif hasattr(current_user, "id"):
            try:
                user_id_int = int(current_user.id)
            except (TypeError, ValueError):
                pass

        byok_resolution = await resolve_byok_credentials(
            provider,
            user_id=user_id_int,
            fallback_resolver=_fallback_resolver,
        )
        api_key = byok_resolution.api_key
        provider_key = (provider or "").strip().lower()
        if provider_requires_api_key(provider_key) and not api_key:
            record_byok_missing_credentials(provider_key, operation="character_chat")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "missing_provider_credentials",
                    "message": f"Provider '{provider}' requires an API key.",
                },
            )

        # Attempt provider call; allow offline simulation for local-llm in test/dev.
        # Offline simulation toggle (supports new flags for clarity, backward compatible with ALLOW_LOCAL_LLM_CALLS)
        enable_local_llm = parse_boolean(os.getenv("ENABLE_LOCAL_LLM_PROVIDER"))
        disable_offline_sim = parse_boolean(os.getenv("DISABLE_OFFLINE_SIM"))
        legacy_allow_local = parse_boolean(os.getenv("ALLOW_LOCAL_LLM_CALLS"))
        offline_sim = provider == "local-llm" and not (enable_local_llm or disable_offline_sim or legacy_allow_local)
        streams_unified = str(os.getenv("STREAMS_UNIFIED", "0")).strip().lower() in {"1", "true", "on", "yes"}
        llm_resp = None
        if not offline_sim:
            # Enforce per-minute completion rate only for real provider calls
            await rate_limiter.check_chat_completion_rate(current_user.id)
            try:
                llm_resp = perform_chat_api_call(
                    api_endpoint=provider,
                    messages_payload=formatted,
                    api_key=api_key,
                    temp=resolved_temperature,
                    top_p=resolved_top_p,
                    repetition_penalty=resolved_repetition_penalty,
                    stop=resolved_stop,
                    model=model,
                    max_tokens=body.max_tokens,
                    tools=body.tools,
                    tool_choice=body.tool_choice,
                    streaming=bool(body.stream),
                    user_identifier=str(current_user.id),
                    app_config=byok_resolution.app_config,
                )
                # Support async-returning provider hooks (test stubs or adapters)
                try:
                    if asyncio.iscoroutine(llm_resp):
                        llm_resp = await llm_resp  # type: ignore
                except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
                    logger.error(f"Failed to await async LLM response: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="LLM provider error"
                    ) from e
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
                logger.error(f"Chat provider call failed: {e}")
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat provider error") from e
            await byok_resolution.touch_last_used()

        # Helper: Convert a provider chunk into a single SSE-formatted line
        def _coerce_sse_line(chunk: Any) -> Optional[str]:
            """Convert a provider chunk into a single SSE-formatted line.

            Prefer provider iterator output (already normalized). If chunk is not a
            string, attempt normalization; return None when nothing to forward.
            """
            try:
                if chunk is None:
                    return None
                if isinstance(chunk, (bytes, bytearray)):
                    text = chunk.decode("utf-8", errors="replace")
                elif isinstance(chunk, str):
                    text = chunk
                else:
                    # As a fallback, stringify and normalize
                    text = str(chunk)
                if not text:
                    return None
                # If line looks like SSE control or data, keep as-is; otherwise normalize
                lower = text.strip().lower()
                if lower.startswith("data:") or lower.startswith("event:") or lower.startswith("id:") or lower.startswith("retry:") or lower.startswith(":"):
                    return ensure_sse_line(text.strip())
                normalized = normalize_provider_line(text)
                return normalized
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                return None

        # Extract assistant content from LLM response
        def _extract_text(resp: Any) -> str:
            if resp is None:
                return ""
            if isinstance(resp, str):
                return resp
            if isinstance(resp, (bytes, bytearray)):
                return resp.decode("utf-8", errors="replace")
            if isinstance(resp, dict):
                # OpenAI-style
                try:
                    return resp.get("choices", [{}])[0].get("message", {}).get("content", "") or resp.get("text", "")
                except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                    return resp.get("text", "")
            try:
                return str(resp)
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                return ""

        def _chunk_text(text: str, size: int = 2000) -> list[str]:
            if not text:
                return []
            return [text[i : i + size] for i in range(0, len(text), size)]

        def _stream_text_as_sse(text: str) -> StreamingResponse:
            async def _stream_text():
                try:
                    created_ts = int(time.time())
                    stream_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
                    model_id = model or "local-test"

                    head = {
                        "id": stream_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": model_id,
                        "choices": [
                            {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
                        ],
                    }
                    yield f"data: {json.dumps(head)}\n\n"

                    for chunk in _chunk_text(text):
                        data = {
                            "id": stream_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": model_id,
                            "choices": [
                                {"index": 0, "delta": {"content": chunk}, "finish_reason": None}
                            ],
                        }
                        yield f"data: {json.dumps(data)}\n\n"

                    tail = {
                        "id": stream_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": model_id,
                        "choices": [
                            {"index": 0, "delta": {}, "finish_reason": "stop"}
                        ],
                    }
                    yield f"data: {json.dumps(tail)}\n\n"
                    yield "data: [DONE]\n\n"
                except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    yield "data: [DONE]\n\n"

            headers = {}
            if streams_unified:
                headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
            return StreamingResponse(_stream_text(), media_type="text/event-stream", headers=headers)

        # Initialize assistant_text to avoid potential UnboundLocalError in edge cases
        assistant_text = ""

        if offline_sim:
            # Simple deterministic response for tests/offline dev
            last_user = None
            for m in reversed(formatted):
                if m.get("role") == "user":
                    last_user = m.get("content")
                    break
            assistant_text = (last_user or "OK").strip()
            assistant_tool_calls = []
            # Streaming stub for offline-sim: emit SSE with plain text chunks and [DONE]
            if bool(body.stream):
                return _stream_text_as_sse(assistant_text or "OK")
        else:
            # For streaming, assistant text is not finalized here; skip extraction.
            assistant_tool_calls = []
            if not bool(body.stream):
                assistant_text = _extract_text(llm_resp).strip()
                # Try to extract tool calls if present (OpenAI-like shape)
                try:
                    if isinstance(llm_resp, dict):
                        tool_calls = llm_resp.get("choices", [{}])[0].get("message", {}).get("tool_calls")
                        if isinstance(tool_calls, list):
                            assistant_tool_calls = tool_calls
                except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                    pass

        # If streaming requested and we have a generator, stream SSE (real providers)
        if not offline_sim and bool(body.stream):
            try:
                # Feature flag: use unified SSEStream when enabled
                if streams_unified:
                    # Unified path expects an iterator; fall back to text streaming for non-iterables.
                    if not hasattr(llm_resp, "__aiter__") and not (
                        hasattr(llm_resp, "__iter__") and not isinstance(llm_resp, (str, bytes, dict, list))
                    ):
                        assistant_text_fallback = _extract_text(llm_resp).strip()
                        return _stream_text_as_sse(assistant_text_fallback)

                    stream = SSEStream(
                        labels={"component": "chat", "endpoint": "character_chat_stream"}
                    )
                    try:
                        logger.debug(
                            f"Unified SSE enabled: interval={stream.heartbeat_interval_s} mode={stream.heartbeat_mode}"
                        )
                    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                        pass

                    chunk_count = 0
                    total_bytes = 0

                    async def _emit_stream_limit_error(message: str) -> None:
                        payload = {"error": message}
                        await stream.send_raw_sse_line(f"data: {json.dumps(payload)}")
                        await stream.done()

                    async def _handle_chunk(chunk: Any) -> bool:
                        nonlocal chunk_count, total_bytes
                        chunk_count += 1
                        if chunk_count > MAX_STREAMING_CHUNKS:
                            logger.warning(f"Streaming chunk limit exceeded ({MAX_STREAMING_CHUNKS})")
                            await _emit_stream_limit_error("Streaming limit exceeded.")
                            return False

                        line = _coerce_sse_line(chunk)
                        if not line:
                            return True

                        total_bytes += len(line.encode("utf-8"))
                        if total_bytes > MAX_STREAMING_BYTES:
                            logger.warning(f"Streaming byte limit exceeded ({MAX_STREAMING_BYTES})")
                            await _emit_stream_limit_error("Streaming size limit exceeded.")
                            return False

                        if line.strip().lower() == "data: [done]":
                            await stream.done()
                            return False

                        await stream.send_raw_sse_line(line)
                        return True

                    async def _produce_async():
                        try:
                            if hasattr(llm_resp, "__aiter__"):
                                async for chunk in llm_resp:  # type: ignore
                                    keep_going = await _handle_chunk(chunk)
                                    if not keep_going:
                                        return
                            elif hasattr(llm_resp, "__iter__") and not isinstance(llm_resp, (str, bytes, dict, list)):
                                for chunk in llm_resp:  # type: ignore
                                    keep_going = await _handle_chunk(chunk)
                                    if not keep_going:
                                        return
                            # Ensure DONE if provider didn't send one
                            await stream.done()
                        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
                            await stream.error("internal_error", f"{e}")

                    async def _generator():
                        producer = asyncio.create_task(_produce_async())
                        try:
                            async for line in stream.iter_sse():
                                yield line
                        except asyncio.CancelledError:
                            # Preserve cancellation semantics; cleanup happens in finally
                            raise
                        else:
                            # Ensure producer completes if stream ended without explicit DONE
                            if not producer.done():
                                try:
                                    await producer
                                except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                                    pass
                            # If DONE wasn’t enqueued for any reason, append one now
                            try:
                                if not getattr(stream, "_done_enqueued", False):
                                    yield sse_done()
                            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                                pass
                        finally:
                            # Always tear down the background producer to avoid leaks
                            if not producer.done():
                                try:
                                    producer.cancel()
                                except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                                    pass
                                try:
                                    await producer
                                except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                                    # Swallow any errors from producer teardown
                                    pass

                    headers = {
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    }
                    return StreamingResponse(_generator(), media_type="text/event-stream", headers=headers)
                # Legacy path (flag off): stream directly (provider iterator yields SSE lines)
                # Support async generators
                if hasattr(llm_resp, "__aiter__"):
                    async def _sse_async():
                        done_sent = False
                        chunk_count = 0
                        total_bytes = 0
                        try:
                            async for chunk in llm_resp:  # type: ignore
                                # Safety limits to prevent DoS
                                chunk_count += 1
                                if chunk_count > MAX_STREAMING_CHUNKS:
                                    logger.warning(f"Streaming chunk limit exceeded ({MAX_STREAMING_CHUNKS})")
                                    yield f"data: {json.dumps({'error': 'Streaming limit exceeded.'})}\n\n"
                                    break

                                line = _coerce_sse_line(chunk)
                                if not line:
                                    continue

                                total_bytes += len(line.encode('utf-8'))
                                if total_bytes > MAX_STREAMING_BYTES:
                                    logger.warning(f"Streaming byte limit exceeded ({MAX_STREAMING_BYTES})")
                                    yield f"data: {json.dumps({'error': 'Streaming size limit exceeded.'})}\n\n"
                                    break

                                normalized = line.strip().lower()
                                if normalized == "data: [done]":
                                    done_sent = True
                                yield ensure_sse_line(line)
                        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
                            if isinstance(e, AttributeError) and "object has no attribute 'close'" in str(e):
                                logger.debug("Ignoring streaming session close error: %s", e)
                            else:
                                logger.exception("Exception occurred in streaming SSE async generator.")
                                yield f"data: {json.dumps({'error': 'An internal error has occurred.'})}\n\n"
                        finally:
                            if not done_sent:
                                yield "data: [DONE]\n\n"
                    # Note: streaming mode does not persist assistant content
                    return StreamingResponse(_sse_async(), media_type="text/event-stream")
                # Support sync generators/iterables that are not plain containers
                if hasattr(llm_resp, "__iter__") and not isinstance(llm_resp, (str, bytes, dict, list)):
                    async def _sse_gen():
                        done_sent = False
                        chunk_count = 0
                        total_bytes = 0
                        try:
                            for chunk in llm_resp:  # type: ignore
                                # Safety limits to prevent DoS
                                chunk_count += 1
                                if chunk_count > MAX_STREAMING_CHUNKS:
                                    logger.warning(f"Streaming chunk limit exceeded ({MAX_STREAMING_CHUNKS})")
                                    yield f"data: {json.dumps({'error': 'Streaming limit exceeded.'})}\n\n"
                                    break

                                line = _coerce_sse_line(chunk)
                                if not line:
                                    continue

                                total_bytes += len(line.encode('utf-8'))
                                if total_bytes > MAX_STREAMING_BYTES:
                                    logger.warning(f"Streaming byte limit exceeded ({MAX_STREAMING_BYTES})")
                                    yield f"data: {json.dumps({'error': 'Streaming size limit exceeded.'})}\n\n"
                                    break

                                normalized = line.strip().lower()
                                if normalized == "data: [done]":
                                    done_sent = True
                                yield ensure_sse_line(line)
                        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                            logger.exception("Exception occurred in streaming SSE generator.")
                            yield f"data: {json.dumps({'error': 'An internal error has occurred.'})}\n\n"
                        finally:
                            if not done_sent:
                                yield "data: [DONE]\n\n"
                    # Note: streaming mode does not persist assistant content
                    return StreamingResponse(_sse_gen(), media_type="text/event-stream")
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                # Fall through to non-streaming response
                pass
            if isinstance(llm_resp, (dict, str, bytes, bytearray)):
                assistant_text_fallback = _extract_text(llm_resp).strip()
                return _stream_text_as_sse(assistant_text_fallback)
        if not assistant_text:
            assistant_text = ""

        saved = False
        assistant_msg_id: Optional[str] = None
        if will_persist:
            # Persist appended user message first, if any
            if body.append_user_message:
                appended_user_id = post_message_to_conversation(
                    db=db,
                    conversation_id=chat_id,
                    character_name=char_label,
                    message_content=body.append_user_message,
                    is_user_message=True,
                    sender_override="user",
                )
                if not appended_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to persist appended user message"
                    )

            # Persist assistant response (tool_calls stored in metadata only)
            assistant_content_for_storage = assistant_text if assistant_text else " "
            assistant_msg_id = post_message_to_conversation(
                db=db,
                conversation_id=chat_id,
                character_name=char_label,
                message_content=assistant_content_for_storage,
                is_user_message=False,
                parent_message_id=appended_user_id,
            )
            if not assistant_msg_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to persist assistant message"
                )
            metadata_extra = {
                "speaker_character_id": active_character_id,
                "speaker_character_name": char_label,
                "turn_taking_mode": turn_context.get("turn_taking_mode", "single"),
            }
            validated_tool_calls = (
                _validate_and_truncate_tool_calls(assistant_tool_calls)
                if assistant_tool_calls
                else None
            )
            try:
                db.add_message_metadata(
                    assistant_msg_id,
                    tool_calls=validated_tool_calls,
                    extra=metadata_extra,
                )
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"Non-fatal: failed to persist assistant metadata: {exc}")
            saved = True

        return CharacterChatCompletionV2Response(
            chat_id=chat_id,
            character_id=active_character_id or conversation['character_id'],
            provider=provider,
            model=model,
            saved=saved,
            user_message_id=appended_user_id,
            assistant_message_id=assistant_msg_id,
            assistant_content=assistant_text,
            speaker_character_id=active_character_id,
            speaker_character_name=char_label,
        )

    except HTTPException:
        raise
    except InputError as e:
        msg = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        if "exceeds maximum" in msg.lower():
            status_code = status.HTTP_413_CONTENT_TOO_LARGE
        logger.warning(f"Input error in character chat completion for {chat_id}: {e}")
        raise HTTPException(status_code=status_code, detail=msg) from e
    except ConflictError as e:
        logger.warning(f"Conflict in character chat completion for {chat_id}: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"DB error in character chat completion for {chat_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error in character chat completion for {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during character chat completion")


@router.get("/", response_model=ChatSessionListResponse,
            summary="List user's chat sessions", tags=["Chat Sessions"])
async def list_chat_sessions(
    character_id: Optional[int] = Query(None, description="Filter by character ID"),
    limit: int = Query(50, ge=1, le=200, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    include_settings: bool = Query(
        False,
        description="Include per-chat settings payload for each returned chat.",
    ),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    List all chat sessions for the current user.

    Args:
        character_id: Optional character ID filter
        limit: Maximum number of items to return
        offset: Number of items to skip
        db: Database instance
        current_user: Authenticated user

    Returns:
        List of chat sessions with pagination info
    """
    try:
        user_id_str = str(current_user.id)
        if character_id:
            # Get conversations for specific character scoped to current user
            conversations = db.get_conversations_for_user_and_character(user_id_str, character_id, limit=limit, offset=offset)
            try:
                total_count = db.count_conversations_for_user_by_character(user_id_str, character_id)
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                # Fallback: filter by client_id in-memory if efficient count isn't available
                total_count = len([c for c in conversations if c.get('client_id') == user_id_str])
        else:
            # Efficient path: list conversations for this user directly
            conversations = db.get_conversations_for_user(user_id_str, limit=limit, offset=offset)
            try:
                total_count = db.count_conversations_for_user(user_id_str)
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                total_count = len(conversations)

        # Filter by client_id for security (redundant in happy path, kept defensively)
        user_conversations = [conv for conv in conversations if conv.get('client_id') == user_id_str]

        # Sort by last_modified descending
        user_conversations.sort(key=lambda x: x.get('last_modified', ''), reverse=True)

        # Note: pagination was already applied at DB level, no need to slice again

        # Add message counts using efficient counter
        for conv in user_conversations:
            try:
                conv['message_count'] = db.count_messages_for_conversation(conv['id'])
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                messages = db.get_messages_for_conversation(conv['id'], limit=1000)
                conv['message_count'] = len(messages) if messages else 0

        chats: list[ChatSessionResponse] = []
        for conv in user_conversations:
            settings_payload: Optional[dict[str, Any]] = None
            if include_settings:
                settings_row = db.get_conversation_settings(conv['id'])
                settings_payload = (settings_row or {}).get("settings") or {}
            chats.append(
                _convert_db_conversation_to_response(
                    conv,
                    settings=settings_payload,
                )
            )

        return ChatSessionListResponse(
            chats=chats,
            total=total_count,
            limit=limit,
            offset=offset
        )

    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error listing chat sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing chat sessions"
        )


@router.put("/{chat_id}", response_model=ChatSessionResponse,
            summary="Update chat session", tags=["Chat Sessions"])
async def update_chat_session(
    update_data: ChatSessionUpdate,
    chat_id: str = Path(..., description="Chat session ID"),
    expected_version: int = Query(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    Update a chat session's metadata.

    Args:
        chat_id: Chat session ID
        update_data: Update data
        expected_version: Expected version for optimistic locking
        db: Database instance
        current_user: Authenticated user

    Returns:
        Updated chat session details

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized, 409 if version conflict
    """
    try:
        # Get current conversation
        conversation = db.get_conversation_by_id(chat_id)
        _verify_chat_ownership(conversation, current_user.id, chat_id)

        # Check version
        if conversation.get('version', 1) != expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version mismatch. Expected {expected_version}, found {conversation.get('version', 1)}"
            )

        # Update fields via DB abstraction with optimistic locking
        update_fields = update_data.model_dump(exclude_unset=True)
        # Only allow supported fields
        allowed_update = {
            k: v
            for k, v in update_fields.items()
            if k in {"title", "rating", "state", "topic_label", "cluster_id", "source", "external_ref"}
        }
        # db.update_conversation updates metadata and bumps version even if payload is empty
        db.update_conversation(chat_id, allowed_update, expected_version)

        # Retrieve updated conversation
        updated_conv = db.get_conversation_by_id(chat_id)
        if updated_conv:
            messages = db.get_messages_for_conversation(chat_id, limit=1000)
            updated_conv['message_count'] = len(messages) if messages else 0

        return _convert_db_conversation_to_response(updated_conv)

    except ConflictError as e:
        # Optimistic locking or state conflicts
        logger.warning(f"Conflict updating chat session {chat_id}: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except CharactersRAGDBError as e:
        logger.error(f"DB error updating chat session {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except HTTPException:
        raise
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error updating chat session {chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating chat session"
        )


@router.get(
    "/{chat_id}/settings",
    response_model=ChatSettingsResponse,
    summary="Get chat settings",
    tags=["Chat Sessions"],
)
async def get_chat_settings(
    chat_id: str = Path(..., description="Chat session ID"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    try:
        conversation = db.get_conversation_by_id(chat_id)
        _verify_chat_ownership(conversation, current_user.id, chat_id)

        settings_row = db.get_conversation_settings(chat_id)
        if not settings_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat settings not found")

        return ChatSettingsResponse(
            conversation_id=chat_id,
            settings=settings_row.get("settings") or {},
            last_modified=settings_row.get("last_modified") or datetime.now(timezone.utc),
        )
    except HTTPException:
        raise
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Error fetching chat settings for {chat_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch chat settings") from exc


@router.put(
    "/{chat_id}/settings",
    response_model=ChatSettingsResponse,
    summary="Update chat settings",
    tags=["Chat Sessions"],
)
async def update_chat_settings(
    payload: ChatSettingsUpdate,
    chat_id: str = Path(..., description="Chat session ID"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    try:
        conversation = db.get_conversation_by_id(chat_id)
        _verify_chat_ownership(conversation, current_user.id, chat_id)

        incoming_settings = payload.settings or {}
        _validate_chat_settings_payload(incoming_settings)

        existing_row = db.get_conversation_settings(chat_id)
        existing_settings = (existing_row or {}).get("settings") or {}
        merged_settings = _merge_conversation_settings(existing_settings, incoming_settings)
        _validate_chat_settings_payload(merged_settings)

        if not db.upsert_conversation_settings(chat_id, merged_settings):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update chat settings")

        _touch_conversation_metadata(db, chat_id)
        settings_row = db.get_conversation_settings(chat_id)

        return ChatSettingsResponse(
            conversation_id=chat_id,
            settings=(settings_row or {}).get("settings") or merged_settings,
            last_modified=(settings_row or {}).get("last_modified") or datetime.now(timezone.utc),
        )
    except HTTPException:
        raise
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Error updating chat settings for {chat_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update chat settings") from exc


@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete chat session",
    tags=["Chat Sessions"],
)
async def delete_chat_session(
    chat_id: str = Path(..., description="Chat session ID"),
    expected_version: Optional[int] = Query(None, description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
) -> Response:
    """
    Soft delete a chat session.

    Args:
        chat_id: Chat session ID
        expected_version: Expected version for optimistic locking
        db: Database instance
        current_user: Authenticated user

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized, 409 if version conflict
    """
    try:
        # Get current conversation
        conversation = db.get_conversation_by_id(chat_id)
        _verify_chat_ownership(conversation, current_user.id, chat_id)

        # Check version if provided
        if expected_version is not None and conversation.get('version', 1) != expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version mismatch. Expected {expected_version}, found {conversation.get('version', 1)}"
            )

        # Delete messages in batches using offset-based pagination to avoid unbounded memory
        # Track failed message IDs to prevent infinite loops when deletions fail
        batch_size = 100
        max_batches = 1000  # Safety limit: max 100,000 messages per conversation
        total_deleted = 0
        consecutive_empty_batches = 0
        max_empty_batches = 3  # Stop after consecutive empty batches (indicates completion)
        failed_message_ids: set = set()  # Track messages that failed to delete

        for _batch_num in range(max_batches):
            # Fetch non-deleted messages only (include_deleted=False is default)
            batch = db.get_messages_for_conversation(chat_id, limit=batch_size, offset=0)

            # Filter out messages that previously failed to delete to prevent infinite loops
            batch = [m for m in batch if m.get("id") not in failed_message_ids]

            if not batch:
                consecutive_empty_batches += 1
                if consecutive_empty_batches >= max_empty_batches:
                    break
                continue

            consecutive_empty_batches = 0  # Reset counter on successful batch

            # Delete messages in this batch
            batch_deleted = 0
            for msg in batch:
                msg_id = msg.get("id")
                if not msg_id:
                    continue
                try:
                    db.soft_delete_message(msg_id, msg.get("version", 1))
                    batch_deleted += 1
                except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                    logger.warning("Failed to soft-delete message {} during conversation delete.", msg_id)
                    failed_message_ids.add(msg_id)  # Track failed deletions

            total_deleted += batch_deleted

            # If we couldn't delete any messages in this batch, we might be stuck
            if batch_deleted == 0:
                consecutive_empty_batches += 1
                if consecutive_empty_batches >= max_empty_batches:
                    logger.warning(f"Stopping message deletion for {chat_id} after {total_deleted} messages - possible stuck state")
                    break

        if failed_message_ids:
            logger.warning(f"Failed to delete {len(failed_message_ids)} messages from conversation {chat_id}: {failed_message_ids}")

        logger.debug(f"Deleted {total_deleted} messages from conversation {chat_id}")

        # Soft delete conversation via DB abstraction (optimistic locking)
        exp_ver = expected_version if expected_version is not None else conversation.get('version', 1)
        # Finally soft delete the conversation
        db.soft_delete_conversation(chat_id, exp_ver)

        logger.info(f"Soft deleted chat session {chat_id} by user {current_user.id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except ConflictError as e:
        logger.warning(f"Conflict deleting chat session {chat_id}: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except CharactersRAGDBError as e:
        logger.error(f"DB error deleting chat session {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except HTTPException:
        raise
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error deleting chat session {chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting chat session"
        )


# ========================================================================
# Note: Character chat completions should use the main /api/v1/chat/completions endpoint
# To get messages formatted for completions, use:
# GET /api/v1/chats/{chat_id}/messages?format_for_completions=true&include_character_context=true
# ========================================================================


# ========================================================================
# Chat Export Endpoint
# ========================================================================

# Maximum messages per export page to prevent DoS
MAX_EXPORT_PAGE_SIZE = 5000
DEFAULT_EXPORT_PAGE_SIZE = 1000


@router.get("/{chat_id}/export",
            summary="Export chat history", tags=["Chat Export"])
async def export_chat_history(
    chat_id: str = Path(..., description="Chat session ID"),
    format: str = Query("json", description="Export format (json, markdown, text)"),
    include_metadata: bool = Query(True, description="Include chat metadata"),
    include_character: bool = Query(True, description="Include character info"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_EXPORT_PAGE_SIZE, ge=1, le=MAX_EXPORT_PAGE_SIZE,
                          description=f"Messages per page (max {MAX_EXPORT_PAGE_SIZE})"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    Export chat history in various formats with pagination support.

    Args:
        chat_id: Chat session ID to export
        format: Export format (json, markdown, text)
        include_metadata: Whether to include metadata
        include_character: Whether to include character info
        page: Page number (1-indexed, default 1)
        page_size: Number of messages per page (default 1000, max 5000)
        db: Database instance
        current_user: Authenticated user

    Returns:
        Chat history in requested format with pagination info

    Raises:
        HTTPException: 404 if chat not found, 403 if unauthorized
    """
    try:
        # Get conversation
        conversation = db.get_conversation_by_id(chat_id)
        _verify_chat_ownership(conversation, current_user.id, chat_id)

        settings_row = db.get_conversation_settings(chat_id)
        history_messages = db.get_messages_for_conversation(chat_id, limit=1000, offset=0) or []
        history_messages = [m for m in history_messages if not m.get("deleted")]
        turn_context = _resolve_chat_turn_context(
            db=db,
            conversation=conversation,
            settings_row=settings_row,
            history_messages=history_messages,
        )
        participant_aliases = turn_context.get("participant_aliases") or set()
        primary_character_name = turn_context.get("primary_character_name")

        # Get character info if requested
        character = None
        if include_character:
            character = db.get_character_card_by_id(conversation['character_id'])

        # Get total message count for pagination info
        try:
            total_messages = db.count_messages_for_conversation(chat_id)
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
            # Fallback if count method not available
            total_messages = None

        # Calculate offset for pagination
        offset = (page - 1) * page_size

        # Get messages with pagination
        messages = db.get_messages_for_conversation(chat_id, limit=page_size, offset=offset)

        # Calculate pagination metadata
        total_pages = None
        has_more = False
        if total_messages is not None:
            total_pages = (total_messages + page_size - 1) // page_size
            has_more = page < total_pages

        # Format based on requested type
        if format == "markdown":
            # Markdown format
            lines = []
            if include_metadata:
                lines.append(f"# Chat Export: {conversation.get('title', 'Untitled')}")
                if character:
                    lines.append(f"**Character**: {character.get('name', 'Unknown')}")
                lines.append(f"**Date**: {conversation.get('created_at', '')}")
                if total_messages is not None:
                    lines.append(f"**Messages**: {len(messages)} of {total_messages} (page {page})")
                else:
                    lines.append(f"**Messages**: {len(messages)}")
                lines.append("\n---\n")

            for msg in messages:
                if msg.get('deleted'):
                    continue
                sender = msg.get('sender', 'unknown')
                content = msg.get('content') or ''
                timestamp = msg.get('timestamp', '')
                lines.append(f"**{sender.title()}** ({timestamp}):")
                lines.append(f"{content}\n")

            return {"content": "\n".join(lines), "format": "markdown"}

        elif format == "text":
            # Plain text format
            lines = []
            if include_metadata:
                lines.append(f"Chat: {conversation.get('title', 'Untitled')}")
                if character:
                    lines.append(f"Character: {character.get('name', 'Unknown')}")
                lines.append(f"Date: {conversation.get('created_at', '')}")
                lines.append("-" * 40)

            for msg in messages:
                if msg.get('deleted'):
                    continue
                sender = msg.get('sender', 'unknown')
                content = msg.get('content') or ''
                lines.append(f"{sender}: {content}")

            return {"content": "\n".join(lines), "format": "text"}

        else:
            # JSON format (default)
            export_data = {
                "chat_id": chat_id,
                "character_name": character.get('name', 'Unknown') if character else 'Unknown',
                "character_id": conversation['character_id'],
                "title": conversation.get('title'),
                "created_at": str(conversation.get('created_at', '')),
                "messages": []
            }
            message_metadata_extra: dict[str, Any] = {}
            # Build messages with optional tool_calls per message
            for msg in messages:
                if msg.get('deleted'):
                    continue
                item = {
                    "id": msg.get('id'),
                    "role": msg.get('sender'),
                    "content": msg.get('content') or '',
                    "timestamp": str(msg.get('timestamp', '')),
                    "has_image": bool(msg.get('image_data'))
                }
                try:
                    md = db.get_message_metadata(msg.get('id'))
                except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                    md = None
                role_for_tool_calls = _map_sender_to_role_with_participants(
                    msg.get('sender'),
                    primary_character_name,
                    participant_aliases,
                )
                if md and md.get('tool_calls') is not None:
                    item["tool_calls"] = md.get('tool_calls')
                elif role_for_tool_calls == 'assistant':
                    # Fallback: parse inline suffix [tool_calls]: <json>
                    try:
                        import json as _json
                        import re as _re
                        m = _re.search(r"\[tool_calls\]\s*:\s*(\{.*|\[.*)$", (msg.get('content') or ''), _re.DOTALL)
                        if m:
                            parsed = _json.loads(m.group(1).strip())
                            if isinstance(parsed, dict) and 'tool_calls' in parsed:
                                tc_list = parsed.get('tool_calls')
                            else:
                                tc_list = parsed
                            if isinstance(tc_list, list):
                                item["tool_calls"] = tc_list
                    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
                        pass
                export_data["messages"].append(item)
                if include_metadata and md and md.get('extra') is not None and msg.get('id'):
                    message_metadata_extra[msg.get('id')] = md.get('extra')

            if include_metadata:
                export_data["metadata"] = {
                    "total_messages": total_messages if total_messages is not None else len(messages),
                    "rating": conversation.get('rating'),
                    "last_modified": str(conversation.get('last_modified', ''))
                }
                if message_metadata_extra:
                    export_data["message_metadata_extra"] = message_metadata_extra

            # Add pagination info to JSON export
            export_data["pagination"] = {
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_messages": total_messages,
                "has_more": has_more,
                "messages_in_page": len(messages)
            }

            return export_data

    except HTTPException:
        raise
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error exporting chat {chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while exporting chat history"
        )


# ========================================================================
# Persist streamed assistant content
# ========================================================================

@router.post(
    "/{chat_id}/completions/persist",
    response_model=CharacterChatStreamPersistResponse,
    summary="Persist streamed assistant content",
    description=(
        "Persist an assistant message after a streamed completion. "
        "Optionally links to a prior user_message_id and stores tool_calls metadata."
    ),
    tags=["Chat Sessions"],
)
async def persist_streamed_assistant_message(
    chat_id: str = Path(..., description="Chat session ID"),
    body: CharacterChatStreamPersistRequest = None,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    try:
        body = body or CharacterChatStreamPersistRequest(assistant_content="")

        conversation = db.get_conversation_by_id(chat_id)
        _verify_chat_ownership(conversation, current_user.id, chat_id)

        # Enforce message cap (+1 assistant)
        try:
            current_count = db.count_messages_for_conversation(chat_id)
            limiter = get_character_rate_limiter()
            await limiter.check_message_limit(chat_id, current_count + 1)
        except HTTPException:
            raise
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS:
            logger.debug("Non-fatal: message cap check skipped in persist endpoint")

        # Validate optional parent message belongs to this conversation
        if getattr(body, "user_message_id", None):
            parent_msg = db.get_message_by_id(body.user_message_id)
            if not parent_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent message not found"
                )
            if parent_msg.get("conversation_id") != chat_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent message must belong to the same conversation"
                )

        # Persist assistant response via Character_Chat guardrails
        char_card = db.get_character_card_by_id(conversation.get('character_id')) or {}
        raw_name = (char_card.get('name') or 'Assistant') if isinstance(char_card, dict) else 'Assistant'
        assistant_msg_id = post_message_to_conversation(
            db=db,
            conversation_id=chat_id,
            character_name=raw_name,
            message_content=body.assistant_content,
            is_user_message=False,
            parent_message_id=body.user_message_id,
            ranking=body.ranking if getattr(body, "ranking", None) is not None else None,
        )
        if not assistant_msg_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist assistant message"
            )
        # Persist metadata: tool_calls and usage
        try:
            extra = None
            if getattr(body, 'usage', None) is not None:
                extra = {"usage": body.usage}
            validated_tool_calls = _validate_and_truncate_tool_calls(getattr(body, 'tool_calls', None))
            if validated_tool_calls is not None or extra is not None:
                db.add_message_metadata(assistant_msg_id, tool_calls=validated_tool_calls, extra=extra)
        except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(
                f"Non-fatal: failed to persist metadata for message {assistant_msg_id}: {exc}"
            )

        # Optionally update chat rating
        if getattr(body, 'chat_rating', None) is not None:
            try:
                conv_for_update = db.get_conversation_by_id(chat_id)
                if conv_for_update:
                    db.update_conversation(
                        chat_id,
                        {"rating": body.chat_rating},
                        conv_for_update.get('version', 1),
                    )
            except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
                logger.warning(
                    "Failed to update chat rating for chat_id={} rating={} error={}",
                    chat_id,
                    getattr(body, "chat_rating", None),
                    e,
                    exc_info=True,
                )

        return CharacterChatStreamPersistResponse(chat_id=chat_id, assistant_message_id=assistant_msg_id, saved=True)
    except HTTPException:
        raise
    except InputError as e:
        msg = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        if "exceeds maximum" in msg.lower():
            status_code = status.HTTP_413_CONTENT_TOO_LARGE
        logger.warning(f"Input error persisting streamed assistant message for {chat_id}: {e}")
        raise HTTPException(status_code=status_code, detail=msg) from e
    except ConflictError as e:
        logger.warning(f"Conflict persisting streamed assistant message for {chat_id}: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"DB error persisting streamed assistant message for {chat_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
    except _CHAR_CHAT_SESSIONS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error persisting streamed assistant message for {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist assistant message")


#
# End of character_chat_sessions.py
######################################################################################################################
