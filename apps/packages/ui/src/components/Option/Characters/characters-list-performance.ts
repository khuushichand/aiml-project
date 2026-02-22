export const CHARACTERS_LIST_PERF_TARGETS = {
  list_payload_max_bytes: 600 * 1024,
  initial_render_p95_ms: 250,
  interaction_p95_ms: 120
} as const

export type CharactersListPerfFixture = {
  fixture_name: string
  list_payload: unknown
  initial_render_latencies_ms: number[]
  interaction_latencies_ms: number[]
}

export type CharactersListPerfStats = {
  count: number
  min: number
  max: number
  mean: number
  p95: number
}

export type CharactersListPerfReport = {
  fixture_name: string
  list_payload_bytes: number
  initial_render: CharactersListPerfStats
  interaction: CharactersListPerfStats
  checks: {
    list_payload_within_limit: boolean
    initial_render_within_target: boolean
    interaction_within_target: boolean
  }
}

const EMPTY_STATS: CharactersListPerfStats = {
  count: 0,
  min: 0,
  max: 0,
  mean: 0,
  p95: 0
}

const encoder = new TextEncoder()

export const computeP95 = (values: number[]): number => {
  if (!Array.isArray(values) || values.length === 0) return 0
  const sorted = values
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b)
  if (sorted.length === 0) return 0
  const index = Math.max(0, Math.ceil(sorted.length * 0.95) - 1)
  return sorted[index]
}

export const computeStats = (values: number[]): CharactersListPerfStats => {
  const normalized = values
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value))
  if (normalized.length === 0) return EMPTY_STATS

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
    p95: computeP95(sorted)
  }
}

export const estimateListPayloadSizeBytes = (payload: unknown): number => {
  try {
    return encoder.encode(JSON.stringify(payload ?? null)).byteLength
  } catch {
    return 0
  }
}

export const evaluateCharactersListPerfFixture = (
  fixture: CharactersListPerfFixture
): CharactersListPerfReport => {
  const listPayloadBytes = estimateListPayloadSizeBytes(fixture.list_payload)
  const initialRender = computeStats(fixture.initial_render_latencies_ms)
  const interaction = computeStats(fixture.interaction_latencies_ms)

  return {
    fixture_name: fixture.fixture_name,
    list_payload_bytes: listPayloadBytes,
    initial_render: initialRender,
    interaction,
    checks: {
      list_payload_within_limit:
        listPayloadBytes <= CHARACTERS_LIST_PERF_TARGETS.list_payload_max_bytes,
      initial_render_within_target:
        initialRender.p95 <= CHARACTERS_LIST_PERF_TARGETS.initial_render_p95_ms,
      interaction_within_target:
        interaction.p95 <= CHARACTERS_LIST_PERF_TARGETS.interaction_p95_ms
    }
  }
}

export const isCharactersListPerfFixturePassing = (
  report: CharactersListPerfReport
): boolean => Object.values(report.checks).every((value) => Boolean(value))
