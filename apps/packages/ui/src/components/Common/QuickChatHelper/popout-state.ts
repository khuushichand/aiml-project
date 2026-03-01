import type {
  QuickChatAssistantMode,
  QuickChatMessage
} from "@/store/quick-chat"
import { normalizeQuickChatRoutePath } from "./workflow-guides"

type QuickChatPopoutStateInput = {
  messages: QuickChatMessage[]
  modelOverride: string | null
  assistantMode: QuickChatAssistantMode
}

export type QuickChatPopoutState = QuickChatPopoutStateInput & {
  sourceRoute: string | null
}

const isValidQuickChatMessage = (value: unknown): value is QuickChatMessage => {
  if (!value || typeof value !== "object") return false
  if (
    !("id" in value) ||
    !("role" in value) ||
    !("content" in value) ||
    !("timestamp" in value)
  ) {
    return false
  }
  const candidate = value as {
    id: unknown
    role: unknown
    content: unknown
    timestamp: unknown
  }
  return (
    typeof candidate.id === "string" &&
    (candidate.role === "user" || candidate.role === "assistant") &&
    typeof candidate.content === "string" &&
    typeof candidate.timestamp === "number"
  )
}

const normalizeAssistantMode = (value: unknown): QuickChatAssistantMode =>
  value === "docs_rag" || value === "browse_guides" ? value : "chat"

const normalizeSourceRoute = (value: unknown): string | null =>
  typeof value === "string" ? normalizeQuickChatRoutePath(value) : null

export const buildQuickChatPopoutState = (
  state: QuickChatPopoutStateInput,
  sourceRoute?: string | null
): QuickChatPopoutState => ({
  ...state,
  sourceRoute: normalizeSourceRoute(sourceRoute)
})

export const parseQuickChatPopoutState = (
  value: unknown
): QuickChatPopoutState | null => {
  if (!value || typeof value !== "object") return null
  const candidate = value as Record<string, unknown>
  const rawMessages = candidate.messages
  if (!Array.isArray(rawMessages)) return null

  const messages = rawMessages.filter(isValidQuickChatMessage)
  if (messages.length !== rawMessages.length) {
    return null
  }

  return {
    messages,
    modelOverride:
      typeof candidate.modelOverride === "string" ? candidate.modelOverride : null,
    assistantMode: normalizeAssistantMode(candidate.assistantMode),
    sourceRoute: normalizeSourceRoute(candidate.sourceRoute)
  }
}
