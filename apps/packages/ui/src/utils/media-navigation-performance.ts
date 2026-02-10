export const MEDIA_NAVIGATION_PERF_TARGETS = {
  navigation_load_p95_ms: 400,
  section_switch_cached_p95_ms: 250,
  navigation_payload_max_bytes: 200 * 1024,
  section_payload_max_bytes: 64 * 1024
} as const

export type MediaNavigationPerfCacheState = "cold" | "warm"

export type MediaNavigationPerfFixtureInput = {
  fixture_name: string
  cache_state: MediaNavigationPerfCacheState
  navigation_payload: unknown
  section_payload: unknown
  navigation_latencies_ms: number[]
  section_switch_latencies_ms: number[]
  payload_truncated?: boolean
}

export type MediaNavigationPerfStats = {
  count: number
  min: number
  max: number
  mean: number
  p50: number
  p95: number
}

export type MediaNavigationPerfFixtureReport = {
  fixture_name: string
  cache_state: MediaNavigationPerfCacheState
  payload_truncated: boolean
  navigation_payload_bytes: number
  section_payload_bytes: number
  navigation_latency: MediaNavigationPerfStats
  section_switch_latency: MediaNavigationPerfStats
  checks: {
    navigation_payload_within_limit: boolean
    section_payload_within_limit: boolean
    navigation_p95_within_target: boolean
    section_switch_p95_within_target: boolean
  }
}

const DEFAULT_STATS: MediaNavigationPerfStats = {
  count: 0,
  min: 0,
  max: 0,
  mean: 0,
  p50: 0,
  p95: 0
}

const encoder = new TextEncoder()

const clampPercentile = (percentile: number): number => {
  if (!Number.isFinite(percentile)) return 95
  return Math.max(0, Math.min(100, percentile))
}

export const computePercentile = (
  values: number[],
  percentile: number
): number => {
  if (!Array.isArray(values) || values.length === 0) return 0
  const normalized = clampPercentile(percentile)
  const sorted = [...values]
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b)
  if (sorted.length === 0) return 0
  if (normalized <= 0) return sorted[0]
  if (normalized >= 100) return sorted[sorted.length - 1]

  const index = Math.ceil((normalized / 100) * sorted.length) - 1
  const boundedIndex = Math.max(0, Math.min(sorted.length - 1, index))
  return sorted[boundedIndex]
}

export const estimatePayloadSizeBytes = (value: unknown): number => {
  try {
    const serialized = JSON.stringify(value ?? null)
    return encoder.encode(serialized).byteLength
  } catch {
    return 0
  }
}

export const computePerfStats = (values: number[]): MediaNavigationPerfStats => {
  const normalized = values
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value))
  if (normalized.length === 0) return DEFAULT_STATS

  const sorted = [...normalized].sort((a, b) => a - b)
  const count = sorted.length
  const min = sorted[0]
  const max = sorted[count - 1]
  const mean = sorted.reduce((sum, value) => sum + value, 0) / count

  return {
    count,
    min,
    max,
    mean,
    p50: computePercentile(sorted, 50),
    p95: computePercentile(sorted, 95)
  }
}

export const evaluateMediaNavigationPerfFixture = (
  fixture: MediaNavigationPerfFixtureInput
): MediaNavigationPerfFixtureReport => {
  const navigationPayloadBytes = estimatePayloadSizeBytes(fixture.navigation_payload)
  const sectionPayloadBytes = estimatePayloadSizeBytes(fixture.section_payload)
  const navigationLatency = computePerfStats(fixture.navigation_latencies_ms)
  const sectionSwitchLatency = computePerfStats(
    fixture.section_switch_latencies_ms
  )

  return {
    fixture_name: fixture.fixture_name,
    cache_state: fixture.cache_state,
    payload_truncated: Boolean(fixture.payload_truncated),
    navigation_payload_bytes: navigationPayloadBytes,
    section_payload_bytes: sectionPayloadBytes,
    navigation_latency: navigationLatency,
    section_switch_latency: sectionSwitchLatency,
    checks: {
      navigation_payload_within_limit:
        navigationPayloadBytes <=
        MEDIA_NAVIGATION_PERF_TARGETS.navigation_payload_max_bytes,
      section_payload_within_limit:
        sectionPayloadBytes <=
        MEDIA_NAVIGATION_PERF_TARGETS.section_payload_max_bytes,
      navigation_p95_within_target:
        navigationLatency.p95 <=
        MEDIA_NAVIGATION_PERF_TARGETS.navigation_load_p95_ms,
      section_switch_p95_within_target:
        sectionSwitchLatency.p95 <=
        MEDIA_NAVIGATION_PERF_TARGETS.section_switch_cached_p95_ms
    }
  }
}

export const isMediaNavigationPerfFixturePassing = (
  report: MediaNavigationPerfFixtureReport
): boolean =>
  Object.values(report.checks).every((value) => Boolean(value))
