import { estimateCost, getModelPricing } from "@/utils/model-pricing"
import { resolveGenerationUsage } from "./usage-metrics"

type SessionMessage = {
  isBot?: boolean
  role?: "user" | "assistant" | "system"
  message?: string
  modelName?: string
  modelId?: string
  generationInfo?: Record<string, unknown> | null
}

export type SessionInsightsModelRow = {
  key: string
  providerKey: string
  modelId: string
  messageCount: number
  inputTokens: number
  outputTokens: number
  totalTokens: number
  estimatedCostUsd: number | null
}

export type SessionInsightsProviderRow = {
  providerKey: string
  modelCount: number
  totalTokens: number
  estimatedCostUsd: number | null
}

export type SessionInsightsTopicRow = {
  label: string
  count: number
}

export type SessionInsights = {
  totals: {
    generatedMessages: number
    totalTokens: number
    estimatedCostUsd: number | null
  }
  models: SessionInsightsModelRow[]
  providers: SessionInsightsProviderRow[]
  topics: SessionInsightsTopicRow[]
}

const UNKNOWN_PROVIDER = "unknown"
const UNKNOWN_MODEL = "unknown-model"

const TOPIC_STOPWORDS = new Set([
  "about",
  "above",
  "after",
  "again",
  "against",
  "among",
  "because",
  "before",
  "being",
  "below",
  "between",
  "could",
  "first",
  "from",
  "have",
  "into",
  "just",
  "make",
  "more",
  "most",
  "need",
  "only",
  "other",
  "over",
  "please",
  "same",
  "some",
  "that",
  "their",
  "them",
  "then",
  "there",
  "these",
  "they",
  "this",
  "what",
  "when",
  "where",
  "which",
  "while",
  "with",
  "would",
  "your"
])

const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

const pickString = (values: unknown[]): string | null => {
  for (const value of values) {
    if (typeof value !== "string") continue
    const trimmed = value.trim()
    if (trimmed.length > 0) return trimmed
  }
  return null
}

const resolveModelAndProvider = (
  message: SessionMessage
): { providerKey: string; modelId: string } => {
  const info = asRecord(message.generationInfo) || {}
  const modelId =
    pickString([
      message.modelId,
      message.modelName,
      info.resolved_model,
      info.resolvedModel,
      info.model_name,
      info.model
    ]) || UNKNOWN_MODEL
  const explicitProvider =
    pickString([
      info.resolved_provider,
      info.resolvedProvider,
      info.provider,
      info.provider_name,
      info.api_provider
    ]) || null
  const providerFromModel =
    !explicitProvider && modelId.includes("/")
      ? modelId.split("/", 1)[0]?.trim().toLowerCase() || null
      : null
  const providerKey = explicitProvider || providerFromModel || UNKNOWN_PROVIDER

  return {
    providerKey,
    modelId
  }
}

const resolveEstimatedMessageCostUsd = (
  message: SessionMessage,
  inputTokens: number,
  outputTokens: number,
  providerKey: string,
  modelId: string
): number | null => {
  const info = asRecord(message.generationInfo) || {}
  const usage = asRecord(info.usage)
  const pricing = asRecord(info.pricing)

  const inlineCost =
    (typeof info.estimated_cost_usd === "number"
      ? info.estimated_cost_usd
      : null) ??
    (typeof usage?.estimated_cost_usd === "number"
      ? usage.estimated_cost_usd
      : null) ??
    (typeof pricing?.total_cost_usd === "number"
      ? pricing.total_cost_usd
      : null) ??
    (typeof info.total_cost_usd === "number"
      ? info.total_cost_usd
      : null)

  if (typeof inlineCost === "number" && Number.isFinite(inlineCost)) {
    return Math.max(0, inlineCost)
  }

  const modelPricing = getModelPricing(modelId, providerKey)
  if (!modelPricing) return null

  return estimateCost(inputTokens, outputTokens, modelPricing)
}

const toTopicTokens = (value: string): string[] => {
  const matches = value.toLowerCase().match(/[a-z0-9]{4,}/g) || []
  return matches.filter((token) => !TOPIC_STOPWORDS.has(token))
}

export const buildSessionInsights = (
  messages: SessionMessage[]
): SessionInsights => {
  const modelMap = new Map<string, SessionInsightsModelRow>()
  const topicCounts = new Map<string, number>()

  messages.forEach((message) => {
    const rawText = typeof message.message === "string" ? message.message : ""
    const role = message.role || (message.isBot ? "assistant" : "user")
    if (role === "user" && rawText.trim().length > 0) {
      toTopicTokens(rawText).forEach((token) => {
        topicCounts.set(token, (topicCounts.get(token) || 0) + 1)
      })
    }

    if (role !== "assistant" && !message.isBot) {
      return
    }

    const usage = resolveGenerationUsage(message.generationInfo || undefined)
    if (usage.totalTokens <= 0) return

    const { providerKey, modelId } = resolveModelAndProvider(message)
    const key = `${providerKey}::${modelId}`
    const estimatedCostUsd = resolveEstimatedMessageCostUsd(
      message,
      usage.inputTokens,
      usage.outputTokens,
      providerKey,
      modelId
    )
    const existing = modelMap.get(key)
    if (!existing) {
      modelMap.set(key, {
        key,
        providerKey,
        modelId,
        messageCount: 1,
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        totalTokens: usage.totalTokens,
        estimatedCostUsd
      })
      return
    }

    existing.messageCount += 1
    existing.inputTokens += usage.inputTokens
    existing.outputTokens += usage.outputTokens
    existing.totalTokens += usage.totalTokens
    if (estimatedCostUsd != null) {
      existing.estimatedCostUsd =
        (existing.estimatedCostUsd || 0) + estimatedCostUsd
    }
  })

  const models = Array.from(modelMap.values()).sort((left, right) => {
    if (right.totalTokens !== left.totalTokens) {
      return right.totalTokens - left.totalTokens
    }
    return left.modelId.localeCompare(right.modelId)
  })

  const providerMap = new Map<string, SessionInsightsProviderRow>()
  models.forEach((row) => {
    const providerEntry = providerMap.get(row.providerKey)
    if (!providerEntry) {
      providerMap.set(row.providerKey, {
        providerKey: row.providerKey,
        modelCount: 1,
        totalTokens: row.totalTokens,
        estimatedCostUsd: row.estimatedCostUsd
      })
      return
    }
    providerEntry.modelCount += 1
    providerEntry.totalTokens += row.totalTokens
    if (row.estimatedCostUsd != null) {
      providerEntry.estimatedCostUsd =
        (providerEntry.estimatedCostUsd || 0) + row.estimatedCostUsd
    }
  })

  const providers = Array.from(providerMap.values()).sort(
    (left, right) => right.totalTokens - left.totalTokens
  )

  const topics = Array.from(topicCounts.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => {
      if (right.count !== left.count) return right.count - left.count
      return left.label.localeCompare(right.label)
    })
    .slice(0, 8)

  const totalTokens = models.reduce((sum, row) => sum + row.totalTokens, 0)
  const estimatedCostEntries = models
    .map((row) => row.estimatedCostUsd)
    .filter((value): value is number => typeof value === "number")
  const estimatedCostUsd =
    estimatedCostEntries.length > 0
      ? estimatedCostEntries.reduce((sum, value) => sum + value, 0)
      : null

  return {
    totals: {
      generatedMessages: models.reduce((sum, row) => sum + row.messageCount, 0),
      totalTokens,
      estimatedCostUsd
    },
    models,
    providers,
    topics
  }
}
