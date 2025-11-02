# character_messages.py
"""
API endpoints for message management within character chat sessions.
Provides CRUD operations for messages in conversations.
"""

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
    status
)
from loguru import logger
from tldw_Server_API.app.core.config import settings

# Database and authentication dependencies
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)

# Schemas
from tldw_Server_API.app.api.v1.schemas.chat_session_schemas import (
    MessageCreate,
    MessageResponse,
    MessageUpdate,
    MessageListResponse
)

# Character chat helpers
from tldw_Server_API.app.core.Character_Chat.Character_Chat_Lib_facade import (
    retrieve_message_details,
    edit_message_content,
    remove_message_from_conversation,
    find_messages_in_conversation,
    map_sender_to_role,
)

# Rate limiting
from tldw_Server_API.app.core.Character_Chat.character_rate_limiter import (
    get_character_rate_limiter
)

router = APIRouter()

# ========================================================================
# Helper Functions
# ========================================================================

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

def _verify_conversation_access(
    db: CharactersRAGDB,
    conversation_id: str,
    user_id: int
) -> Dict[str, Any]:
    """
    Verify user has access to a conversation.

    Args:
        db: Database instance
        conversation_id: Conversation ID to check
        user_id: User ID to verify

    Returns:
        Conversation data if access allowed

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized
    """
    conversation = db.get_conversation_by_id(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session {conversation_id} not found"
        )

    if conversation.get('client_id') != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this chat session"
        )

    return conversation

def _verify_message_access(
    db: CharactersRAGDB,
    message_id: str,
    user_id: int
) -> Dict[str, Any]:
    """
    Verify user has access to a message using DB abstractions.
    """
    message = db.get_message_by_id(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found"
        )
    conv = db.get_conversation_by_id(message.get('conversation_id'))
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session {message.get('conversation_id')} not found"
        )
    if conv.get('client_id') != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this message"
        )
    message['client_id'] = conv.get('client_id')
    return message

# ========================================================================
# Message Endpoints
# ========================================================================

@router.post("/chats/{chat_id}/messages", response_model=MessageResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Send a message in a chat", tags=["Messages"])
async def send_message(
    message_data: MessageCreate,
    chat_id: str = Path(..., description="Chat session ID"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    Add a new message to a chat session.

    Args:
        chat_id: Chat session ID
        message_data: Message content and metadata
        db: Database instance
        current_user: Authenticated user

    Returns:
        Created message details

    Raises:
        HTTPException: 404 if chat not found, 403 if unauthorized, 429 if rate limited
    """
    try:
        # Check rate limits (global + per-minute + per-chat message count)
        rate_limiter = get_character_rate_limiter()
        await rate_limiter.check_rate_limit(current_user.id, "message_send")
        await rate_limiter.check_message_send_rate(current_user.id)

        # Verify conversation access
        conversation = _verify_conversation_access(db, chat_id, current_user.id)
        # Enforce per-chat message cap
        try:
            existing_msgs = db.get_messages_for_conversation(chat_id, limit=10000)
            await rate_limiter.check_message_limit(chat_id, len(existing_msgs) + 1)
        except HTTPException:
            raise
        except Exception:
            logger.debug("Non-fatal: message cap check skipped")

        # Validate parent message if provided
        if message_data.parent_message_id:
            parent_msg = _verify_message_access(db, message_data.parent_message_id, current_user.id)
            if parent_msg.get('conversation_id') != chat_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent message must be from the same conversation"
                )

        # Create message
        message_id = str(uuid.uuid4())

        # Map role to sender format used in database
        sender_map = {
            "user": "user",
            "assistant": "assistant",
            "system": "system"
        }
        sender = sender_map.get(message_data.role, "user")

        msg_data = {
            'id': message_id,
            'conversation_id': chat_id,
            'parent_message_id': message_data.parent_message_id,
            'sender': sender,
            'content': message_data.content,
            'client_id': str(current_user.id),
            'version': 1
        }

        # Handle image if provided
        if message_data.image_base64:
            try:
                import base64
                img_data = base64.b64decode(message_data.image_base64)
                # Preflight size check before DB layer
                try:
                    _max_img_bytes = int(settings.get("MAX_MESSAGE_IMAGE_BYTES", 5 * 1024 * 1024))
                except Exception:
                    _max_img_bytes = 5 * 1024 * 1024
                if isinstance(img_data, (bytes, bytearray)) and len(img_data) > _max_img_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Image too large. Max {_max_img_bytes} bytes allowed."
                    )
                msg_data['image_data'] = img_data
                msg_data['image_mime_type'] = 'image/png'  # Default, could detect
            except Exception as e:
                logger.warning(f"Failed to decode image data: {e}")

        # Add to database
        created_id = db.add_message(msg_data)

        if not created_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create message"
            )

        # Update conversation metadata (last_modified/version) via DB abstraction
        conv_for_update = db.get_conversation_by_id(chat_id)
        if conv_for_update:
            try:
                db.update_conversation(chat_id, {}, conv_for_update.get('version', 1))
            except (ConflictError, CharactersRAGDBError):
                logger.debug(f"Non-fatal: failed to bump conversation metadata for {chat_id}")

        # Get character details for placeholders
        character_id = conversation.get('character_id')
        character = db.get_character_card_by_id(character_id) if character_id else None
        character_name = character.get('name', 'Assistant') if character else 'Assistant'
        user_name = conversation.get('user_name', 'User')

        # Retrieve created message with placeholder parameters
        created_msg = retrieve_message_details(db, created_id, character_name, user_name)

        logger.info(f"Created message {created_id} in chat {chat_id} by user {current_user.id}")

        return _convert_db_message_to_response(created_msg)

    except HTTPException:
        raise
    except ConflictError as e:
        # Optimistic lock or state conflict during creation
        logger.warning(f"Conflict sending message to chat {chat_id}: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except InputError as e:
        # Map DB validation errors to appropriate HTTP codes
        msg = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        if "exceeds maximum size" in msg.lower():
            status_code = status.HTTP_413_CONTENT_TOO_LARGE
        logger.warning(f"Input error sending message to chat {chat_id}: {e}")
        raise HTTPException(status_code=status_code, detail=msg)
    except CharactersRAGDBError as e:
        logger.error(f"DB error sending message to chat {chat_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending message to chat {chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while sending message"
        )


@router.get("/chats/{chat_id}/messages",
            summary="Get messages in a chat", tags=["Messages"])
async def get_chat_messages(
    chat_id: str = Path(..., description="Chat session ID"),
    limit: int = Query(50, ge=1, le=200, description="Number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    include_deleted: bool = Query(False, description="Include deleted messages"),
    include_character_context: bool = Query(False, description="Include character context for chat completions"),
    format_for_completions: bool = Query(False, description="Format messages for use with chat/completions endpoint"),
    include_tool_calls: bool = Query(False, description="Include tool_calls metadata per message when available (standard format only)"),
    include_metadata: bool = Query(False, description="Include stored message metadata.extra JSON where available"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    Get messages from a chat session.

    Args:
        chat_id: Chat session ID
        limit: Maximum number of messages to return
        offset: Number of messages to skip
        include_deleted: Whether to include soft-deleted messages
        include_character_context: Include character personality as system message
        format_for_completions: Return in format ready for /api/v1/chat/completions
        db: Database instance
        current_user: Authenticated user

    Returns:
        List of messages with pagination info, or formatted for completions if requested

    Raises:
        HTTPException: 404 if chat not found, 403 if unauthorized
    """
    try:
        # Verify conversation access
        conversation = _verify_conversation_access(db, chat_id, current_user.id)

        # Get messages (honor include_deleted and DB pagination)
        messages = db.get_messages_for_conversation(chat_id, limit=limit, offset=offset, include_deleted=include_deleted)

        if not messages:
            messages = []
        paginated = messages

        # If character context or completions format requested
        if include_character_context or format_for_completions:
            # Get character info
            character_id = conversation.get('character_id')
            character = db.get_character_card_by_id(character_id) if character_id else None

            if format_for_completions:
                # Return format ready for chat completions endpoint
                formatted_messages = []
                metadata_extra_map: Dict[str, Any] = {}

                # Add system prompt if character exists
                if character and include_character_context:
                    system_prompt_parts = [
                        f"You are {character.get('name', 'Assistant')}.",
                        character.get('description', ''),
                        character.get('personality', ''),
                        character.get('scenario', ''),
                        character.get('system_prompt', '')
                    ]
                    system_prompt = '\n'.join(part for part in system_prompt_parts if part)
                    formatted_messages.append({
                        "role": "system",
                        "content": system_prompt.strip()
                    })

                # Add conversation messages with optional tool role messages
                import re as _re
                _suffix_re = _re.compile(r"\[tool_calls\]\s*:\s*(\{.*|\[.*)$", _re.DOTALL)
                for msg in paginated:
                    role = map_sender_to_role(msg.get('sender'), character.get('name') if character else None)
                    content = msg.get('content', '')
                    msg_id = msg.get('id')

                    base_message: Dict[str, Any] = {"role": role, "content": content}

                    # If assistant message has tool_calls in metadata, include tool role messages (OpenAI-compatible)
                    md = None
                    try:
                        md = db.get_message_metadata(msg_id)
                    except Exception:
                        md = None

                    if include_metadata and md and md.get('extra') is not None and msg_id:
                        metadata_extra_map[msg_id] = md.get('extra')

                    # Add the original message first
                    tool_calls_list = None
                    if role == 'assistant':
                        if md and isinstance(md.get('tool_calls'), list) and md.get('tool_calls'):
                            tool_calls_list = md.get('tool_calls')
                        else:
                            # Fallback: parse inline suffix if present
                            try:
                                match = _suffix_re.search(content or '')
                                if match:
                                    import json as _json
                                    parsed = _json.loads(match.group(1).strip())
                                    if isinstance(parsed, dict) and 'tool_calls' in parsed:
                                        tool_calls_list = parsed.get('tool_calls')
                                    else:
                                        tool_calls_list = parsed
                                    if not isinstance(tool_calls_list, list):
                                        tool_calls_list = None
                            except Exception as e:
                                logger.debug(f"character_messages: failed to parse tool_calls from suffix: {e}")
                                tool_calls_list = None

                    if role == 'assistant' and tool_calls_list:
                        # Optionally include tool_calls array on assistant message for completeness
                        base_message_with_tools = dict(base_message)
                        base_message_with_tools["tool_calls"] = tool_calls_list
                        formatted_messages.append(base_message_with_tools)

                        # Emit tool role messages after the assistant message
                        tool_results_by_id: Dict[str, Any] = {}
                        try:
                            extra = md.get('extra') or {}
                            # Common pattern: extra.tool_results: { tool_call_id: { ... } }
                            tr = extra.get('tool_results') if isinstance(extra, dict) else None
                            if isinstance(tr, dict):
                                tool_results_by_id = tr
                        except Exception as e:
                            logger.debug(f"character_messages: failed to extract tool_results: {e}")
                            tool_results_by_id = {}

                        for tc in tool_calls_list:
                            tc_id = None
                            tc_name = None
                            try:
                                tc_id = tc.get('id')
                                func = tc.get('function') or {}
                                tc_name = func.get('name')
                            except Exception as e:
                                logger.debug(f"character_messages: tool_call parse error: {e}")
                            tool_content = ""
                            # If we have stored results keyed by tool_call_id, include them
                            try:
                                if tc_id and tool_results_by_id.get(tc_id) is not None:
                                    # Convert result to string; JSON-encode if needed
                                    res = tool_results_by_id.get(tc_id)
                                    if isinstance(res, (dict, list)):
                                        import json as _json
                                        tool_content = _json.dumps(res)
                                    else:
                                        tool_content = str(res)
                            except Exception as e:
                                logger.debug(f"character_messages: failed to stringify tool result: {e}")
                            tool_msg: Dict[str, Any] = {"role": "tool", "content": tool_content}
                            if tc_id:
                                tool_msg["tool_call_id"] = tc_id
                            if tc_name:
                                tool_msg["name"] = tc_name
                            formatted_messages.append(tool_msg)
                    else:
                        # No tools: append base message as-is
                        formatted_messages.append(base_message)

                resp_obj: Dict[str, Any] = {
                    "character_name": character.get('name') if character else None,
                    "character_id": character_id,
                    "chat_id": chat_id,
                    "messages": formatted_messages,
                    "total": len(messages),
                    "usage_instructions": "Use these messages with POST /api/v1/chat/completions"
                }
                if include_metadata and metadata_extra_map:
                    # Provide sidecar of metadata.extra without polluting message objects
                    resp_obj["metadata_extra"] = metadata_extra_map
                return resp_obj

            # Otherwise return standard format with character info
            # Build standard response messages, optionally including tool_calls
            built_messages = []
            for m in paginated:
                resp = _convert_db_message_to_response(m)
                if include_tool_calls:
                    try:
                        md = db.get_message_metadata(resp.id)
                        if md and md.get('tool_calls') is not None:
                            resp = resp.model_copy(update={"tool_calls": md.get('tool_calls')})
                    except Exception as e:
                        logger.debug(f"character_messages: failed to include tool_calls in response: {e}")
                if include_metadata:
                    try:
                        md = db.get_message_metadata(resp.id)
                        if md and md.get('extra') is not None:
                            resp = resp.model_copy(update={"metadata_extra": md.get('extra')})
                    except Exception as e:
                        logger.debug(f"character_messages: failed to include metadata_extra in response: {e}")
                built_messages.append(resp)
            response = MessageListResponse(
                messages=built_messages,
                total=len(messages),
                limit=limit,
                offset=offset
            )

            # Add character context as additional field
            if character:
                response_dict = response.model_dump()
                response_dict['character_context'] = {
                    "name": character.get('name'),
                    "description": character.get('description'),
                    "personality": character.get('personality'),
                    "system_prompt": character.get('system_prompt')
                }
                return response_dict

            return response

        # Standard response
        # Standard response (no character context)
        built_messages = []
        for m in paginated:
            resp = _convert_db_message_to_response(m)
            if include_tool_calls:
                try:
                    md = db.get_message_metadata(resp.id)
                    if md and md.get('tool_calls') is not None:
                        resp = resp.model_copy(update={"tool_calls": md.get('tool_calls')})
                except Exception as e:
                    logger.debug(f"character_messages: failed to include tool_calls (std): {e}")
            if include_metadata:
                try:
                    md = db.get_message_metadata(resp.id)
                    if md and md.get('extra') is not None:
                        resp = resp.model_copy(update={"metadata_extra": md.get('extra')})
                except Exception as e:
                    logger.debug(f"character_messages: failed to include metadata_extra (std): {e}")
            built_messages.append(resp)
        return MessageListResponse(
            messages=built_messages,
            total=len(messages),
            limit=limit,
            offset=offset
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages for chat {chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving messages"
        )


@router.get("/messages/{message_id}", response_model=MessageResponse,
            summary="Get a specific message", tags=["Messages"])
async def get_message(
    message_id: str = Path(..., description="Message ID"),
    include_tool_calls: bool = Query(False, description="Include tool_calls metadata when available"),
    include_metadata: bool = Query(False, description="Include stored message metadata.extra JSON where available"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    Get details of a specific message.

    Args:
        message_id: Message ID
        db: Database instance
        current_user: Authenticated user

    Returns:
        Message details

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized
    """
    try:
        message = _verify_message_access(db, message_id, current_user.id)
        resp = _convert_db_message_to_response(message)
        if include_tool_calls or include_metadata:
            try:
                md = db.get_message_metadata(resp.id)
                if include_tool_calls and md and md.get('tool_calls') is not None:
                    resp = resp.model_copy(update={"tool_calls": md.get('tool_calls')})
                if include_metadata and md and md.get('extra') is not None:
                    resp = resp.model_copy(update={"metadata_extra": md.get('extra')})
            except Exception:
                pass
        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting message {message_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving message"
        )


@router.put("/messages/{message_id}", response_model=MessageResponse,
            summary="Edit a message", tags=["Messages"])
async def edit_message(
    update_data: MessageUpdate,
    message_id: str = Path(..., description="Message ID"),
    expected_version: int = Query(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    Edit the content of a message.

    Args:
        message_id: Message ID to edit
        update_data: New message content
        expected_version: Expected version for optimistic locking
        db: Database instance
        current_user: Authenticated user

    Returns:
        Updated message details

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized, 409 if version conflict
    """
    try:
        # Verify message access
        message = _verify_message_access(db, message_id, current_user.id)

        # Check version
        if message.get('version', 1) != expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version mismatch. Expected {expected_version}, found {message.get('version', 1)}"
            )

        # Update message content
        success = edit_message_content(db, message_id, update_data.content, expected_version)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update message"
            )

        # Update conversation metadata (last_modified/version) via DB abstraction
        conv = db.get_conversation_by_id(message['conversation_id'])
        if conv:
            try:
                db.update_conversation(message['conversation_id'], {}, conv.get('version', 1))
            except (ConflictError, CharactersRAGDBError):
                logger.debug(f"Non-fatal: failed to bump conversation metadata for {message['conversation_id']}")

        # Get character details for placeholders
        conversation = db.get_conversation_by_id(message['conversation_id'])
        character_id = conversation.get('character_id') if conversation else None
        character = db.get_character_card_by_id(character_id) if character_id else None
        character_name = character.get('name', 'Assistant') if character else 'Assistant'
        user_name = conversation.get('user_name', 'User') if conversation else 'User'

        # Retrieve updated message with placeholder parameters
        updated_msg = retrieve_message_details(db, message_id, character_name, user_name)

        logger.info(f"Updated message {message_id} by user {current_user.id}")

        return _convert_db_message_to_response(updated_msg)

    except HTTPException:
        raise
    except ConflictError as e:
        logger.warning(f"Conflict editing message {message_id}: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except CharactersRAGDBError as e:
        logger.error(f"DB error editing message {message_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Error editing message {message_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while editing message"
        )


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a message", tags=["Messages"])
async def delete_message(
    message_id: str = Path(..., description="Message ID"),
    expected_version: int = Query(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    Soft delete a message from a conversation.

    Args:
        message_id: Message ID to delete
        expected_version: Expected version for optimistic locking
        db: Database instance
        current_user: Authenticated user

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized, 409 if version conflict
    """
    try:
        # Verify message access
        message = _verify_message_access(db, message_id, current_user.id)

        # Check version
        if message.get('version', 1) != expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version mismatch. Expected {expected_version}, found {message.get('version', 1)}"
            )

        # Soft delete the message
        success = remove_message_from_conversation(db, message_id, expected_version)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete message"
            )

        # Update conversation metadata (last_modified/version) via DB abstraction
        conv = db.get_conversation_by_id(message['conversation_id'])
        if conv:
            try:
                db.update_conversation(message['conversation_id'], {}, conv.get('version', 1))
            except (ConflictError, CharactersRAGDBError):
                logger.debug(f"Non-fatal: failed to bump conversation metadata for {message['conversation_id']}")

        logger.info(f"Soft deleted message {message_id} by user {current_user.id}")

    except HTTPException:
        raise
    except ConflictError as e:
        logger.warning(f"Conflict deleting message {message_id}: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except CharactersRAGDBError as e:
        logger.error(f"DB error deleting message {message_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting message {message_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting message"
        )


@router.get("/chats/{chat_id}/messages/search", response_model=MessageListResponse,
            summary="Search messages in a chat", tags=["Messages"])
async def search_messages(
    chat_id: str = Path(..., description="Chat session ID"),
    query: str = Query(..., description="Search query", min_length=1),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user)
):
    """
    Search for messages in a chat session.

    Args:
        chat_id: Chat session ID
        query: Search query string
        limit: Maximum number of results
        db: Database instance
        current_user: Authenticated user

    Returns:
        List of matching messages

    Raises:
        HTTPException: 404 if chat not found, 403 if unauthorized
    """
    try:
        # Verify conversation access
        conversation = _verify_conversation_access(db, chat_id, current_user.id)

        # Resolve character/user names for placeholder-aware search
        character_id = conversation.get('character_id')
        character = db.get_character_card_by_id(character_id) if character_id else None
        character_name = character.get('name', 'Assistant') if character else 'Assistant'
        user_name = conversation.get('user_name', 'User')
        # Search messages with placeholder replacement
        results = find_messages_in_conversation(
            db,
            chat_id,
            query,
            character_name_for_placeholders=character_name,
            user_name_for_placeholders=user_name,
            limit=limit,
        )

        if not results:
            results = []

        return MessageListResponse(
            messages=[_convert_db_message_to_response(msg) for msg in results],
            total=len(results),
            limit=limit,
            offset=0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching messages in chat {chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while searching messages"
        )


#
# End of character_messages.py
######################################################################################################################
