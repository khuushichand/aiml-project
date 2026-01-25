/**
 * Metrics formatting helpers for evaluations UI.
 */

export interface MetricPoint {
  key: string
  value: number
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value)

export const clamp01 = (value: number): number => {
  if (!Number.isFinite(value)) return 0
  return Math.min(Math.max(value, 0), 1)
}

export const formatMetricValue = (value: number, digits = 3): string => {
  if (!isFiniteNumber(value)) return "—"
  return value.toFixed(digits)
}

export const formatMetricDelta = (delta: number, digits = 3): string => {
  if (!isFiniteNumber(delta)) return "—"
  const sign = delta > 0 ? "+" : delta < 0 ? "-" : ""
  return `${sign}${Math.abs(delta).toFixed(digits)}`
}

export const flattenMetrics = (
  results: unknown,
  maxItems = 30
): Record<string, number> => {
  const map: Record<string, number> = {}
  const candidate =
    isRecord(results) && isRecord(results.metrics) ? results.metrics : results

  const walk = (obj: unknown, prefix = "") => {
    if (!isRecord(obj)) return
    for (const [k, v] of Object.entries(obj)) {
      const name = prefix ? `${prefix}.${k}` : k
      if (isFiniteNumber(v)) {
        map[name] = v
      } else if (isRecord(v) && Object.keys(map).length < maxItems) {
        walk(v, name)
      }
      if (Object.keys(map).length >= maxItems) return
    }
  }

  walk(candidate)
  return map
}

export const metricsFromResults = (
  results: unknown,
  maxItems = 20
): MetricPoint[] => {
  const map = flattenMetrics(results, maxItems)
  return Object.entries(map).map(([key, value]) => ({ key, value }))
}
