import type { SessionInsights } from "./session-insights"
import type { TokenBudgetRiskLevel } from "./usage-metrics"

export type ModelRecommendationAction =
  | "open_model_settings"
  | "enable_json_mode"
  | "open_context_window"
  | "open_session_insights"

export type ModelRecommendation = {
  id: string
  title: string
  reason: string
  action: ModelRecommendationAction
}

type Params = {
  draftText: string
  selectedModel: string | null | undefined
  modelCapabilities: string[]
  webSearch: boolean
  jsonMode: boolean
  hasImageAttachment: boolean
  tokenBudgetRiskLevel: TokenBudgetRiskLevel
  sessionInsights: SessionInsights
}

const isStructuredOutputRequest = (value: string): boolean =>
  /\b(json|schema|fields|object|array|table|csv|yaml)\b/i.test(value)

const isCodingRequest = (value: string): boolean =>
  /\b(code|function|typescript|javascript|python|sql|debug|refactor|test)\b/i.test(
    value
  )

const isResearchRequest = (value: string): boolean =>
  /\b(source|citation|research|evidence|web|search|references)\b/i.test(value)

const isSmallTierModel = (model: string | null | undefined): boolean => {
  if (!model) return false
  return /\b(mini|small|nano|haiku|7b|8b|3b|1b)\b/i.test(model)
}

const isHighTierModel = (model: string | null | undefined): boolean => {
  if (!model) return false
  return /\b(pro|opus|sonnet|gpt-4|gpt-5|reasoner)\b/i.test(model)
}

const supportsCapability = (
  capabilities: string[],
  capability: "vision" | "tools"
): boolean => capabilities.includes(capability)

export const buildModelRecommendations = (
  params: Params
): ModelRecommendation[] => {
  const {
    draftText,
    selectedModel,
    modelCapabilities,
    webSearch,
    jsonMode,
    hasImageAttachment,
    tokenBudgetRiskLevel,
    sessionInsights
  } = params

  const recommendations: ModelRecommendation[] = []

  if (hasImageAttachment && !supportsCapability(modelCapabilities, "vision")) {
    recommendations.push({
      id: "vision-mismatch",
      title: "Switch to a vision-capable model",
      reason:
        "This prompt includes an image attachment but the current model does not advertise vision input support.",
      action: "open_model_settings"
    })
  }

  if ((webSearch || isResearchRequest(draftText)) && !supportsCapability(modelCapabilities, "tools")) {
    recommendations.push({
      id: "tools-mismatch",
      title: "Use a tools-capable model for research tasks",
      reason:
        "Research and citation-heavy prompts are more reliable with models that support tool/routing orchestration.",
      action: "open_model_settings"
    })
  }

  if (isStructuredOutputRequest(draftText) && !jsonMode) {
    recommendations.push({
      id: "structured-json-mode",
      title: "Enable JSON mode for structured output",
      reason:
        "The prompt asks for structured output. JSON mode reduces malformed responses and parsing failures.",
      action: "enable_json_mode"
    })
  }

  if (isCodingRequest(draftText) && isSmallTierModel(selectedModel)) {
    recommendations.push({
      id: "coding-reasoning-tier",
      title: "Consider a higher-reasoning model for coding",
      reason:
        "Code generation/debugging requests usually benefit from stronger reasoning models than mini/small tiers.",
      action: "open_model_settings"
    })
  }

  if (tokenBudgetRiskLevel === "high" || tokenBudgetRiskLevel === "critical") {
    recommendations.push({
      id: "token-risk",
      title: "Reduce truncation risk before sending",
      reason:
        "Projected context utilization is high; consider a checkpoint summary or a larger context window.",
      action: "open_context_window"
    })
  }

  if (
    sessionInsights.totals.estimatedCostUsd != null &&
    sessionInsights.totals.estimatedCostUsd > 1 &&
    isHighTierModel(selectedModel)
  ) {
    recommendations.push({
      id: "session-cost",
      title: "Review session cost distribution",
      reason:
        "Session cost is trending high. Inspect model usage breakdown and consider routing routine turns to lower-cost models.",
      action: "open_session_insights"
    })
  }

  return recommendations.slice(0, 4)
}
