/**
 * Query suggestion model for Knowledge QA.
 *
 * This file intentionally includes:
 * 1) Local suggestion prototype logic (Stage 4 implementation path)
 * 2) Remote API contract types (phased rollout contract)
 */

export const QUERY_SUGGESTION_MIN_QUERY_LENGTH = 2
export const QUERY_SUGGESTION_DEFAULT_LIMIT = 5
export const QUERY_SUGGESTION_MAX_LIMIT = 10

export const QUERY_SUGGESTION_ROLLOUT_PHASES = [
  "phase_1_local_history_examples",
  "phase_2_remote_personalized",
  "phase_3_semantic_cross_document",
] as const

export type QuerySuggestionSource = "history" | "example" | "source_title"

export type QuerySuggestion = {
  id: string
  text: string
  source: QuerySuggestionSource
  score: number
}

export type BuildQuerySuggestionsInput = {
  query: string
  historyQueries?: string[]
  exampleQueries?: string[]
  sourceTitles?: string[]
  limit?: number
}

export type QuerySuggestionApiRequest = {
  query: string
  limit?: number
  thread_id?: string
  include_history?: boolean
  include_source_titles?: boolean
}

export type QuerySuggestionApiResponse = {
  suggestions: Array<{
    text: string
    source: QuerySuggestionSource | "semantic"
    score: number
    reason?: string
  }>
  model_version: string
  generated_at: string
}

const SOURCE_BOOST: Record<QuerySuggestionSource, number> = {
  history: 0.06,
  source_title: 0.04,
  example: 0.02,
}

const normalize = (value: string): string => value.trim().toLowerCase()

const tokenize = (value: string): string[] =>
  normalize(value)
    .split(/\s+/)
    .filter(Boolean)

const scoreCandidate = (query: string, candidate: string): number => {
  const normalizedQuery = normalize(query)
  const normalizedCandidate = normalize(candidate)
  if (!normalizedQuery || !normalizedCandidate) return 0

  if (normalizedCandidate === normalizedQuery) return 1
  if (normalizedCandidate.startsWith(normalizedQuery)) return 0.92
  if (normalizedCandidate.includes(normalizedQuery)) return 0.78

  const tokens = tokenize(normalizedQuery)
  if (tokens.length === 0) return 0

  const matchedTokens = tokens.filter((token) =>
    normalizedCandidate.includes(token)
  ).length
  if (matchedTokens === 0) return 0
  return 0.5 * (matchedTokens / tokens.length)
}

const normalizeLimit = (value: number | undefined): number => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return QUERY_SUGGESTION_DEFAULT_LIMIT
  }
  return Math.max(1, Math.min(QUERY_SUGGESTION_MAX_LIMIT, Math.floor(value)))
}

export const shouldShowSuggestionPrototype = (query: string): boolean =>
  normalize(query).length >= QUERY_SUGGESTION_MIN_QUERY_LENGTH

export const buildLocalQuerySuggestions = (
  input: BuildQuerySuggestionsInput
): QuerySuggestion[] => {
  if (!shouldShowSuggestionPrototype(input.query)) {
    return []
  }

  const dedupe = new Set<string>()
  const candidates: QuerySuggestion[] = []
  const limit = normalizeLimit(input.limit)

  const addCandidates = (
    source: QuerySuggestionSource,
    values: string[] | undefined
  ) => {
    if (!values || values.length === 0) return

    for (const rawValue of values) {
      const text = rawValue.trim()
      const key = normalize(text)
      if (!text || dedupe.has(key)) continue

      const baseScore = scoreCandidate(input.query, text)
      if (baseScore <= 0) continue

      dedupe.add(key)
      candidates.push({
        id: `${source}:${key}`,
        text,
        source,
        score: Math.min(1, baseScore + SOURCE_BOOST[source]),
      })
    }
  }

  addCandidates("history", input.historyQueries)
  addCandidates("source_title", input.sourceTitles)
  addCandidates("example", input.exampleQueries)

  return candidates
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score
      if (a.text.length !== b.text.length) return a.text.length - b.text.length
      return a.text.localeCompare(b.text)
    })
    .slice(0, limit)
}
