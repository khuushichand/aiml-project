const DEFAULT_PREVIEW_BUDGET = 180
const MIN_PREVIEW_BUDGET = 120
const MAX_PREVIEW_BUDGET = 280

export const collapsePreviewText = (value: string): string => {
  return value.replace(/\s+/g, " ").trim()
}

export const computeNormalizedPreviewBudget = (
  values: string[],
  fallbackBudget = DEFAULT_PREVIEW_BUDGET
): number => {
  const lengths = values
    .map(collapsePreviewText)
    .map((value) => value.length)
    .filter((length) => length > 0)
  if (lengths.length === 0) {
    return fallbackBudget
  }
  const shortest = Math.min(...lengths)
  return Math.max(MIN_PREVIEW_BUDGET, Math.min(MAX_PREVIEW_BUDGET, shortest))
}

export const buildNormalizedPreview = (
  value: string,
  maxChars: number
): string => {
  const collapsed = collapsePreviewText(value)
  if (!collapsed) return ""
  const safeBudget =
    Number.isFinite(maxChars) && maxChars > 0
      ? Math.max(1, Math.floor(maxChars))
      : DEFAULT_PREVIEW_BUDGET
  if (collapsed.length <= safeBudget) {
    return collapsed
  }
  if (safeBudget <= 1) {
    return "..."
  }
  return `${collapsed.slice(0, safeBudget - 1)}...`
}
