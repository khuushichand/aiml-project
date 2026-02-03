# VoiceAssistant/schemas.py
# Internal data models for the Voice Assistant module
#
#######################################################################################################################
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Types of actions that can be triggered by voice commands."""
    MCP_TOOL = "mcp_tool"
    WORKFLOW = "workflow"
    CUSTOM = "custom"
    LLM_CHAT = "llm_chat"


class VoiceCommand(BaseModel):
    """
    A registered voice command that maps phrases to actions.

    Voice commands define trigger phrases and the action to execute when matched.
    """
    id: str = Field(..., description="Unique identifier for the command")
    user_id: int = Field(..., description="Owner user ID")
    name: str = Field(..., description="Human-readable name for the command")
    phrases: list[str] = Field(..., description="Trigger phrases that activate this command")
    action_type: ActionType = Field(..., description="Type of action to execute")
    action_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration for the action (tool name, workflow ID, etc.)"
    )
    priority: int = Field(default=0, description="Priority for disambiguation (higher = prefer)")
    enabled: bool = Field(default=True, description="Whether the command is active")
    requires_confirmation: bool = Field(
        default=False,
        description="Whether to ask for confirmation before executing"
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional description of what the command does"
    )
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")


class VoiceIntent(BaseModel):
    """
    Represents a parsed intent from voice input.

    Contains the detected intent type, extracted entities, and confidence score.
    """
    command_id: Optional[str] = Field(
        default=None,
        description="Matched command ID (if keyword/pattern match)"
    )
    action_type: ActionType = Field(..., description="Determined action type")
    action_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Action configuration with extracted parameters"
    )
    entities: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted entities from the utterance"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the intent match"
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether confirmation is needed before execution"
    )
    raw_text: str = Field(..., description="Original transcribed text")


class ParsedIntent(BaseModel):
    """
    Result of intent parsing including match method and alternatives.
    """
    intent: VoiceIntent = Field(..., description="Primary matched intent")
    match_method: str = Field(
        default="unknown",
        description="How the intent was matched: keyword, pattern, llm, or default"
    )
    alternatives: list[VoiceIntent] = Field(
        default_factory=list,
        description="Alternative intent matches if ambiguous"
    )
    processing_time_ms: float = Field(
        default=0.0,
        description="Time taken to parse the intent in milliseconds"
    )


class VoiceSessionState(str, Enum):
    """States a voice session can be in."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    ERROR = "error"


class VoiceSessionContext(BaseModel):
    """
    Maintains context for a voice assistant session.

    Tracks conversation history, pending confirmations, and session state.
    """
    session_id: str = Field(..., description="Unique session identifier")
    user_id: int = Field(..., description="User ID for the session")
    state: VoiceSessionState = Field(
        default=VoiceSessionState.IDLE,
        description="Current session state"
    )
    conversation_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent conversation turns for context"
    )
    pending_intent: Optional[VoiceIntent] = Field(
        default=None,
        description="Intent awaiting confirmation"
    )
    last_action_result: Optional[dict[str, Any]] = Field(
        default=None,
        description="Result of the last executed action"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Session-specific metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Session creation time"
    )
    last_activity: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last activity timestamp"
    )

    def add_turn(self, role: str, content: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Add a conversation turn to history."""
        turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if metadata:
            turn["metadata"] = metadata
        self.conversation_history.append(turn)
        self.last_activity = datetime.utcnow()
        # Keep last 20 turns
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    def get_context_messages(self, max_turns: int = 10) -> list[dict[str, str]]:
        """Get recent conversation history for LLM context."""
        recent = self.conversation_history[-max_turns:]
        return [{"role": t["role"], "content": t["content"]} for t in recent]


class ActionResult(BaseModel):
    """Result of executing a voice command action."""
    success: bool = Field(..., description="Whether the action succeeded")
    action_type: ActionType = Field(..., description="Type of action that was executed")
    result_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Data returned by the action"
    )
    response_text: str = Field(
        ...,
        description="Text response to speak to the user"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if action failed"
    )
    execution_time_ms: float = Field(
        default=0.0,
        description="Time taken to execute the action"
    )


class BuiltinCommand(str, Enum):
    """Built-in voice commands that are always available."""
    STOP = "stop"
    CANCEL = "cancel"
    HELP = "help"
    REPEAT = "repeat"
    YES = "yes"
    NO = "no"


#
# End of VoiceAssistant/schemas.py
#######################################################################################################################
