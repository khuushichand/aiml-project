from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Union

from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Agent Types
# -----------------------------------------------------------------------------


# Agent type identifiers are user-configurable strings.
ACPAgentType = str


class ACPAgentInfo(BaseModel):
    """Information about an available agent."""
    type: ACPAgentType = Field(..., description="Agent type identifier")
    name: str = Field(..., description="Human-readable agent name")
    description: str = Field(default="", description="Agent description")
    is_configured: bool = Field(
        default=False, description="Whether the agent is properly configured"
    )
    requires_api_key: str | None = Field(
        default=None,
        description="Name of required API key if not configured (e.g., 'ANTHROPIC_API_KEY')",
    )


class ACPAgentListResponse(BaseModel):
    """Response for listing available agents."""
    agents: list[ACPAgentInfo] = Field(default_factory=list)
    default_agent: ACPAgentType = Field(default="custom")


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
    url: str | None = Field(default=None, description="WebSocket URL (for websocket type)")
    command: str | None = Field(default=None, description="Command to execute (for stdio type)")
    args: list[str] | None = Field(default=None, description="Command arguments (for stdio type)")
    env: dict[str, str] | None = Field(default=None, description="Environment variables")


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
    agent_capabilities: dict[str, Any] | None = None


class ACPWSUpdateMessage(BaseModel):
    """Streamed update from the agent session."""
    type: Literal["update"] = "update"
    session_id: str
    update_type: str = Field(..., description="Type of update (e.g., 'text', 'tool_call', 'tool_result')")
    data: dict[str, Any] = Field(default_factory=dict)


class ACPWSPermissionRequestMessage(BaseModel):
    """Request for permission to execute a tool."""
    type: Literal["permission_request"] = "permission_request"
    request_id: str = Field(..., description="Unique ID for this permission request")
    session_id: str
    tool_name: str
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    tier: ACPPermissionTier = ACPPermissionTier.INDIVIDUAL
    timeout_seconds: int = Field(default=300, description="Seconds until auto-cancel if no response")


class ACPWSErrorMessage(BaseModel):
    """Error message from the server."""
    type: Literal["error"] = "error"
    code: str
    message: str
    session_id: str | None = None
    data: dict[str, Any] | None = None


class ACPWSPromptCompleteMessage(BaseModel):
    """Sent when a prompt execution completes."""
    type: Literal["prompt_complete"] = "prompt_complete"
    session_id: str
    stop_reason: str | None = None
    raw_result: dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# WebSocket Message Types (Client → Server)
# -----------------------------------------------------------------------------


class ACPWSPermissionResponseMessage(BaseModel):
    """Response to a permission request."""
    type: Literal["permission_response"] = "permission_response"
    request_id: str
    approved: bool
    batch_approve_tier: ACPPermissionTier | None = Field(
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
    prompt: list[dict[str, Any]]


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
    name: str | None = Field(
        default=None,
        description="Optional session name. Auto-generated from cwd if not provided.",
    )
    agent_type: ACPAgentType | None = Field(
        default=None, description="Type of agent to use"
    )
    tags: list[str] | None = Field(
        default=None, description="Optional tags for organizing sessions"
    )
    mcp_servers: list[ACPMCPServerConfig] | None = Field(
        default=None, description="Optional MCP server configurations"
    )
    persona_id: str | None = Field(
        default=None,
        description="Optional persona identifier bound to sandbox tenancy metadata",
    )
    workspace_id: str | None = Field(
        default=None,
        description="Optional workspace identifier bound to sandbox tenancy metadata",
    )
    workspace_group_id: str | None = Field(
        default=None,
        description="Optional workspace group identifier bound to sandbox tenancy metadata",
    )
    scope_snapshot_id: str | None = Field(
        default=None,
        description="Optional materialized scope snapshot identifier for sandbox tenancy metadata",
    )


class ACPSessionNewResponse(BaseModel):
    """Response when a new ACP session is created."""
    session_id: str
    name: str = Field(..., description="Session name (user-provided or auto-generated)")
    agent_type: ACPAgentType = Field(..., description="Type of agent used")
    agent_capabilities: dict[str, Any] | None = None
    sandbox_session_id: str | None = Field(default=None, description="Sandbox session backing this ACP session")
    sandbox_run_id: str | None = Field(default=None, description="Sandbox run backing this ACP session")
    ssh_ws_url: str | None = Field(default=None, description="WebSocket URL for browser-based SSH")
    ssh_user: str | None = Field(default=None, description="SSH username for this session")
    persona_id: str | None = Field(default=None, description="Persona identifier bound to this ACP session")
    workspace_id: str | None = Field(default=None, description="Workspace identifier bound to this ACP session")
    workspace_group_id: str | None = Field(
        default=None, description="Workspace group identifier bound to this ACP session"
    )
    scope_snapshot_id: str | None = Field(
        default=None, description="Scope snapshot identifier bound to this ACP session"
    )


class ACPSessionPromptRequest(BaseModel):
    session_id: str
    prompt: list[dict[str, Any]]


class ACPSessionPromptResponse(BaseModel):
    stop_reason: str | None = None
    raw_result: dict[str, Any]
    usage: ACPTokenUsage | None = Field(default=None, description="Token usage for this prompt turn")


class ACPSessionCancelRequest(BaseModel):
    session_id: str


class ACPSessionCloseRequest(BaseModel):
    session_id: str


class ACPSessionUpdatesResponse(BaseModel):
    updates: list[dict[str, Any]]


# -----------------------------------------------------------------------------
# Token Usage Tracking
# -----------------------------------------------------------------------------


class ACPTokenUsage(BaseModel):
    """Token usage counts for an ACP session."""
    prompt_tokens: int = Field(default=0, description="Total prompt/input tokens consumed")
    completion_tokens: int = Field(default=0, description="Total completion/output tokens consumed")
    total_tokens: int = Field(default=0, description="Total tokens consumed (prompt + completion)")


# -----------------------------------------------------------------------------
# Session Listing & Detail
# -----------------------------------------------------------------------------


class ACPSessionStatus(str, Enum):
    """Status of an ACP session."""
    ACTIVE = "active"
    CLOSED = "closed"
    ERROR = "error"


class ACPSessionInfo(BaseModel):
    """Summary information about an ACP session."""
    session_id: str = Field(..., description="Unique session identifier")
    user_id: int = Field(..., description="ID of the user who owns this session")
    agent_type: str = Field(default="custom", description="Type of agent used")
    name: str = Field(default="", description="Session name")
    status: ACPSessionStatus = Field(default=ACPSessionStatus.ACTIVE, description="Current session status")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    last_activity_at: str | None = Field(default=None, description="ISO 8601 timestamp of last activity")
    message_count: int = Field(default=0, description="Number of messages exchanged")
    usage: ACPTokenUsage = Field(default_factory=ACPTokenUsage, description="Token usage for this session")
    tags: list[str] = Field(default_factory=list, description="Tags for organizing sessions")
    has_websocket: bool = Field(default=False, description="Whether a WebSocket is connected")
    persona_id: str | None = Field(default=None, description="Persona identifier bound to this ACP session")
    workspace_id: str | None = Field(default=None, description="Workspace identifier bound to this ACP session")
    workspace_group_id: str | None = Field(
        default=None, description="Workspace group identifier bound to this ACP session"
    )
    scope_snapshot_id: str | None = Field(
        default=None, description="Scope snapshot identifier bound to this ACP session"
    )
    forked_from: str | None = Field(default=None, description="Source session ID when this session was forked")


class ACPSessionListResponse(BaseModel):
    """Response for listing ACP sessions."""
    sessions: list[ACPSessionInfo] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of sessions matching filters")


class ACPSessionDetailResponse(ACPSessionInfo):
    """Detailed information about an ACP session, including message history."""
    messages: list[dict[str, Any]] = Field(default_factory=list, description="Message history (if available)")
    cwd: str | None = Field(default=None, description="Working directory for this session")
    fork_lineage: list[str] = Field(default_factory=list, description="Ancestor session IDs from oldest to most recent parent")


class ACPSessionForkRequest(BaseModel):
    """Request to fork an ACP session from a specific message index."""
    message_index: int = Field(
        ...,
        ge=0,
        description="Index of the last message to include in the forked session (0-based)",
    )
    name: str | None = Field(default=None, description="Optional name for the forked session")


class ACPSessionForkResponse(BaseModel):
    """Response when a session is forked."""
    session_id: str = Field(..., description="New forked session ID")
    name: str = Field(..., description="Name of the forked session")
    forked_from: str = Field(..., description="ID of the source session")
    message_count: int = Field(default=0, description="Number of messages copied to the fork")


class ACPSessionUsageResponse(BaseModel):
    """Usage details for a specific ACP session."""
    session_id: str
    user_id: int
    agent_type: str = "custom"
    usage: ACPTokenUsage = Field(default_factory=ACPTokenUsage)
    message_count: int = 0
    created_at: str = ""
    last_activity_at: str | None = None


# -----------------------------------------------------------------------------
# Agent Configuration (Admin-managed)
# -----------------------------------------------------------------------------


class ACPAgentConfigCreate(BaseModel):
    """Request to create a custom agent configuration."""
    type: str = Field(..., description="Unique agent type identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(default="", description="Agent description")
    system_prompt: str | None = Field(default=None, description="System prompt for the agent")
    allowed_tools: list[str] | None = Field(default=None, description="Tools this agent is allowed to use (null = all)")
    denied_tools: list[str] | None = Field(default=None, description="Tools this agent is denied from using")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Agent parameters (temperature, topP, model, max_tokens, etc.)",
    )
    requires_api_key: str | None = Field(default=None, description="Env var name for required API key")
    org_id: int | None = Field(default=None, description="Restrict to specific organization")
    team_id: int | None = Field(default=None, description="Restrict to specific team")
    enabled: bool = Field(default=True, description="Whether the agent is enabled")


class ACPAgentConfigResponse(ACPAgentConfigCreate):
    """Agent configuration as stored."""
    id: int = Field(..., description="Config ID")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    updated_at: str | None = Field(default=None, description="ISO 8601 last update timestamp")
    is_configured: bool = Field(default=True, description="Whether required keys are present")


class ACPAgentConfigListResponse(BaseModel):
    """Response for listing agent configurations."""
    agents: list[ACPAgentConfigResponse] = Field(default_factory=list)
    total: int = Field(default=0)


# -----------------------------------------------------------------------------
# Permission Policy (Admin-managed)
# -----------------------------------------------------------------------------


class ACPPermissionPolicyRule(BaseModel):
    """A single permission policy rule."""
    tool_pattern: str = Field(..., description="Tool name or glob pattern (e.g., 'file_*', 'bash')")
    tier: ACPPermissionTier = Field(..., description="Permission tier to assign")


class ACPPermissionPolicyCreate(BaseModel):
    """Request to create/update a permission policy."""
    name: str = Field(..., description="Policy name")
    description: str = Field(default="", description="Policy description")
    rules: list[ACPPermissionPolicyRule] = Field(default_factory=list)
    org_id: int | None = Field(default=None, description="Restrict to specific organization")
    team_id: int | None = Field(default=None, description="Restrict to specific team")
    priority: int = Field(default=0, description="Higher priority policies take precedence")


class ACPPermissionPolicyResponse(ACPPermissionPolicyCreate):
    """Permission policy as stored."""
    id: int = Field(..., description="Policy ID")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    updated_at: str | None = Field(default=None)


class ACPPermissionPolicyListResponse(BaseModel):
    """Response for listing permission policies."""
    policies: list[ACPPermissionPolicyResponse] = Field(default_factory=list)
    total: int = Field(default=0)


# -----------------------------------------------------------------------------
# Health Check Response
# -----------------------------------------------------------------------------


class ACPHealthResponse(BaseModel):
    """ACP dependency chain health check response."""
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    runner: dict[str, Any] = Field(default_factory=dict, description="Runner binary status")
    agents: list[dict[str, Any]] = Field(default_factory=list, description="Downstream agent statuses")
    runner_probe: dict[str, Any] = Field(default_factory=dict, description="Runner process probe result")
    overall: str = Field(default="unknown", description="ok | degraded | unavailable")
    message: str | None = Field(default=None, description="Human-readable status message")


# -----------------------------------------------------------------------------
# Structured Error Responses
# -----------------------------------------------------------------------------


class ACPErrorSuggestion(BaseModel):
    """A suggestion for resolving an error."""
    action: str = Field(..., description="Suggested action to take")
    description: str | None = Field(default=None, description="More details about the action")


class ACPErrorResponse(BaseModel):
    """Structured error response with suggestions."""
    code: str = Field(..., description="Error code for programmatic handling")
    message: str = Field(..., description="Human-readable error message")
    suggestions: list[ACPErrorSuggestion] = Field(
        default_factory=list, description="Suggestions for resolving the error"
    )
    data: dict[str, Any] | None = Field(
        default=None, description="Additional error context"
    )
