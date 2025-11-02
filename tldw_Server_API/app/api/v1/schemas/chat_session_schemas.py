# chat_session_schemas.py
"""
Pydantic schemas for character chat sessions and messages.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID


# ========================================================================
# Chat Session Schemas
# ========================================================================

class ChatSessionCreate(BaseModel):
    """Schema for creating a new chat session."""
    character_id: int = Field(..., description="ID of the character for this chat", gt=0)
    title: Optional[str] = Field(None, description="Optional title for the chat session")
    parent_conversation_id: Optional[str] = Field(None, description="Parent conversation ID for forked chats")

    model_config = {"json_schema_extra": {
        "example": {
            "character_id": 1,
            "title": "Evening Chat with Assistant"
        }
    }}


class ChatSessionUpdate(BaseModel):
    """Schema for updating a chat session."""
    title: Optional[str] = Field(None, description="New title for the chat")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating for the conversation")

    model_config = {"json_schema_extra": {
        "example": {
            "title": "Updated Chat Title",
            "rating": 5
        }
    }}


class ChatSessionResponse(BaseModel):
    """Schema for chat session responses."""
    id: str = Field(..., description="UUID of the chat session")
    character_id: int = Field(..., description="ID of the associated character")
    title: Optional[str] = Field(None, description="Chat session title")
    rating: Optional[int] = Field(None, description="User rating of the conversation")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    message_count: Optional[int] = Field(0, description="Number of messages in the chat")
    version: int = Field(1, description="Version number for optimistic locking")

    model_config = {"from_attributes": True}


class ChatSessionListResponse(BaseModel):
    """Schema for listing chat sessions."""
    chats: List[ChatSessionResponse] = Field(..., description="List of chat sessions")
    total: int = Field(..., description="Total number of chats")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Offset for pagination")


# ========================================================================
# Message Schemas
# ========================================================================

class MessageCreate(BaseModel):
    """Schema for creating a new message."""
    role: Literal["user", "assistant", "system"] = Field(..., description="Message sender role")
    content: Optional[str] = Field(
        None,
        description="Message content (required unless image_base64 is provided)",
        min_length=1,
    )
    parent_message_id: Optional[str] = Field(None, description="Parent message ID for branching")
    image_base64: Optional[str] = Field(None, description="Optional base64 encoded image")

    model_config = {"json_schema_extra": {
        "example": {
            "role": "user",
            "content": "Hello, how are you today?"
        }
    }}

    @model_validator(mode="after")
    def _validate_content_or_image(self) -> "MessageCreate":
        """Ensure at least one of content or image_base64 is provided.

        Allows image-only messages and enforces content non-empty when provided.
        """
        content_ok = bool(self.content and str(self.content).strip())
        image_ok = bool(self.image_base64 and str(self.image_base64).strip())
        if not content_ok and not image_ok:
            raise ValueError("Provide either non-empty content or image_base64.")
        return self


class MessageUpdate(BaseModel):
    """Schema for updating a message."""
    content: str = Field(..., description="New message content", min_length=1)

    model_config = {"json_schema_extra": {
        "example": {
            "content": "Updated message content"
        }
    }}


class MessageResponse(BaseModel):
    """Schema for message responses."""
    id: str = Field(..., description="UUID of the message")
    conversation_id: str = Field(..., description="ID of the parent conversation")
    parent_message_id: Optional[str] = Field(None, description="ID of parent message")
    sender: str = Field(..., description="Message sender (user/assistant/system)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    ranking: Optional[int] = Field(None, description="Message ranking/rating")
    has_image: bool = Field(False, description="Whether message has an attached image")
    version: int = Field(1, description="Version number for optimistic locking")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls associated with this message (if any)")
    metadata_extra: Optional[Dict[str, Any]] = Field(None, description="Additional stored metadata for this message (if requested)")

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    """Schema for listing messages."""
    messages: List[MessageResponse] = Field(..., description="List of messages")
    total: int = Field(..., description="Total number of messages")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Offset for pagination")


# ========================================================================
# Chat Completion Schemas
# ========================================================================

class CharacterChatCompletionV1Request(BaseModel):
    """Schema for character-specific chat completion requests."""
    message: str = Field(..., description="User message to respond to", min_length=1)
    max_tokens: Optional[int] = Field(500, ge=1, le=4096, description="Maximum tokens in response")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Response randomness")
    stream: bool = Field(False, description="Enable streaming response")
    include_history: bool = Field(True, description="Include conversation history")
    history_limit: Optional[int] = Field(20, ge=0, le=100, description="Number of history messages to include")

    model_config = {"json_schema_extra": {
        "example": {
            "message": "What's your favorite color?",
            "max_tokens": 150,
            "temperature": 0.8,
            "stream": False
        }
    }}


class CharacterChatCompletionV1Response(BaseModel):
    """Schema for chat completion responses."""
    response: str = Field(..., description="AI response")
    message_id: str = Field(..., description="ID of the created message")
    usage: Optional[Dict[str, int]] = Field(None, description="Token usage statistics")

    model_config = {"json_schema_extra": {
        "example": {
            "response": "My favorite color is blue, like the vast ocean!",
            "message_id": "550e8400-e29b-41d4-a716-446655440000",
            "usage": {
                "prompt_tokens": 45,
                "completion_tokens": 12,
                "total_tokens": 57
            }
        }
    }}


# ========================================================================
# Character Chat v2 + Prep Schemas (centralized)
# ========================================================================

class CharacterChatCompletionPrepRequest(BaseModel):
    """Prepare chat messages for use with the main Chat API.

    Controls pagination and optional user message appending for preparation.
    """
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


class CharacterChatCompletionV2Request(BaseModel):
    """Character Chat completion (v2) - builds context and calls a provider.

    Includes provider/model controls, optional appended user message,
    persistence toggle, and streaming control.
    """
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


class CharacterChatCompletionV2Response(BaseModel):
    chat_id: str
    character_id: int
    provider: str
    model: Optional[str] = None
    saved: bool = False
    user_message_id: Optional[str] = None
    assistant_message_id: Optional[str] = None
    assistant_content: str


# New: Persist streamed assistant content after SSE
class CharacterChatStreamPersistRequest(BaseModel):
    """Persist assistant content produced via streaming.

    Use after a streamed completion where the assistant content was not persisted.
    """
    assistant_content: str = Field(..., min_length=1, description="Assistant text to persist")
    user_message_id: Optional[str] = Field(None, description="Optional parent user message id to link threading")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Optional tool_calls metadata to store")
    usage: Optional[Dict[str, int]] = Field(None, description="Optional token usage stats: prompt_tokens, completion_tokens, total_tokens")
    chat_rating: Optional[int] = Field(None, ge=1, le=5, description="Optional conversation rating to set (1-5)")
    ranking: Optional[int] = Field(None, description="Optional ranking for the assistant message")


class CharacterChatStreamPersistResponse(BaseModel):
    chat_id: str
    assistant_message_id: Optional[str] = None
    saved: bool = False


# ========================================================================
# Export Schemas
# ========================================================================

class ChatExportFormat(BaseModel):
    """Schema for chat export format options."""
    format: Literal["json", "markdown", "text"] = Field("json", description="Export format")
    include_metadata: bool = Field(True, description="Include chat metadata")
    include_character: bool = Field(True, description="Include character information")


class ChatHistoryExport(BaseModel):
    """Schema for exported chat history."""
    chat_id: str = Field(..., description="Chat session ID")
    character_name: str = Field(..., description="Character name")
    character_id: int = Field(..., description="Character ID")
    title: Optional[str] = Field(None, description="Chat title")
    created_at: datetime = Field(..., description="Creation timestamp")
    messages: List[Dict[str, Any]] = Field(..., description="Message history")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    model_config = {"json_schema_extra": {
        "example": {
            "chat_id": "550e8400-e29b-41d4-a716-446655440000",
            "character_name": "Assistant",
            "character_id": 1,
            "title": "Evening Chat",
            "created_at": "2024-01-15T20:30:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello!",
                    "timestamp": "2024-01-15T20:30:00Z"
                },
                {
                    "role": "assistant",
                    "content": "Hello! How can I help you?",
                    "timestamp": "2024-01-15T20:30:05Z"
                }
            ]
        }
    }}


# ========================================================================
# Error Response Schemas
# ========================================================================

class ChatErrorResponse(BaseModel):
    """Schema for chat-related error responses."""
    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Detailed error message")
    chat_id: Optional[str] = Field(None, description="Related chat ID if applicable")
    message_id: Optional[str] = Field(None, description="Related message ID if applicable")

    model_config = {"json_schema_extra": {
        "example": {
            "error": "ChatNotFound",
            "detail": "Chat session with ID '550e8400-e29b-41d4-a716-446655440000' not found",
            "chat_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    }}


# ========================================================================
# Filter Schemas
# ========================================================================

class CharacterTagFilter(BaseModel):
    """Schema for filtering characters by tags."""
    tags: List[str] = Field(..., description="Tags to filter by", min_length=1)
    match_all: bool = Field(False, description="Require all tags to match (AND) vs any tag (OR)")

    model_config = {"json_schema_extra": {
        "example": {
            "tags": ["fantasy", "wizard"],
            "match_all": False
        }
    }}


#
# End of chat_session_schemas.py
######################################################################################################################
