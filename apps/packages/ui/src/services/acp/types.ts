/**
 * ACP (Agent Client Protocol) TypeScript Types
 *
 * These types mirror the backend Pydantic schemas for ACP WebSocket communication.
 */

// -----------------------------------------------------------------------------
// Agent Types
// -----------------------------------------------------------------------------

export type ACPAgentType = string

export interface ACPAgentInfo {
  type: ACPAgentType
  name: string
  description: string
  is_configured: boolean
  requires_api_key?: string | null
}

export interface ACPAgentListResponse {
  agents: ACPAgentInfo[]
  default_agent: ACPAgentType
}

// -----------------------------------------------------------------------------
// MCP Server Configuration
// -----------------------------------------------------------------------------

export type ACPMCPServerType = "websocket" | "stdio"

export interface ACPMCPServerConfig {
  name: string
  type: ACPMCPServerType
  url?: string
  command?: string
  args?: string[]
  env?: Record<string, string>
}

// -----------------------------------------------------------------------------
// Permission Tiers
// -----------------------------------------------------------------------------

export type ACPPermissionTier = "auto" | "batch" | "individual"

// -----------------------------------------------------------------------------
// Session State
// -----------------------------------------------------------------------------

export type ACPSessionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "running"
  | "waiting_permission"
  | "error"

// -----------------------------------------------------------------------------
// WebSocket Message Types (Server → Client)
// -----------------------------------------------------------------------------

export interface ACPWSConnectedMessage {
  type: "connected"
  session_id: string
  agent_capabilities?: Record<string, unknown>
}

export interface ACPWSUpdateMessage {
  type: "update"
  session_id: string
  update_type: string
  data: Record<string, unknown>
}

export interface ACPWSPermissionRequestMessage {
  type: "permission_request"
  request_id: string
  session_id: string
  tool_name: string
  tool_arguments: Record<string, unknown>
  tier: ACPPermissionTier
  timeout_seconds: number
}

export interface ACPWSErrorMessage {
  type: "error"
  code: string
  message: string
  session_id?: string
  data?: Record<string, unknown>
}

export interface ACPWSPromptCompleteMessage {
  type: "prompt_complete"
  session_id: string
  stop_reason?: string
  raw_result: Record<string, unknown>
}

export interface ACPWSDoneMessage {
  type: "done"
}

export type ACPWSServerMessage =
  | ACPWSConnectedMessage
  | ACPWSUpdateMessage
  | ACPWSPermissionRequestMessage
  | ACPWSErrorMessage
  | ACPWSPromptCompleteMessage
  | ACPWSDoneMessage

// -----------------------------------------------------------------------------
// WebSocket Message Types (Client → Server)
// -----------------------------------------------------------------------------

export interface ACPWSPermissionResponseMessage {
  type: "permission_response"
  request_id: string
  approved: boolean
  batch_approve_tier?: ACPPermissionTier
}

export interface ACPWSCancelMessage {
  type: "cancel"
  session_id: string
}

export interface ACPWSPromptMessage {
  type: "prompt"
  session_id: string
  prompt: Array<{
    role: "system" | "user" | "assistant"
    content: string
  }>
}

export type ACPWSClientMessage =
  | ACPWSPermissionResponseMessage
  | ACPWSCancelMessage
  | ACPWSPromptMessage

// -----------------------------------------------------------------------------
// REST API Types
// -----------------------------------------------------------------------------

export interface ACPSessionNewRequest {
  cwd: string
  name?: string
  agent_type?: ACPAgentType
  tags?: string[]
  mcp_servers?: ACPMCPServerConfig[]
}

export interface ACPSessionNewResponse {
  session_id: string
  name: string
  agent_type: ACPAgentType
  agent_capabilities?: Record<string, unknown>
  sandbox_session_id?: string | null
  sandbox_run_id?: string | null
  ssh_ws_url?: string | null
  ssh_user?: string | null
}

export interface ACPSessionPromptRequest {
  session_id: string
  prompt: Array<{
    role: "system" | "user" | "assistant"
    content: string
  }>
}

export interface ACPSessionPromptResponse {
  stop_reason?: string
  raw_result: Record<string, unknown>
}

// -----------------------------------------------------------------------------
// Session and Update Types
// -----------------------------------------------------------------------------

export interface ACPSession {
  id: string
  cwd: string
  name?: string
  forkParentSessionId?: string | null
  agentType?: ACPAgentType
  tags?: string[]
  mcpServers?: ACPMCPServerConfig[]
  state: ACPSessionState
  capabilities?: Record<string, unknown>
  sandboxSessionId?: string | null
  sandboxRunId?: string | null
  sshWsUrl?: string | null
  sshUser?: string | null
  updates: ACPUpdate[]
  pendingPermissions: ACPPendingPermission[]
  createdAt: Date
  updatedAt: Date
}

export interface ACPUpdate {
  timestamp: Date
  type: string
  data: Record<string, unknown>
}

export interface ACPPendingPermission {
  request_id: string
  tool_name: string
  tool_arguments: Record<string, unknown>
  tier: ACPPermissionTier
  timeout_seconds: number
  requestedAt: Date
}

// -----------------------------------------------------------------------------
// Agent Capabilities
// -----------------------------------------------------------------------------

export interface ACPAgentCapabilities {
  fs?: {
    readTextFile?: boolean
    writeTextFile?: boolean
  }
  terminal?: boolean
  tools?: string[]
}

// -----------------------------------------------------------------------------
// Callbacks for useACPSession hook
// -----------------------------------------------------------------------------

export interface ACPSessionCallbacks {
  onStateChange?: (state: ACPSessionState) => void
  onUpdate?: (update: ACPWSUpdateMessage) => void
  onPermissionRequest?: (request: ACPWSPermissionRequestMessage) => void
  onPromptComplete?: (result: ACPWSPromptCompleteMessage) => void
  onError?: (error: ACPWSErrorMessage) => void
  onConnected?: (message: ACPWSConnectedMessage) => void
  onDisconnected?: () => void
}

// -----------------------------------------------------------------------------
// Structured Error Types
// -----------------------------------------------------------------------------

export interface ACPErrorSuggestion {
  action: string
  description?: string
}

export interface ACPStructuredError {
  code: string
  message: string
  suggestions: ACPErrorSuggestion[]
  data?: Record<string, unknown>
}

// -----------------------------------------------------------------------------
// Session Creation Progress
// -----------------------------------------------------------------------------

export type ACPSessionCreationStep =
  | "idle"
  | "creating"
  | "starting_agent"
  | "connecting"
  | "ready"
  | "error"

export interface ACPSessionCreationState {
  step: ACPSessionCreationStep
  error?: ACPStructuredError
}
