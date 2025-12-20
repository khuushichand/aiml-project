# character_chat_sessions.py
"""
API endpoints for character chat session management.
Provides CRUD operations for chat sessions and character-specific completions.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Literal
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    status,
    Body,
    Response,

)
from fastapi.responses import StreamingResponse
from loguru import logger
from collections import defaultdict, deque
import time
import os
import asyncio
import random

# Database and authentication dependencies
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError
)

# Schemas
from tldw_Server_API.app.api.v1.schemas.chat_session_schemas import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatSessionListResponse,
    MessageResponse,

    CharacterChatCompletionPrepRequest,
    CharacterChatCompletionPrepResponse,
    CharacterChatCompletionV2Request,
    CharacterChatCompletionV2Response,
    CharacterChatStreamPersistRequest,
    CharacterChatStreamPersistResponse,
)

# Character chat helpers
from tldw_Server_API.app.core.Character_Chat.Character_Chat_Lib_facade import (
    start_new_chat_session,
    post_message_to_conversation,
    retrieve_conversation_messages_for_ui,
    load_chat_and_character,
    map_sender_to_role,
    replace_placeholders,
)
from tldw_Server_API.app.core.Character_Chat.modules.character_utils import (
    sanitize_sender_name,
)

# Chat helpers and utilities
from tldw_Server_API.app.core.Chat.chat_helpers import (
    get_or_create_conversation,
    load_conversation_history
)

# Rate limiting
from tldw_Server_API.app.core.Character_Chat.character_rate_limiter import (
    get_character_rate_limiter,
)

# For chat completions
from tldw_Server_API.app.core.Chat.chat_orchestrator import (
    chat_api_call as perform_chat_api_call
)
from tldw_Server_API.app.core.AuthNZ.byok_runtime import resolve_byok_credentials

# Completion schemas centralized in schemas/chat_session_schemas.py
from tldw_Server_API.app.core.Streaming.streams import SSEStream
from tldw_Server_API.app.core.LLM_Calls.sse import ensure_sse_line, normalize_provider_line, sse_done
from tldw_Server_API.app.core.Utils.common import parse_boolean

# Import shared constants
from tldw_Server_API.app.core.Character_Chat.constants import (
    MAX_STREAMING_CHUNKS,
    MAX_STREAMING_BYTES,
    MAX_TOOL_CALLS_SIZE,
    MAX_TOOL_CALLS_COUNT,
    THROTTLE_CACHE_MAX_KEYS,
    THROTTLE_STALE_SECONDS,
)

THROTTLE_WINDOW_SIZE = 100

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
            while tool_calls and len(json.dumps(tool_calls)) > MAX_TOOL_CALLS_SIZE:
                tool_calls = tool_calls[:-1]
            if not tool_calls:
                return None
    except (TypeError, ValueError) as e:
        logger.warning(f"tool_calls not JSON serializable: {e}")
        return None

    return tool_calls

# Legacy local SSE helpers removed — unified streams handle normalization


def _verify_chat_ownership(
    conversation: Optional[Dict[str, Any]],
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
        self._data: Dict[str, deque] = {}
        self._last_access: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> deque:
        """Concurrency-safe access to throttle window for a given key."""
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

# ========================================================================
# Helper Functions
# ========================================================================

def _convert_db_conversation_to_response(conv_data: Dict[str, Any]) -> ChatSessionResponse:
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
        version=conv_data.get('version', 1)
    )

def _convert_db_message_to_response(msg_data: Dict[str, Any]) -> MessageResponse:
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

"""Role mapping provided by Character_Chat utility: map_sender_to_role"""

# ========================================================================
# Chat Session Endpoints
# ========================================================================

@router.post("/", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED,
             summary="Create a new chat session", tags=["Chat Sessions"])
async def create_chat_session(
    session_data: ChatSessionCreate,
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
        except Exception as e:
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

        # Generate chat ID and title
        chat_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        title = session_data.title or f"{character['name']} Chat ({timestamp})"

        # Create conversation data
        conv_data = {
            'id': chat_id,
            'character_id': session_data.character_id,
            'title': title,
            'root_id': chat_id,  # Root for new conversations
            'parent_conversation_id': session_data.parent_conversation_id,
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
        if seed_first_message:
            try:
                raw_name = character.get('name') or 'Assistant'
                char_name = sanitize_sender_name(raw_name)
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
                    content = replace_placeholders(choice_text, char_name, 'User')
                    db.add_message({
                        'conversation_id': created_id,
                        'sender': char_name,
                        'content': content,
                        'client_id': str(current_user.id),
                        'version': 1
                    })
                    # Bump conversation metadata (best-effort)
                    try:
                        refreshed = db.get_conversation_by_id(created_id) or {}
                        db.update_conversation(created_id, {}, refreshed.get('version', 1))
                        created_conv['message_count'] = (created_conv.get('message_count') or 0) + 1
                    except Exception:
                        pass
            except Exception as _seed_err:
                logger.debug(f"Non-fatal: failed to seed first message for chat {created_id}: {_seed_err}")

        # Log creation
        logger.info(f"Created chat session {created_id} for character {session_data.character_id} by user {current_user.id}")

        return _convert_db_conversation_to_response(created_conv)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating chat session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating chat session"
        )


@router.get("/{chat_id}", response_model=ChatSessionResponse,
            summary="Get chat session details", tags=["Chat Sessions"])
async def get_chat_session(
    chat_id: str = Path(..., description="Chat session ID"),
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
        except Exception:
            messages = db.get_messages_for_conversation(chat_id, limit=1000)
            conversation['message_count'] = len(messages) if messages else 0

        return _convert_db_conversation_to_response(conversation)

    except HTTPException:
        raise
    except Exception as e:
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

        character = db.get_character_card_by_id(conversation['character_id']) or {}
        char_name = character.get('name', 'Unknown')

        messages = db.get_messages_for_conversation(chat_id, limit=1000) or []
        # Map DB messages to chat-completions messages with normalized roles
        formatted = []
        for m in messages:
            if m.get('deleted'):
                continue
            role = map_sender_to_role(m.get('sender'), character.get('name'))
            content = m.get('content') or ''
            formatted.append({"role": role, "content": content})

        # If no messages, include first_message as an initial assistant message (with placeholders resolved)
        if not formatted and character.get('first_message'):
            try:
                fm = replace_placeholders(character['first_message'], char_name, 'User')
            except Exception:
                fm = character['first_message']
            formatted.append({"role": "assistant", "content": fm})

        return {"character_name": char_name, "messages": formatted}

    except HTTPException:
        raise
    except Exception as e:
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
    body: Optional[Dict[str, Any]] = Body(
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
            from datetime import datetime, timedelta, timezone as _tz
            sunset_days = int(os.getenv("DEPRECATION_SUNSET_DAYS", "90"))
            sunset = (datetime.now(_tz.utc) + timedelta(days=sunset_days)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        except Exception:
            sunset = "Tue, 31 Dec 2025 00:00:00 GMT"
        dep_headers = {
            "Deprecation": "true",
            "Sunset": sunset,
            "Link": "</api/v1/chats/{chat_id}/complete-v2>; rel=successor-version",
        }
        try:
            if response is not None:
                for k, v in dep_headers.items():
                    response.headers[k] = v
        except Exception:
            pass

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
        now = time.time()
        window = await _complete_windows.get(key)
        # Evict entries older than 1 second
        while window and (now - window[0]) > 1.0:
            window.popleft()
        # Enforce limit
        if len(window) >= 5:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded for chat completion")
        window.append(now)

        # Return a minimal success payload
        return {"status": "ok", "chat_id": chat_id}

    except HTTPException:
        raise
    except Exception as e:
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
        character = db.get_character_card_by_id(conversation['character_id']) or {}
        character_name = character.get('name')
        include_ctx = bool(body.include_character_context)
        # Fields are validated by Pydantic; avoid redundant int() casting
        limit = body.limit
        offset = body.offset

        messages = db.get_messages_for_conversation(chat_id, limit=limit, offset=offset) or []
        # Filter deleted
        messages = [m for m in messages if not m.get('deleted')]
        paginated = messages

        formatted: List[Dict[str, Any]] = []
        if include_ctx and character:
            parts = [
                f"You are {character.get('name', 'Assistant')}.",
                character.get('description', ''),
                character.get('personality', ''),
                character.get('scenario', ''),
                character.get('system_prompt', ''),
            ]
            sys_text = '\n'.join([p for p in parts if p])
            if sys_text.strip():
                formatted.append({"role": "system", "content": sys_text.strip()})

        for msg in paginated:
            formatted.append({
                "role": map_sender_to_role(msg.get('sender'), character.get('name')),
                "content": msg.get('content') or ''
            })

        if body.append_user_message:
            formatted.append({"role": "user", "content": body.append_user_message})

        return CharacterChatCompletionPrepResponse(
            chat_id=chat_id,
            character_id=conversation['character_id'],
            character_name=character_name,
            messages=formatted,
            total=len(messages)
        )

    except HTTPException:
        raise
    except Exception as e:
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
        character = db.get_character_card_by_id(conversation['character_id']) or {}
        include_ctx = bool(body.include_character_context)
        limit = body.limit
        offset = body.offset

        messages = db.get_messages_for_conversation(chat_id, limit=limit, offset=offset) or []
        messages = [m for m in messages if not m.get('deleted')]
        paginated = messages

        formatted: List[Dict[str, Any]] = []
        if include_ctx and character:
            parts = [
                f"You are {character.get('name', 'Assistant')}.",
                character.get('description', ''),
                character.get('personality', ''),
                character.get('scenario', ''),
                character.get('system_prompt', ''),
            ]
            sys_text = '\n'.join([p for p in parts if p])
            if sys_text.strip():
                formatted.append({"role": "system", "content": sys_text.strip()})

        for msg in paginated:
            formatted.append({
                "role": map_sender_to_role(msg.get('sender'), character.get('name')),
                "content": msg.get('content') or ''
            })

        # Optional appended user message
        appended_user_id: Optional[str] = None
        if body.append_user_message:
            formatted.append({"role": "user", "content": body.append_user_message})

        # Determine provider/model with safe defaults for test/offline
        provider = (body.provider or os.getenv("CHAR_CHAT_PROVIDER") or "local-llm").strip()
        model = (body.model or os.getenv("CHAR_CHAT_MODEL") or "local-test").strip()

        # If we will persist, ensure message cap won't be exceeded
        will_add = 1 if body.append_user_message else 0
        will_add += 1  # assistant reply
        try:
            # Use efficient counter to avoid loading large message lists into memory
            current_count = db.count_messages_for_conversation(chat_id)
            await rate_limiter.check_message_limit(chat_id, current_count + will_add)
        except HTTPException:
            raise
        except Exception:
            logger.debug("Non-fatal: message cap pre-check skipped")

        # Resolve BYOK credentials (fall back to env/config)
        def _fallback_resolver(name: str) -> Optional[str]:
            try:
                from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import get_api_keys
                return get_api_keys().get(name)
            except Exception:
                return None

        user_id_int = getattr(current_user, "id_int", None)
        if user_id_int is None:
            try:
                user_id_int = int(getattr(current_user, "id", None))
            except Exception:
                user_id_int = None

        byok_resolution = await resolve_byok_credentials(
            provider,
            user_id=user_id_int,
            fallback_resolver=_fallback_resolver,
        )
        api_key = byok_resolution.api_key

        # Attempt provider call; allow offline simulation for local-llm in test/dev.
        # Offline simulation toggle (supports new flags for clarity, backward compatible with ALLOW_LOCAL_LLM_CALLS)
        enable_local_llm = parse_boolean(os.getenv("ENABLE_LOCAL_LLM_PROVIDER"))
        disable_offline_sim = parse_boolean(os.getenv("DISABLE_OFFLINE_SIM"))
        legacy_allow_local = parse_boolean(os.getenv("ALLOW_LOCAL_LLM_CALLS"))
        offline_sim = provider == "local-llm" and not (enable_local_llm or disable_offline_sim or legacy_allow_local)
        llm_resp = None
        if not offline_sim:
            # Enforce per-minute completion rate only for real provider calls
            await rate_limiter.check_chat_completion_rate(current_user.id)
            try:
                llm_resp = perform_chat_api_call(
                    api_endpoint=provider,
                    messages_payload=formatted,
                    api_key=api_key,
                    temp=body.temperature,
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
                except Exception as e:
                    logger.error(f"Failed to await async LLM response: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="LLM provider error"
                    ) from e
            except Exception as e:
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
            except Exception:
                return None

        # Extract assistant content from LLM response
        def _extract_text(resp: Any) -> str:
            if resp is None:
                return ""
            if isinstance(resp, str):
                return resp
            if isinstance(resp, dict):
                # OpenAI-style
                try:
                    return resp.get("choices", [{}])[0].get("message", {}).get("content", "") or resp.get("text", "")
                except Exception:
                    return resp.get("text", "")
            try:
                return str(resp)
            except Exception:
                return ""

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
                async def _offline_sse():
                    try:
                        import time as _time
                        created_ts = int(_time.time())
                        stream_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
                        model_id = model or "local-test"

                        # Initial role chunk (OpenAI-style)
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

                        # Content chunks
                        text = assistant_text or "OK"
                        words = text.split()
                        step = 20
                        if not words:
                            words = ["OK"]
                        for i in range(0, len(words), step):
                            chunk = " ".join(words[i : i + step])
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

                        # Finish chunk
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
                    except Exception as e:
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"
                        yield "data: [DONE]\n\n"
                return StreamingResponse(_offline_sse(), media_type="text/event-stream")
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
                except Exception:
                    pass

        # If streaming requested and we have a generator, stream SSE (real providers)
        if not offline_sim and bool(body.stream):
            try:
                # Feature flag: use unified SSEStream when enabled
                if str(os.getenv("STREAMS_UNIFIED", "0")).strip() in {"1", "true", "on", "yes"}:
                    stream = SSEStream(
                        labels={"component": "chat", "endpoint": "character_chat_stream"}
                    )
                    try:
                        logger.debug(
                            f"Unified SSE enabled: interval={stream.heartbeat_interval_s} mode={stream.heartbeat_mode}"
                        )
                    except Exception:
                        pass

                    async def _produce_async():
                        try:
                            if hasattr(llm_resp, "__aiter__"):
                                async for chunk in llm_resp:  # type: ignore
                                    line = _coerce_sse_line(chunk)
                                    if not line:
                                        continue
                                    if line.strip().lower() == "data: [done]":
                                        await stream.done()
                                        break
                                    await stream.send_raw_sse_line(line)
                            elif hasattr(llm_resp, "__iter__") and not isinstance(llm_resp, (str, bytes, dict, list)):
                                for chunk in llm_resp:  # type: ignore
                                    line = _coerce_sse_line(chunk)
                                    if not line:
                                        continue
                                    if line.strip().lower() == "data: [done]":
                                        await stream.done()
                                        break
                                    await stream.send_raw_sse_line(line)
                            # Ensure DONE if provider didn't send one
                            await stream.done()
                        except Exception as e:
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
                                except Exception:
                                    pass
                            # If DONE wasn’t enqueued for any reason, append one now
                            try:
                                if not getattr(stream, "_done_enqueued", False):
                                    yield sse_done()
                            except Exception:
                                pass
                        finally:
                            # Always tear down the background producer to avoid leaks
                            if not producer.done():
                                try:
                                    producer.cancel()
                                except Exception:
                                    pass
                                try:
                                    await producer
                                except (asyncio.CancelledError, Exception):
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
                        except Exception as e:
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
                        except Exception as e:
                            logger.exception("Exception occurred in streaming SSE generator.")
                            yield f"data: {json.dumps({'error': 'An internal error has occurred.'})}\n\n"
                        finally:
                            if not done_sent:
                                yield "data: [DONE]\n\n"
                    # Note: streaming mode does not persist assistant content
                    return StreamingResponse(_sse_gen(), media_type="text/event-stream")
            except Exception:
                # Fall through to non-streaming response
                pass
        if not assistant_text:
            assistant_text = ""

        # Persistence decision
        save_to_db = body.save_to_db
        if save_to_db is None:
            # default from Chat API settings
            try:
                from tldw_Server_API.app.api.v1.endpoints.chat import DEFAULT_SAVE_TO_DB as CHAT_DEFAULT_SAVE
                save_to_db = CHAT_DEFAULT_SAVE
            except Exception:
                save_to_db = False

        saved = False
        assistant_msg_id: Optional[str] = None
        if save_to_db:
            # Persist appended user message first, if any
            if body.append_user_message:
                try:
                    appended_user_id = str(uuid.uuid4())
                    db.add_message({
                        'id': appended_user_id,
                        'conversation_id': chat_id,
                        'parent_message_id': None,
                        'sender': 'user',
                        'content': body.append_user_message,
                        'client_id': str(current_user.id),
                        'version': 1
                    })
                except Exception as e:
                    logger.warning(f"Failed to persist appended user message: {e}")

            # Persist assistant response
            try:
                assistant_msg_id = str(uuid.uuid4())
                content_to_store = assistant_text
                if assistant_tool_calls:
                    try:
                        content_to_store = f"{assistant_text}\n\n[tool_calls]: {json.dumps(assistant_tool_calls)}"
                    except Exception:
                        pass
                # Use character name as the assistant sender (sanitized) for DB storage
                char_card = db.get_character_card_by_id(conversation.get('character_id')) or {}
                raw_name = (char_card.get('name') or 'Assistant') if isinstance(char_card, dict) else 'Assistant'
                assistant_sender = sanitize_sender_name(raw_name)
                db.add_message({
                    'id': assistant_msg_id,
                    'conversation_id': chat_id,
                    'parent_message_id': appended_user_id,
                    'sender': assistant_sender,
                    'content': content_to_store,
                    'client_id': str(current_user.id),
                    'version': 1
                })
                # Persist tool_calls into schema-level metadata for richer retrieval
                if assistant_tool_calls:
                    validated_tool_calls = _validate_and_truncate_tool_calls(assistant_tool_calls)
                    if validated_tool_calls:
                        try:
                            db.add_message_metadata(assistant_msg_id, tool_calls=validated_tool_calls)
                        except Exception as exc:
                            logger.debug(f"Non-fatal: failed to persist tool_calls metadata: {exc}")
                # Bump conversation metadata
                conv_for_update = db.get_conversation_by_id(chat_id)
                if conv_for_update:
                    try:
                        db.update_conversation(chat_id, {}, conv_for_update.get('version', 1))
                    except Exception:
                        pass
                saved = True
            except Exception as e:
                logger.warning(f"Failed to persist assistant message: {e}")

        return CharacterChatCompletionV2Response(
            chat_id=chat_id,
            character_id=conversation['character_id'],
            provider=provider,
            model=model,
            saved=saved,
            user_message_id=appended_user_id,
            assistant_message_id=assistant_msg_id,
            assistant_content=assistant_text,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in character chat completion for {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during character chat completion")


@router.get("/", response_model=ChatSessionListResponse,
            summary="List user's chat sessions", tags=["Chat Sessions"])
async def list_chat_sessions(
    character_id: Optional[int] = Query(None, description="Filter by character ID"),
    limit: int = Query(50, ge=1, le=200, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
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
            except Exception:
                # Fallback: filter by client_id in-memory if efficient count isn't available
                total_count = len([c for c in conversations if c.get('client_id') == user_id_str])
        else:
            # Efficient path: list conversations for this user directly
            conversations = db.get_conversations_for_user(user_id_str, limit=limit, offset=offset)
            try:
                total_count = db.count_conversations_for_user(user_id_str)
            except Exception:
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
            except Exception:
                messages = db.get_messages_for_conversation(conv['id'], limit=1000)
                conv['message_count'] = len(messages) if messages else 0

        return ChatSessionListResponse(
            chats=[_convert_db_conversation_to_response(conv) for conv in user_conversations],
            total=total_count,
            limit=limit,
            offset=offset
        )

    except Exception as e:
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
    except Exception as e:
        logger.error(f"Error updating chat session {chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating chat session"
        )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete chat session", tags=["Chat Sessions"])
async def delete_chat_session(
    chat_id: str = Path(..., description="Chat session ID"),
    expected_version: Optional[int] = Query(None, description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
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
                except Exception:
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

    except ConflictError as e:
        logger.warning(f"Conflict deleting chat session {chat_id}: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except CharactersRAGDBError as e:
        logger.error(f"DB error deleting chat session {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
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

        # Get character info if requested
        character = None
        if include_character:
            character = db.get_character_card_by_id(conversation['character_id'])

        # Get total message count for pagination info
        try:
            total_messages = db.count_messages_for_conversation(chat_id)
        except Exception:
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
            message_metadata_extra: Dict[str, Any] = {}
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
                except Exception:
                    md = None
                role_for_tool_calls = map_sender_to_role(
                    msg.get('sender'),
                    character.get('name') if character else None,
                )
                if md and md.get('tool_calls') is not None:
                    item["tool_calls"] = md.get('tool_calls')
                elif role_for_tool_calls == 'assistant':
                    # Fallback: parse inline suffix [tool_calls]: <json>
                    try:
                        import re as _re, json as _json
                        m = _re.search(r"\[tool_calls\]\s*:\s*(\{.*|\[.*)$", (msg.get('content') or ''), _re.DOTALL)
                        if m:
                            parsed = _json.loads(m.group(1).strip())
                            if isinstance(parsed, dict) and 'tool_calls' in parsed:
                                tc_list = parsed.get('tool_calls')
                            else:
                                tc_list = parsed
                            if isinstance(tc_list, list):
                                item["tool_calls"] = tc_list
                    except Exception:
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
    except Exception as e:
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
        except Exception:
            logger.debug("Non-fatal: message cap check skipped in persist endpoint")

        assistant_msg_id = str(uuid.uuid4())
        # Resolve assistant sender as sanitized character name
        char_card = db.get_character_card_by_id(conversation.get('character_id')) or {}
        raw_name = (char_card.get('name') or 'Assistant') if isinstance(char_card, dict) else 'Assistant'
        assistant_sender = sanitize_sender_name(raw_name)
        db.add_message({
            'id': assistant_msg_id,
            'conversation_id': chat_id,
            'parent_message_id': body.user_message_id,
            'sender': assistant_sender,
            'content': body.assistant_content,
            'ranking': body.ranking if getattr(body, 'ranking', None) is not None else None,
            'client_id': str(current_user.id),
            'version': 1,
        })
        # Persist metadata: tool_calls and usage
        try:
            extra = None
            if getattr(body, 'usage', None) is not None:
                extra = {"usage": body.usage}
            validated_tool_calls = _validate_and_truncate_tool_calls(getattr(body, 'tool_calls', None))
            if validated_tool_calls is not None or extra is not None:
                db.add_message_metadata(assistant_msg_id, tool_calls=validated_tool_calls, extra=extra)
        except Exception:
            pass

        # Touch conversation metadata
        try:
            conv_for_update = db.get_conversation_by_id(chat_id)
            if conv_for_update:
                # Optionally update chat rating alongside metadata bump
                update_fields = {}
                if getattr(body, 'chat_rating', None) is not None:
                    update_fields['rating'] = body.chat_rating
                db.update_conversation(chat_id, update_fields, conv_for_update.get('version', 1))
        except Exception:
            pass

        return CharacterChatStreamPersistResponse(chat_id=chat_id, assistant_message_id=assistant_msg_id, saved=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error persisting streamed assistant message for {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist assistant message")


#
# End of character_chat_sessions.py
######################################################################################################################
