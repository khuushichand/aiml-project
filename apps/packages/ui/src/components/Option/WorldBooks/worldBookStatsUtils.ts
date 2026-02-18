export type BudgetUtilizationBand = "safe" | "warning" | "critical"

export const getBudgetUtilizationPercent = (
  estimatedTokens: unknown,
  tokenBudget: unknown
): number | null => {
  const estimated = Number(estimatedTokens)
  const budget = Number(tokenBudget)
  if (!Number.isFinite(budget) || budget <= 0) return null
  const safeEstimated = Number.isFinite(estimated) && estimated > 0 ? estimated : 0
  return Number(((safeEstimated / budget) * 100).toFixed(1))
}

export const getBudgetUtilizationBand = (
  percent: number | null
): BudgetUtilizationBand => {
  if (percent == null || !Number.isFinite(percent)) return "safe"
  if (percent > 90) return "critical"
  if (percent >= 70) return "warning"
  return "safe"
}

export const getBudgetUtilizationColor = (band: BudgetUtilizationBand): string => {
  if (band === "critical") return "#ff4d4f"
  if (band === "warning") return "#faad14"
  return "#52c41a"
}

export const getTokenEstimatorNote = (stats: Record<string, any> | null | undefined): string => {
  const method =
    String(
      stats?.tokenizer_name ||
        stats?.token_estimator ||
        stats?.token_estimation_method ||
        ""
    ).trim()
  if (method) {
    return `Estimated using ${method}.`
  }
  return "Estimated using ~4 characters per token."
}
