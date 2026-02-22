export type PromptTokenThresholds = {
  warning: number
  danger: number
}

export const DEFAULT_PROMPT_TOKEN_THRESHOLDS: PromptTokenThresholds = {
  warning: 1000,
  danger: 2000
}

export const estimatePromptTokens = (text: string | null | undefined): number => {
  const normalized = typeof text === "string" ? text : ""
  if (!normalized.length) {
    return 0
  }

  // Fast, model-agnostic approximation used for inline UX guidance.
  return Math.ceil(normalized.length / 4)
}

export type PromptTokenBudgetState = "normal" | "warning" | "danger"

export const getPromptTokenBudgetState = (
  tokenCount: number,
  thresholds: PromptTokenThresholds = DEFAULT_PROMPT_TOKEN_THRESHOLDS
): PromptTokenBudgetState => {
  if (tokenCount >= thresholds.danger) {
    return "danger"
  }
  if (tokenCount >= thresholds.warning) {
    return "warning"
  }
  return "normal"
}
