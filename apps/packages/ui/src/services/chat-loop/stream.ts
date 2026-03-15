import type { ChatLoopEvent, ChatLoopEventName } from "@/services/chat-loop/types"

const CHAT_LOOP_EVENT_NAMES = new Set<ChatLoopEventName>([
  "run_started",
  "llm_chunk",
  "llm_complete",
  "tool_proposed",
  "approval_required",
  "approval_resolved",
  "tool_started",
  "tool_finished",
  "tool_failed",
  "assistant_message_committed",
  "run_complete",
  "run_error",
  "run_cancelled",
])

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value)

const asNonEmptyString = (value: unknown): string | null => {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

const asPositiveInt = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isInteger(value) && value > 0) {
    return value
  }
  if (typeof value === "string") {
    const parsed = Number(value)
    if (Number.isInteger(parsed) && parsed > 0) {
      return parsed
    }
  }
  return null
}

export function extractChatLoopEvent(chunk: unknown): ChatLoopEvent | null {
  if (!isRecord(chunk)) return null

  const eventNameRaw = asNonEmptyString(chunk.event)
  if (!eventNameRaw || !CHAT_LOOP_EVENT_NAMES.has(eventNameRaw as ChatLoopEventName)) {
    return null
  }

  const data = isRecord(chunk.data)
    ? (chunk.data as Record<string, unknown>)
    : {}

  const runId = asNonEmptyString(chunk.run_id) ?? asNonEmptyString(data.run_id)
  const seq = asPositiveInt(chunk.seq) ?? asPositiveInt(data.seq)

  if (!runId || !seq) return null

  const ts = asNonEmptyString(chunk.ts) ?? undefined
  return {
    run_id: runId,
    seq,
    event: eventNameRaw as ChatLoopEventName,
    data,
    ...(ts ? { ts } : {}),
  }
}
