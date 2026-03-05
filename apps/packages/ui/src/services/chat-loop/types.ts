export type ChatLoopEventName =
  | "run_started"
  | "llm_chunk"
  | "llm_complete"
  | "tool_proposed"
  | "approval_required"
  | "approval_resolved"
  | "tool_started"
  | "tool_finished"
  | "tool_failed"
  | "assistant_message_committed"
  | "run_complete"
  | "run_error"
  | "run_cancelled"

export interface ChatLoopEvent {
  run_id: string
  seq: number
  event: ChatLoopEventName
  data: Record<string, unknown>
  ts?: string
}

export interface ChatLoopPendingApproval {
  approvalId: string
  toolCallId?: string
  seq: number
}

export interface ChatLoopState {
  runId: string | null
  lastSeq: number
  status: "idle" | "running" | "complete" | "error" | "cancelled"
  assistantText: string
  pendingApprovals: ChatLoopPendingApproval[]
  inflightToolCallIds: string[]
  errorMessage: string | null
}

export interface ChatLoopStartRequest {
  messages: Array<Record<string, unknown>>
}

export interface ChatLoopStartResponse {
  run_id: string
}

export interface ChatLoopEventsResponse {
  run_id: string
  events: ChatLoopEvent[]
}
