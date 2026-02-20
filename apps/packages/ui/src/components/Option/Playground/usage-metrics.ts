import { estimateCost, getModelPricing } from "@/utils/model-pricing"

type GenerationUsage = {
  prompt_eval_count?: number
  eval_count?: number
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  usage?: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
  }
}

type MessageWithGenerationInfo = {
  generationInfo?: GenerationUsage | null
}

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value !== "number" || !Number.isFinite(value)) return null
  return value
}

export type ResolvedUsage = {
  inputTokens: number
  outputTokens: number
  totalTokens: number
}

export const resolveGenerationUsage = (
  generationInfo?: GenerationUsage | null
): ResolvedUsage => {
  if (!generationInfo || typeof generationInfo !== "object") {
    return { inputTokens: 0, outputTokens: 0, totalTokens: 0 }
  }

  const inputTokens =
    toFiniteNumber(generationInfo.prompt_eval_count) ??
    toFiniteNumber(generationInfo.prompt_tokens) ??
    toFiniteNumber(generationInfo.usage?.prompt_tokens) ??
    0
  const outputTokens =
    toFiniteNumber(generationInfo.eval_count) ??
    toFiniteNumber(generationInfo.completion_tokens) ??
    toFiniteNumber(generationInfo.usage?.completion_tokens) ??
    0
  const totalTokens =
    toFiniteNumber(generationInfo.total_tokens) ??
    toFiniteNumber(generationInfo.usage?.total_tokens) ??
    inputTokens + outputTokens

  return {
    inputTokens: Math.max(0, Math.round(inputTokens)),
    outputTokens: Math.max(0, Math.round(outputTokens)),
    totalTokens: Math.max(0, Math.round(totalTokens))
  }
}

export type SessionUsageSummary = ResolvedUsage & {
  estimatedCostUsd: number | null
}

export const aggregateSessionUsage = (
  messages: MessageWithGenerationInfo[],
  modelId?: string | null,
  providerKey?: string | null
): SessionUsageSummary => {
  const totals = messages.reduce<ResolvedUsage>(
    (acc, message) => {
      const usage = resolveGenerationUsage(message.generationInfo ?? null)
      return {
        inputTokens: acc.inputTokens + usage.inputTokens,
        outputTokens: acc.outputTokens + usage.outputTokens,
        totalTokens: acc.totalTokens + usage.totalTokens
      }
    },
    { inputTokens: 0, outputTokens: 0, totalTokens: 0 }
  )

  const pricing =
    modelId && modelId.trim().length > 0
      ? getModelPricing(modelId, providerKey || undefined)
      : null

  return {
    ...totals,
    estimatedCostUsd: pricing
      ? estimateCost(totals.inputTokens, totals.outputTokens, pricing)
      : null
  }
}

export type TokenBudgetProjection = {
  projectedTotalTokens: number
  remainingTokens: number | null
  utilizationPercent: number | null
  isNearLimit: boolean
  isOverLimit: boolean
}

export const projectTokenBudget = (params: {
  conversationTokens: number
  draftTokens: number
  maxTokens: number | null
  nearLimitPercent?: number
}): TokenBudgetProjection => {
  const {
    conversationTokens,
    draftTokens,
    maxTokens,
    nearLimitPercent = 85
  } = params
  const projectedTotalTokens = Math.max(
    0,
    Math.round((conversationTokens || 0) + (draftTokens || 0))
  )

  if (typeof maxTokens !== "number" || !Number.isFinite(maxTokens) || maxTokens <= 0) {
    return {
      projectedTotalTokens,
      remainingTokens: null,
      utilizationPercent: null,
      isNearLimit: false,
      isOverLimit: false
    }
  }

  const utilizationPercent = (projectedTotalTokens / maxTokens) * 100
  const remainingTokens = Math.round(maxTokens - projectedTotalTokens)
  const isOverLimit = projectedTotalTokens > maxTokens
  const isNearLimit = !isOverLimit && utilizationPercent >= nearLimitPercent

  return {
    projectedTotalTokens,
    remainingTokens,
    utilizationPercent,
    isNearLimit,
    isOverLimit
  }
}
