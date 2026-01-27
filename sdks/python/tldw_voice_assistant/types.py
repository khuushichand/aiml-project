"""
Type definitions for tldw Voice Assistant SDK.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class WSMessageType(str, Enum):
    """WebSocket message types."""

    # Client -> Server
    AUTH = "auth"
    CONFIG = "config"
    AUDIO = "audio"
    COMMIT = "commit"
    CANCEL = "cancel"
    TEXT = "text"
    WORKFLOW_SUBSCRIBE = "workflow_subscribe"
    WORKFLOW_CANCEL = "workflow_cancel"

    # Server -> Client
    AUTH_OK = "auth_ok"
    AUTH_ERROR = "auth_error"
    CONFIG_ACK = "config_ack"
    TRANSCRIPTION = "transcription"
    INTENT = "intent"
    ACTION_START = "action_start"
    ACTION_RESULT = "action_result"
    TTS_CHUNK = "tts_chunk"
    TTS_END = "tts_end"
    ERROR = "error"
    STATE_CHANGE = "state_change"
    WORKFLOW_PROGRESS = "workflow_progress"
    WORKFLOW_COMPLETE = "workflow_complete"


class VoiceAssistantState(str, Enum):
    """Voice assistant session states."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    ERROR = "error"


class VoiceActionType(str, Enum):
    """Types of voice command actions."""

    MCP_TOOL = "mcp_tool"
    WORKFLOW = "workflow"
    CUSTOM = "custom"
    LLM_CHAT = "llm_chat"


@dataclass
class TranscriptionResult:
    """Result from speech-to-text transcription."""

    text: str
    is_final: bool = False
    confidence: Optional[float] = None


@dataclass
class IntentResult:
    """Parsed intent from voice command."""

    action_type: VoiceActionType
    command_name: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    requires_confirmation: bool = False


@dataclass
class ActionResult:
    """Result from executing a voice command action."""

    success: bool
    action_type: VoiceActionType
    response_text: str
    result_data: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0


@dataclass
class WorkflowProgress:
    """Progress update from a running workflow."""

    run_id: str
    event_type: str
    message: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class WorkflowComplete:
    """Completion notification for a workflow."""

    run_id: str
    status: str
    response_text: str
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class TTSChunk:
    """Audio chunk from TTS response."""

    data: bytes
    sequence: int
    format: str = "mp3"


@dataclass
class VoiceError:
    """Error from voice assistant."""

    error: str
    code: Optional[str] = None
    recoverable: bool = True
