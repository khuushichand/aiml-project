import type { ChatLoopEvent, ChatLoopState } from "@/services/chat-loop/types"

export function createInitialChatLoopState(): ChatLoopState {
  return {
    runId: null,
    lastSeq: 0,
    status: "idle",
    assistantText: "",
    pendingApprovals: [],
    inflightToolCallIds: [],
    errorMessage: null,
  }
}

function normalizeToolCallId(value: unknown): string | null {
  if (typeof value !== "string") {
    return null
  }
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

function normalizeApprovalId(value: unknown): string | null {
  if (typeof value !== "string") {
    return null
  }
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

export function reduceLoopEvent(state: ChatLoopState, event: ChatLoopEvent): ChatLoopState {
  const isNewRun = Boolean(event.run_id) && event.run_id !== state.runId
  const next: ChatLoopState = {
    ...state,
    runId: event.run_id || state.runId,
    lastSeq: Math.max(state.lastSeq, event.seq || 0),
  }

  switch (event.event) {
    case "run_started":
      if (isNewRun) {
        next.assistantText = ""
        next.pendingApprovals = []
        next.inflightToolCallIds = []
      }
      next.status = "running"
      next.errorMessage = null
      return next
    case "llm_chunk": {
      const chunkText = String(event.data?.text ?? event.data?.content ?? "")
      next.assistantText = `${state.assistantText}${chunkText}`
      return next
    }
    case "approval_required": {
      const approvalId = normalizeApprovalId(event.data?.approval_id)
      if (!approvalId) {
        return next
      }
      const toolCallId = normalizeToolCallId(event.data?.tool_call_id) ?? undefined
      const alreadyExists = state.pendingApprovals.some((item) => item.approvalId === approvalId)
      if (alreadyExists) {
        return next
      }
      next.pendingApprovals = [
        ...state.pendingApprovals,
        {
          approvalId,
          toolCallId,
          seq: event.seq,
        },
      ]
      return next
    }
    case "approval_resolved": {
      const approvalId = normalizeApprovalId(event.data?.approval_id)
      if (!approvalId) {
        return next
      }
      next.pendingApprovals = state.pendingApprovals.filter((item) => item.approvalId !== approvalId)
      return next
    }
    case "tool_started": {
      const toolCallId = normalizeToolCallId(event.data?.tool_call_id)
      if (!toolCallId) {
        return next
      }
      if (!state.inflightToolCallIds.includes(toolCallId)) {
        next.inflightToolCallIds = [...state.inflightToolCallIds, toolCallId]
      }
      return next
    }
    case "tool_finished":
    case "tool_failed": {
      const toolCallId = normalizeToolCallId(event.data?.tool_call_id)
      if (!toolCallId) {
        return next
      }
      next.inflightToolCallIds = state.inflightToolCallIds.filter((id) => id !== toolCallId)
      return next
    }
    case "run_cancelled":
      next.pendingApprovals = []
      next.inflightToolCallIds = []
      next.status = "cancelled"
      return next
    case "run_error":
      next.inflightToolCallIds = []
      next.status = "error"
      next.errorMessage = String(event.data?.error ?? "Chat loop failed")
      return next
    case "run_complete":
      next.pendingApprovals = []
      next.inflightToolCallIds = []
      next.status = "complete"
      return next
    default:
      return next
  }
}
