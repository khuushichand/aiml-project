const COLLAPSE_WHITESPACE = /\s+/g
const SENTENCE_BOUNDARY = /(?<=[.!?])\s+/

const collapseWhitespace = (value: string): string =>
  value.replace(COLLAPSE_WHITESPACE, " ").trim()

const normalizeSegment = (value: string): string =>
  collapseWhitespace(value).toLowerCase()

const truncateSegment = (value: string, maxChars = 160): string => {
  const collapsed = collapseWhitespace(value)
  if (!collapsed) return ""
  if (collapsed.length <= maxChars) return collapsed
  if (maxChars <= 3) return "..."
  return `${collapsed.slice(0, maxChars - 3)}...`
}

const segmentResponse = (value: string): string[] => {
  return value
    .split(/\n+/)
    .flatMap((line) => line.split(SENTENCE_BOUNDARY))
    .map(collapseWhitespace)
    .filter(Boolean)
}

const uniqueSegmentsByKey = (segments: string[]): Map<string, string> => {
  const map = new Map<string, string>()
  segments.forEach((segment) => {
    const key = normalizeSegment(segment)
    if (!key || map.has(key)) return
    map.set(key, segment)
  })
  return map
}

export type CompareResponseDiff = {
  baselineSegments: number
  candidateSegments: number
  sharedSegments: number
  overlapRatio: number
  addedHighlights: string[]
  removedHighlights: string[]
  hasMeaningfulDifference: boolean
}

export const computeResponseDiffPreview = (params: {
  baseline: string
  candidate: string
  maxHighlights?: number
}): CompareResponseDiff => {
  const { baseline, candidate, maxHighlights = 2 } = params
  const safeHighlightLimit =
    Number.isFinite(maxHighlights) && maxHighlights > 0
      ? Math.floor(maxHighlights)
      : 2

  const baselineMap = uniqueSegmentsByKey(segmentResponse(baseline))
  const candidateMap = uniqueSegmentsByKey(segmentResponse(candidate))

  const baselineKeys = Array.from(baselineMap.keys())
  const candidateKeys = Array.from(candidateMap.keys())

  const sharedSegments = candidateKeys.reduce((acc, key) => {
    if (baselineMap.has(key)) return acc + 1
    return acc
  }, 0)

  const addedHighlights = candidateKeys
    .filter((key) => !baselineMap.has(key))
    .map((key) => truncateSegment(candidateMap.get(key) || ""))
    .filter(Boolean)
    .slice(0, safeHighlightLimit)

  const removedHighlights = baselineKeys
    .filter((key) => !candidateMap.has(key))
    .map((key) => truncateSegment(baselineMap.get(key) || ""))
    .filter(Boolean)
    .slice(0, safeHighlightLimit)

  const denominator = Math.max(candidateMap.size, baselineMap.size, 1)
  const overlapRatio = Math.max(
    0,
    Math.min(1, Number((sharedSegments / denominator).toFixed(4)))
  )

  return {
    baselineSegments: baselineMap.size,
    candidateSegments: candidateMap.size,
    sharedSegments,
    overlapRatio,
    addedHighlights,
    removedHighlights,
    hasMeaningfulDifference:
      addedHighlights.length > 0 || removedHighlights.length > 0
  }
}
