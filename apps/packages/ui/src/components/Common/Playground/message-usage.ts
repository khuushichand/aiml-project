const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value !== "number" || !Number.isFinite(value)) return null
  return value
}

export type MessageUsage = {
  promptTokens: number
  completionTokens: number
  totalTokens: number
}

export const resolveMessageUsage = (generationInfo: unknown): MessageUsage => {
  if (!generationInfo || typeof generationInfo !== "object") {
    return { promptTokens: 0, completionTokens: 0, totalTokens: 0 }
  }

  const payload = generationInfo as Record<string, any>
  const usage = (payload.usage || {}) as Record<string, any>

  const promptTokens =
    toFiniteNumber(payload.prompt_eval_count) ??
    toFiniteNumber(payload.prompt_tokens) ??
    toFiniteNumber(payload.input_tokens) ??
    toFiniteNumber(usage.prompt_tokens) ??
    toFiniteNumber(usage.input_tokens) ??
    0
  const completionTokens =
    toFiniteNumber(payload.eval_count) ??
    toFiniteNumber(payload.completion_tokens) ??
    toFiniteNumber(payload.output_tokens) ??
    toFiniteNumber(usage.completion_tokens) ??
    toFiniteNumber(usage.output_tokens) ??
    0
  const totalTokens =
    toFiniteNumber(payload.total_tokens) ??
    toFiniteNumber(payload.total_token_count) ??
    toFiniteNumber(usage.total_tokens) ??
    promptTokens + completionTokens

  return {
    promptTokens: Math.max(0, Math.round(promptTokens)),
    completionTokens: Math.max(0, Math.round(completionTokens)),
    totalTokens: Math.max(0, Math.round(totalTokens))
  }
}

export const resolveMessageCostUsd = (generationInfo: unknown): number | null => {
  if (!generationInfo || typeof generationInfo !== "object") {
    return null
  }

  const payload = generationInfo as Record<string, any>
  const usage = (payload.usage || {}) as Record<string, any>
  const pricing = (payload.pricing || {}) as Record<string, any>
  const cost =
    toFiniteNumber(payload.total_cost_usd) ??
    toFiniteNumber(payload.estimated_cost_usd) ??
    toFiniteNumber(payload.cost_usd) ??
    toFiniteNumber(payload.total_cost) ??
    toFiniteNumber(payload.estimated_cost) ??
    toFiniteNumber(usage.total_cost_usd) ??
    toFiniteNumber(usage.estimated_cost_usd) ??
    toFiniteNumber(usage.cost_usd) ??
    toFiniteNumber(pricing.total_cost_usd) ??
    toFiniteNumber(pricing.estimated_cost_usd) ??
    toFiniteNumber(pricing.cost_usd)

  if (cost == null || cost < 0) return null
  return cost
}
