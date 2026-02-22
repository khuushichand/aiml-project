import type { Message } from "@/store/option"
import type { TokenBudgetProjection } from "./usage-metrics"

const DEFAULT_MAX_RECENT_MESSAGES = 8
const MAX_SNIPPET_CHARS = 240
const MIN_MESSAGE_COUNT_FOR_SUGGESTION = 8
const MIN_UTILIZATION_PERCENT_FOR_SUGGESTION = 72

const normalizeWhitespace = (value: string): string =>
  value.replace(/\s+/g, " ").trim()

const clip = (value: string, maxChars: number): string => {
  if (value.length <= maxChars) return value
  return `${value.slice(0, Math.max(0, maxChars - 1)).trimEnd()}…`
}

const resolveRoleLabel = (message: Message): "User" | "Assistant" | "System" => {
  if (message.role === "user") return "User"
  if (message.role === "assistant") return "Assistant"
  if (message.role === "system") return "System"
  return message.isBot ? "Assistant" : "User"
}

const toTranscriptLine = (message: Message, index: number): string | null => {
  const rawContent =
    typeof message.message === "string" ? normalizeWhitespace(message.message) : ""
  if (!rawContent) return null
  const role = resolveRoleLabel(message)
  const clipped = clip(rawContent, MAX_SNIPPET_CHARS)
  return `${index + 1}. ${role}: ${clipped}`
}

export const buildConversationSummaryCheckpointPrompt = (
  messages: Message[],
  options?: { maxRecentMessages?: number }
): string => {
  const maxRecentMessages = Math.max(
    2,
    Math.round(options?.maxRecentMessages ?? DEFAULT_MAX_RECENT_MESSAGES)
  )
  const recentMessages = messages
    .filter((entry) => typeof entry?.message === "string" && entry.message.trim().length > 0)
    .slice(-maxRecentMessages)
  const transcriptLines = recentMessages
    .map((message, index) => toTranscriptLine(message, index))
    .filter((line): line is string => Boolean(line))

  const transcriptBlock =
    transcriptLines.length > 0
      ? transcriptLines.join("\n")
      : "No transcript excerpt available yet. Summarize the current task intent and next steps."

  return [
    "Create a checkpoint summary of this conversation so we can continue in a fresh context window.",
    "Keep the summary concise and actionable.",
    "Return these sections:",
    "- Goals and constraints",
    "- Decisions and assumptions",
    "- Open questions and blockers",
    "- Next steps",
    "- Sources that must remain pinned",
    "",
    "Conversation excerpt:",
    transcriptBlock
  ].join("\n")
}

export type SummaryCheckpointSuggestion = {
  shouldSuggest: boolean
  reason: "token-budget" | "message-volume" | null
}

export const evaluateSummaryCheckpointSuggestion = (params: {
  messageCount: number
  projectedBudget: TokenBudgetProjection
  minMessageCount?: number
  minUtilizationPercent?: number
}): SummaryCheckpointSuggestion => {
  const {
    messageCount,
    projectedBudget,
    minMessageCount = MIN_MESSAGE_COUNT_FOR_SUGGESTION,
    minUtilizationPercent = MIN_UTILIZATION_PERCENT_FOR_SUGGESTION
  } = params

  if (projectedBudget.isOverLimit || projectedBudget.isNearLimit) {
    return {
      shouldSuggest: true,
      reason: "token-budget"
    }
  }

  if (
    messageCount >= minMessageCount &&
    typeof projectedBudget.utilizationPercent === "number" &&
    projectedBudget.utilizationPercent >= minUtilizationPercent
  ) {
    return {
      shouldSuggest: true,
      reason: "message-volume"
    }
  }

  return {
    shouldSuggest: false,
    reason: null
  }
}
