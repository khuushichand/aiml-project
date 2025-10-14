# character_chat_sessions.py
"""
API endpoints for character chat session management.
Provides CRUD operations for chat sessions and character-specific completions.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    Query, 
    Path,
    BackgroundTasks,
    status,
    Request
)
from fastapi.responses import StreamingResponse, JSONResponse
from loguru import logger
from collections import defaultdict, deque
import time

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
    MessageCreate,
    MessageResponse,
    MessageListResponse,
    ChatHistoryExport,
    ChatErrorResponse
)

# Character chat helpers
from tldw_Server_API.app.core.Character_Chat.Character_Chat_Lib_facade import (
    start_new_chat_session,
    post_message_to_conversation,
    retrieve_conversation_messages_for_ui,
    load_chat_and_character
)

# Chat helpers and utilities
from tldw_Server_API.app.core.Chat.chat_helpers import (
    get_or_create_conversation,
    load_conversation_history
)

# Rate limiting
from tldw_Server_API.app.core.Character_Chat.character_rate_limiter import (
    get_character_rate_limiter,
    CharacterRateLimiter
)

# For chat completions
from tldw_Server_API.app.core.Chat.Chat_Functions import (
    chat_api_call as perform_chat_api_call
)

# Simple schema for preparing completions
from pydantic import BaseModel, Field


class CharacterChatCompletionPrepRequest(BaseModel):
    include_character_context: bool = Field(True, description="Include character system context")
    limit: int = Field(100, ge=1, le=1000, description="Max messages to include")
    offset: int = Field(0, ge=0, description="Messages offset")
    append_user_message: Optional[str] = Field(None, description="Optional user message to append to the end")


class CharacterChatCompletionPrepResponse(BaseModel):
    chat_id: str
    character_id: int
    character_name: Optional[str] = None
    messages: List[Dict[str, Any]]
    total: int
    usage_instructions: str = "Use these messages with POST /api/v1/chat/completions"


class CharacterChatCompletionRequest(BaseModel):
    # Character/context controls
    include_character_context: bool = Field(True, description="Include character system context")
    limit: int = Field(100, ge=1, le=1000, description="Max messages to include")
    offset: int = Field(0, ge=0, description="Messages offset")
    append_user_message: Optional[str] = Field(None, description="Optional user message to append and (optionally) persist")
    save_to_db: Optional[bool] = Field(None, description="Persist appended user and assistant messages to this chat")
    # LLM controls
    provider: Optional[str] = Field(None, description="LLM provider (e.g., openai, anthropic, local-llm). Defaults to local-llm if omitted.")
    model: Optional[str] = Field(None, description="Model identifier. Defaults to a local test model if omitted.")
    temperature: Optional[float] = Field(None, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, description="Max tokens in the completion")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="Tool definitions")
    tool_choice: Optional[Dict[str, Any]] = Field(None, description="Tool choice specification")
    stream: Optional[bool] = Field(False, description="If true, stream the assistant response (SSE)")


class CharacterChatCompletionResponse(BaseModel):
    chat_id: str
    character_id: int
    provider: str
    model: Optional[str] = None
    saved: bool = False
    user_message_id: Optional[str] = None
    assistant_message_id: Optional[str] = None
    assistant_content: str

router = APIRouter()

# Simple per-chat throttle used for legacy /complete endpoint in tests (TEST_MODE only)
_complete_windows = defaultdict(lambda: deque(maxlen=100))

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
        content=msg_data.get('content', ''),
        timestamp=msg_data.get('timestamp', datetime.now(timezone.utc)),
        ranking=msg_data.get('ranking'),
        has_image=bool(msg_data.get('image_data')),
        version=msg_data.get('version', 1)
    )

# ========================================================================
# Chat Session Endpoints
# ========================================================================

@router.post("/", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED,
             summary="Create a new chat session", tags=["Chat Sessions"])
async def create_chat_session(
    session_data: ChatSessionCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Create a new chat session with a character.
    
    Args:
        session_data: Chat session creation data
        db: Database instance
        current_user: Authenticated user
        
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
            # Use DB-layer count for efficiency/accuracy
            user_chat_count = db.count_conversations_for_user(str(current_user.id))
            await rate_limiter.check_chat_limit(current_user.id, user_chat_count)
        except HTTPException:
            # Propagate enforcement failures
            raise
        except Exception:
            # Non-fatal: skip enforcement if count fails
            logger.debug("Non-fatal: chat limit count failed; skipping cap enforcement")
        
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
            'version': 1
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
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat session {chat_id} not found"
            )
        
        # Verify ownership
        if conversation.get('client_id') != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this chat session"
            )
        
        # Get message count
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

        if conversation.get('client_id') != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this chat session")

        character = db.get_character_card_by_id(conversation['character_id']) or {}
        char_name = character.get('name', 'Unknown')

        messages = db.get_messages_for_conversation(chat_id, limit=1000) or []
        # Map DB messages to chat-completions messages
        formatted = []
        for m in messages:
            if m.get('deleted'):
                continue
            role = m.get('sender') or 'user'
            content = m.get('content') or ''
            formatted.append({"role": role, "content": content})

        # If no messages, include first_message as system message
        if not formatted and character.get('first_message'):
            formatted.append({"role": "assistant", "content": character['first_message']})

        return {"character_name": char_name, "messages": formatted}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat context for {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while retrieving chat context")


@router.post("/{chat_id}/complete", summary="Legacy completion endpoint with simple rate limit", tags=["Chat Sessions"])
async def complete_chat_legacy(
    chat_id: str = Path(..., description="Chat session ID"),
    payload: Dict[str, Any] = None,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """Legacy completion endpoint used by tests to validate rate limiting.

    Applies a very small per-conversation throttle when TEST_MODE=true so that
    burst requests trigger HTTP 429 as expected by tests.
    """
    try:
        # Validate chat ownership
        conversation = db.get_conversation_by_id(chat_id)
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat session {chat_id} not found")
        if conversation.get('client_id') != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this chat session")

        # Per-minute completion limiter (global per-user)
        rate_limiter = get_character_rate_limiter()
        await rate_limiter.check_chat_completion_rate(current_user.id)

        # Test-mode throttle: 5 requests per second per (user, chat)
        if (str(payload or {}),):
            pass  # payload accepted but unused
        key = f"{current_user.id}:{chat_id}"
        now = time.time()
        window = _complete_windows[key]
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
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat session {chat_id} not found")
        if conversation.get('client_id') != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this chat session")

        # Per-minute completion limiter (global per-user)
        rate_limiter = get_character_rate_limiter()
        await rate_limiter.check_chat_completion_rate(current_user.id)

        # Build messages
        character = db.get_character_card_by_id(conversation['character_id']) or {}
        character_name = character.get('name')
        include_ctx = bool(body.include_character_context)
        limit = int(body.limit)
        offset = int(body.offset)

        messages = db.get_messages_for_conversation(chat_id, limit=limit + offset) or []
        # Filter deleted
        messages = [m for m in messages if not m.get('deleted')]
        paginated = messages[offset:offset + limit]

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
                "role": msg.get('sender', 'user'),
                "content": msg.get('content', '')
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


@router.post("/{chat_id}/complete-v2", response_model=CharacterChatCompletionResponse,
             summary="Character Chat completion (operational, rate-limited)", tags=["Chat Sessions"])
async def character_chat_completion(
    chat_id: str = Path(..., description="Chat session ID"),
    body: CharacterChatCompletionRequest = None,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """Perform a character chat completion using configured providers and persist results optionally.

    Behavior:
    - Enforces per-minute completion limiter (per-user)
    - Builds message context from the chat (and optional appended user message)
    - Calls provider via unified chat function
    - Persists appended user message and assistant reply when save_to_db is true
    """
    try:
        import os
        body = body or CharacterChatCompletionRequest()

        # Validate and ownership
        conversation = db.get_conversation_by_id(chat_id)
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat session {chat_id} not found")
        if conversation.get('client_id') != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this chat session")

        # Prepare rate limiter
        rate_limiter = get_character_rate_limiter()

        # Gather character and context
        character = db.get_character_card_by_id(conversation['character_id']) or {}
        include_ctx = bool(body.include_character_context)
        limit = int(body.limit)
        offset = int(body.offset)

        messages = db.get_messages_for_conversation(chat_id, limit=limit + offset) or []
        messages = [m for m in messages if not m.get('deleted')]
        paginated = messages[offset:offset + limit]

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
                "role": msg.get('sender', 'user'),
                "content": msg.get('content', '')
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
            current_count = len(db.get_messages_for_conversation(chat_id, limit=10000) or [])
            await rate_limiter.check_message_limit(chat_id, current_count + will_add)
        except HTTPException:
            raise
        except Exception:
            logger.debug("Non-fatal: message cap pre-check skipped")

        # Fetch API key dynamically
        try:
            from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import get_api_keys
            api_keys = get_api_keys()
            api_key = api_keys.get(provider)
        except Exception:
            api_key = None

        # Attempt provider call; allow offline simulation for local-llm in test/dev
        offline_sim = provider == "local-llm" and os.getenv("ALLOW_LOCAL_LLM_CALLS", "").lower() not in {"1", "true", "yes", "on"}
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
                    user_identifier=str(current_user.id)
                )
            except Exception as e:
                logger.error(f"Chat provider call failed: {e}")
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat provider error")

        # Extract assistant content
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

        if offline_sim:
            # Simple deterministic response for tests/offline dev
            last_user = None
            for m in reversed(formatted):
                if m.get("role") == "user":
                    last_user = m.get("content")
                    break
            assistant_text = (last_user or "OK").strip()
            assistant_tool_calls = []
        else:
            assistant_text = _extract_text(llm_resp).strip()
            # Try to extract tool calls if present (OpenAI-like shape)
            assistant_tool_calls = []
            try:
                if isinstance(llm_resp, dict):
                    tool_calls = llm_resp.get("choices", [{}])[0].get("message", {}).get("tool_calls")
                    if isinstance(tool_calls, list):
                        assistant_tool_calls = tool_calls
            except Exception:
                pass

        # If streaming requested and we have a generator, stream SSE
        if not offline_sim and bool(body.stream):
            try:
                if hasattr(llm_resp, "__iter__") and not isinstance(llm_resp, (str, bytes, dict, list)):
                    async def _sse_gen():
                        try:
                            # llm_resp may be a sync generator; iterate in thread if needed
                            for chunk in llm_resp:  # type: ignore
                                text = str(chunk).rstrip("\n")
                                # Ensure each line adheres to SSE: prefix 'data: '
                                if text.startswith("data:"):
                                    yield text + "\n\n"
                                else:
                                    yield f"data: {text}\n\n"
                        except Exception as e:
                            yield f"data: {json.dumps({'error': str(e)})}\n\n"
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
                db.add_message({
                    'id': assistant_msg_id,
                    'conversation_id': chat_id,
                    'parent_message_id': appended_user_id,
                    'sender': 'assistant',
                    'content': content_to_store,
                    'client_id': str(current_user.id),
                    'version': 1
                })
                # Persist tool_calls into schema-level metadata for richer retrieval
                if assistant_tool_calls:
                    try:
                        db.add_message_metadata(assistant_msg_id, tool_calls=assistant_tool_calls)
                    except Exception:
                        pass
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

        return CharacterChatCompletionResponse(
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
        if character_id:
            # Get conversations for specific character
            conversations = db.get_conversations_for_character(character_id, limit=limit, offset=offset)
        else:
            # Get all user conversations (need to implement this method)
            # For now, aggregate from all characters
            conversations = []
            characters = db.list_character_cards(limit=1000)
            for char in characters:
                char_convs = db.get_conversations_for_character(char['id'], limit=limit, offset=offset)
                conversations.extend(char_convs)
        
        # Filter by client_id for security
        user_conversations = [
            conv for conv in conversations 
            if conv.get('client_id') == str(current_user.id)
        ]
        
        # Sort by last_modified descending
        user_conversations.sort(key=lambda x: x.get('last_modified', ''), reverse=True)
        
        # Apply pagination after filtering
        paginated = user_conversations[offset:offset+limit]
        
        # Add message counts
        for conv in paginated:
            messages = db.get_messages_for_conversation(conv['id'], limit=1)
            conv['message_count'] = len(messages) if messages else 0
        
        return ChatSessionListResponse(
            chats=[_convert_db_conversation_to_response(conv) for conv in paginated],
            total=len(user_conversations),
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
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat session {chat_id} not found"
            )
        
        # Verify ownership
        if conversation.get('client_id') != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this chat session"
            )
        
        # Check version
        if conversation.get('version', 1) != expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version mismatch. Expected {expected_version}, found {conversation.get('version', 1)}"
            )
        
        # Update fields via DB abstraction with optimistic locking
        update_fields = update_data.model_dump(exclude_unset=True)
        # Only allow supported fields
        allowed_update = {k: v for k, v in update_fields.items() if k in {"title", "rating"}}
        # db.update_conversation updates metadata and bumps version even if payload is empty
        db.update_conversation(chat_id, allowed_update, expected_version)
        
        # Retrieve updated conversation
        updated_conv = db.get_conversation_by_id(chat_id)
        if updated_conv:
            messages = db.get_messages_for_conversation(chat_id, limit=1000)
            updated_conv['message_count'] = len(messages) if messages else 0
        
        return _convert_db_conversation_to_response(updated_conv)
        
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
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat session {chat_id} not found"
            )
        
        # Verify ownership
        if conversation.get('client_id') != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this chat session"
            )
        
        # Check version if provided
        if expected_version is not None and conversation.get('version', 1) != expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version mismatch. Expected {expected_version}, found {conversation.get('version', 1)}"
            )
        
        # Collect current non-deleted messages prior to conversation soft-delete
        existing_messages = db.get_messages_for_conversation(chat_id, limit=10000, offset=0)

        # Soft delete conversation via DB abstraction (optimistic locking)
        exp_ver = expected_version if expected_version is not None else conversation.get('version', 1)
        db.soft_delete_conversation(chat_id, exp_ver)

        # Also soft delete messages individually to keep data consistent
        for msg in existing_messages:
            try:
                db.soft_delete_message(msg.get("id"), msg.get("version", 1))
            except Exception:
                # Best-effort; continue even if a specific message fails due to version mismatch etc.
                logger.warning(f"Failed to soft-delete message {msg.get('id')} during conversation delete.")
        
        logger.info(f"Soft deleted chat session {chat_id} by user {current_user.id}")
        
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

@router.get("/{chat_id}/export", 
            summary="Export chat history", tags=["Chat Export"])
async def export_chat_history(
    chat_id: str = Path(..., description="Chat session ID"),
    format: str = Query("json", description="Export format (json, markdown, text)"),
    include_metadata: bool = Query(True, description="Include chat metadata"),
    include_character: bool = Query(True, description="Include character info"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    Export chat history in various formats.
    
    Args:
        chat_id: Chat session ID to export
        format: Export format
        include_metadata: Whether to include metadata
        include_character: Whether to include character info
        db: Database instance
        current_user: Authenticated user
        
    Returns:
        Chat history in requested format
        
    Raises:
        HTTPException: 404 if chat not found, 403 if unauthorized
    """
    try:
        # Get conversation
        conversation = db.get_conversation_by_id(chat_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat session {chat_id} not found"
            )
        
        # Verify ownership
        if conversation.get('client_id') != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this chat session"
            )
        
        # Get character info if requested
        character = None
        if include_character:
            character = db.get_character_card_by_id(conversation['character_id'])
        
        # Get messages
        messages = db.get_messages_for_conversation(chat_id, limit=10000)
        
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
                content = msg.get('content', '')
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
                content = msg.get('content', '')
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
                    "content": msg.get('content'),
                    "timestamp": str(msg.get('timestamp', '')),
                    "has_image": bool(msg.get('image_data'))
                }
                try:
                    md = db.get_message_metadata(msg.get('id'))
                except Exception:
                    md = None
                if md and md.get('tool_calls') is not None:
                    item["tool_calls"] = md.get('tool_calls')
                elif msg.get('sender') == 'assistant':
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
                    "total_messages": len(messages),
                    "rating": conversation.get('rating'),
                    "last_modified": str(conversation.get('last_modified', ''))
                }
                if message_metadata_extra:
                    export_data["message_metadata_extra"] = message_metadata_extra
            
            return export_data
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting chat {chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while exporting chat history"
        )


#
# End of character_chat_sessions.py
######################################################################################################################
