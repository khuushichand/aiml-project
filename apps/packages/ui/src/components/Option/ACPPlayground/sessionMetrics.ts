import type { ACPSession } from "@/services/acp/types"

const MESSAGE_UPDATE_TYPES = new Set(["text", "assistant_text", "user_text"])

export const getSessionMessageCount = (session: Pick<ACPSession, "updates">): number => {
  const explicitMessageCount = session.updates.filter((update) => MESSAGE_UPDATE_TYPES.has(update.type)).length
  return explicitMessageCount > 0 ? explicitMessageCount : session.updates.length
}

export const getSessionTokenUsage = (session: Pick<ACPSession, "updates">): number | null => {
  let total = 0
  let hasAnyUsage = false

  for (const update of session.updates) {
    const data = update.data as Record<string, unknown>
    const usage = (data.usage || null) as Record<string, unknown> | null

    const totalFromUsage = typeof usage?.total_tokens === "number" ? usage.total_tokens : null
    const totalFromFlat = typeof data.total_tokens === "number" ? data.total_tokens : null

    if (typeof totalFromUsage === "number") {
      total += totalFromUsage
      hasAnyUsage = true
      continue
    }

    if (typeof totalFromFlat === "number") {
      total += totalFromFlat
      hasAnyUsage = true
      continue
    }

    const promptTokens = typeof data.prompt_tokens === "number" ? data.prompt_tokens : 0
    const completionTokens = typeof data.completion_tokens === "number" ? data.completion_tokens : 0
    if (promptTokens > 0 || completionTokens > 0) {
      total += promptTokens + completionTokens
      hasAnyUsage = true
    }
  }

  return hasAnyUsage ? total : null
}
