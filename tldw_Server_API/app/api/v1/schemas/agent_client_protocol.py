from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Agent Types
# -----------------------------------------------------------------------------


class ACPAgentType(str, Enum):
    """Supported agent types for ACP sessions."""
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    OPENCODE = "opencode"
    CUSTOM = "custom"


class ACPAgentInfo(BaseModel):
    """Information about an available agent."""
    type: ACPAgentType = Field(..., description="Agent type identifier")
    name: str = Field(..., description="Human-readable agent name")
    description: str = Field(default="", description="Agent description")
    is_configured: bool = Field(
        default=False, description="Whether the agent is properly configured"
    )
    requires_api_key: Optional[str] = Field(
        default=None,
        description="Name of required API key if not configured (e.g., 'ANTHROPIC_API_KEY')",
    )


class ACPAgentListResponse(BaseModel):
    """Response for listing available agents."""
    agents: List[ACPAgentInfo] = Field(default_factory=list)
    default_agent: ACPAgentType = Field(default=ACPAgentType.CLAUDE_CODE)


# -----------------------------------------------------------------------------
# MCP Server Configuration
# -----------------------------------------------------------------------------


class ACPMCPServerType(str, Enum):
    """MCP server connection types."""
    WEBSOCKET = "websocket"
    STDIO = "stdio"


class ACPMCPServerConfig(BaseModel):
    """Configuration for an MCP server."""
    name: str = Field(..., description="Server identifier/name")
    type: ACPMCPServerType = Field(..., description="Connection type")
    url: Optional[str] = Field(default=None, description="WebSocket URL (for websocket type)")
    command: Optional[str] = Field(default=None, description="Command to execute (for stdio type)")
    args: Optional[List[str]] = Field(default=None, description="Command arguments (for stdio type)")
    env: Optional[Dict[str, str]] = Field(default=None, description="Environment variables")


# -----------------------------------------------------------------------------
# Permission Tiers
# -----------------------------------------------------------------------------


class ACPPermissionTier(str, Enum):
    """Permission tier for tool execution approval.

    - auto: Automatically approved (read-only operations)
    - batch: Can be approved in batches (write operations)
    - individual: Requires individual approval (destructive/execute operations)
    """
    AUTO = "auto"
    BATCH = "batch"
    INDIVIDUAL = "individual"


# -----------------------------------------------------------------------------
# WebSocket Message Types (Server → Client)
# -----------------------------------------------------------------------------


class ACPWSConnectedMessage(BaseModel):
    """Sent when WebSocket connection is established."""
    type: Literal["connected"] = "connected"
    session_id: str
    agent_capabilities: Optional[Dict[str, Any]] = None


class ACPWSUpdateMessage(BaseModel):
    """Streamed update from the agent session."""
    type: Literal["update"] = "update"
    session_id: str
    update_type: str = Field(..., description="Type of update (e.g., 'text', 'tool_call', 'tool_result')")
    data: Dict[str, Any] = Field(default_factory=dict)


class ACPWSPermissionRequestMessage(BaseModel):
    """Request for permission to execute a tool."""
    type: Literal["permission_request"] = "permission_request"
    request_id: str = Field(..., description="Unique ID for this permission request")
    session_id: str
    tool_name: str
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
    tier: ACPPermissionTier = ACPPermissionTier.INDIVIDUAL
    timeout_seconds: int = Field(default=300, description="Seconds until auto-cancel if no response")


class ACPWSErrorMessage(BaseModel):
    """Error message from the server."""
    type: Literal["error"] = "error"
    code: str
    message: str
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ACPWSPromptCompleteMessage(BaseModel):
    """Sent when a prompt execution completes."""
    type: Literal["prompt_complete"] = "prompt_complete"
    session_id: str
    stop_reason: Optional[str] = None
    raw_result: Dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# WebSocket Message Types (Client → Server)
# -----------------------------------------------------------------------------


class ACPWSPermissionResponseMessage(BaseModel):
    """Response to a permission request."""
    type: Literal["permission_response"] = "permission_response"
    request_id: str
    approved: bool
    batch_approve_tier: Optional[ACPPermissionTier] = Field(
        default=None,
        description="If set, auto-approve all future requests of this tier"
    )


class ACPWSCancelMessage(BaseModel):
    """Request to cancel the current operation."""
    type: Literal["cancel"] = "cancel"
    session_id: str


class ACPWSPromptMessage(BaseModel):
    """Send a prompt to the session via WebSocket."""
    type: Literal["prompt"] = "prompt"
    session_id: str
    prompt: List[Dict[str, Any]]


# -----------------------------------------------------------------------------
# Union types for message handling
# -----------------------------------------------------------------------------


ACPWSServerMessage = Union[
    ACPWSConnectedMessage,
    ACPWSUpdateMessage,
    ACPWSPermissionRequestMessage,
    ACPWSErrorMessage,
    ACPWSPromptCompleteMessage,
]

ACPWSClientMessage = Union[
    ACPWSPermissionResponseMessage,
    ACPWSCancelMessage,
    ACPWSPromptMessage,
]


# -----------------------------------------------------------------------------
# REST API Schemas
# -----------------------------------------------------------------------------


class ACPSessionNewRequest(BaseModel):
    """Request to create a new ACP session."""
    cwd: str = Field(..., description="Absolute working directory for the ACP session")
    name: Optional[str] = Field(
        default=None,
        description="Optional session name. Auto-generated from cwd if not provided.",
    )
    agent_type: ACPAgentType = Field(
        default=ACPAgentType.CLAUDE_CODE, description="Type of agent to use"
    )
    tags: Optional[List[str]] = Field(
        default=None, description="Optional tags for organizing sessions"
    )
    mcp_servers: Optional[List[ACPMCPServerConfig]] = Field(
        default=None, description="Optional MCP server configurations"
    )


class ACPSessionNewResponse(BaseModel):
    """Response when a new ACP session is created."""
    session_id: str
    name: str = Field(..., description="Session name (user-provided or auto-generated)")
    agent_type: ACPAgentType = Field(..., description="Type of agent used")
    agent_capabilities: Optional[Dict[str, Any]] = None


class ACPSessionPromptRequest(BaseModel):
    session_id: str
    prompt: List[Dict[str, Any]]


class ACPSessionPromptResponse(BaseModel):
    stop_reason: Optional[str] = None
    raw_result: Dict[str, Any]


class ACPSessionCancelRequest(BaseModel):
    session_id: str


class ACPSessionCloseRequest(BaseModel):
    session_id: str


class ACPSessionUpdatesResponse(BaseModel):
    updates: List[Dict[str, Any]]


# -----------------------------------------------------------------------------
# Structured Error Responses
# -----------------------------------------------------------------------------


class ACPErrorSuggestion(BaseModel):
    """A suggestion for resolving an error."""
    action: str = Field(..., description="Suggested action to take")
    description: Optional[str] = Field(default=None, description="More details about the action")


class ACPErrorResponse(BaseModel):
    """Structured error response with suggestions."""
    code: str = Field(..., description="Error code for programmatic handling")
    message: str = Field(..., description="Human-readable error message")
    suggestions: List[ACPErrorSuggestion] = Field(
        default_factory=list, description="Suggestions for resolving the error"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error context"
    )
