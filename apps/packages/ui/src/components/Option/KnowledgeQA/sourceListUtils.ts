import type { RagResult } from "./types"

export type SourceSortMode = "relevance" | "title" | "date" | "cited"

export type SourceListItem = {
  result: RagResult
  originalIndex: number
}

const SOURCE_TYPE_LABELS: Record<
  string,
  { singular: string; plural: string }
> = {
  media_db: { singular: "Document", plural: "Documents" },
  notes: { singular: "Note", plural: "Notes" },
  characters: { singular: "Character", plural: "Characters" },
  chats: { singular: "Chat", plural: "Chats" },
  kanban: { singular: "Board item", plural: "Board items" },
  unknown: { singular: "Other", plural: "Other" },
}

const DATE_METADATA_KEYS = [
  "published_at",
  "publishedAt",
  "created_at",
  "createdAt",
  "updated_at",
  "updatedAt",
  "date",
  "source_date",
] as const

export function normalizeSourceType(sourceType: unknown): string {
  const normalized = String(sourceType || "").trim().toLowerCase()
  if (!normalized) return "unknown"
  if (SOURCE_TYPE_LABELS[normalized]) return normalized
  return "unknown"
}

export function getSourceTypeLabel(
  sourceType: unknown,
  options: { plural?: boolean } = {}
): string {
  const normalized = normalizeSourceType(sourceType)
  const labels = SOURCE_TYPE_LABELS[normalized] || SOURCE_TYPE_LABELS.unknown
  return options.plural ? labels.plural : labels.singular
}

export function buildSourceTypeCounts(results: RagResult[]): Record<string, number> {
  return results.reduce<Record<string, number>>((acc, result) => {
    const sourceType = normalizeSourceType(result.metadata?.source_type)
    acc[sourceType] = (acc[sourceType] || 0) + 1
    return acc
  }, {})
}

function parseDateValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value
  }
  if (typeof value !== "string" || value.trim().length === 0) {
    return null
  }
  const parsed = Date.parse(value)
  if (Number.isNaN(parsed)) return null
  return parsed
}

export function getSourceTimestamp(result: RagResult): number | null {
  const metadata = result.metadata
  if (!metadata || typeof metadata !== "object") {
    return null
  }

  for (const key of DATE_METADATA_KEYS) {
    const value = metadata[key]
    const parsed = parseDateValue(value)
    if (parsed != null) return parsed
  }
  return null
}

export function formatSourceDate(result: RagResult): string | null {
  const timestamp = getSourceTimestamp(result)
  if (timestamp == null) return null
  return new Date(timestamp).toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

export type RelevanceDescriptor = {
  percent: number
  level: "high" | "moderate" | "low"
  label: string
  className: string
}

export function getRelevanceDescriptor(
  score: number | undefined
): RelevanceDescriptor | null {
  if (typeof score !== "number" || !Number.isFinite(score)) return null
  const percent = Math.max(0, Math.min(100, Math.round(score * 100)))
  if (score >= 0.8) {
    return {
      percent,
      level: "high",
      label: "High match",
      className: "bg-success/15 text-success border border-success/30",
    }
  }
  if (score >= 0.5) {
    return {
      percent,
      level: "moderate",
      label: "Moderate match",
      className: "bg-warn/15 text-warn border border-warn/30",
    }
  }
  return {
    percent,
    level: "low",
    label: "Low match",
    className: "bg-danger/15 text-danger border border-danger/30",
  }
}

export function formatChunkPosition(chunkId: unknown): string | null {
  if (typeof chunkId !== "string" || chunkId.trim().length === 0) return null
  const normalized = chunkId.trim()

  const slashPattern = normalized.match(/\b(\d+)\s*\/\s*(\d+)\b/)
  if (slashPattern) {
    return `Chunk ${slashPattern[1]} of ${slashPattern[2]}`
  }

  const chunkPattern = normalized.match(
    /chunk[_\s-]?(\d+)(?:[_\s-]?(?:of)?[_\s-]?(\d+))?/i
  )
  if (chunkPattern) {
    if (chunkPattern[2]) {
      return `Chunk ${chunkPattern[1]} of ${chunkPattern[2]}`
    }
    return `Chunk ${chunkPattern[1]}`
  }

  if (/^\d{1,4}$/.test(normalized)) {
    return `Chunk ${normalized}`
  }

  return null
}

export function filterItemsBySourceType(
  items: SourceListItem[],
  sourceType: string
): SourceListItem[] {
  if (sourceType === "all") return items
  return items.filter(
    (item) => normalizeSourceType(item.result.metadata?.source_type) === sourceType
  )
}

export function sortSourceItems(
  items: SourceListItem[],
  mode: SourceSortMode,
  citedIndices: Set<number>
): SourceListItem[] {
  const copy = [...items]

  if (mode === "relevance") {
    return copy
  }

  if (mode === "title") {
    return copy.sort((left, right) => {
      const titleLeft = left.result.metadata?.title || left.result.metadata?.source || ""
      const titleRight =
        right.result.metadata?.title || right.result.metadata?.source || ""
      return titleLeft.localeCompare(titleRight)
    })
  }

  if (mode === "date") {
    return copy.sort((left, right) => {
      const dateLeft = getSourceTimestamp(left.result)
      const dateRight = getSourceTimestamp(right.result)
      if (dateLeft == null && dateRight == null) {
        return left.originalIndex - right.originalIndex
      }
      if (dateLeft == null) return 1
      if (dateRight == null) return -1
      return dateRight - dateLeft
    })
  }

  return copy.sort((left, right) => {
    const leftCited = citedIndices.has(left.originalIndex)
    const rightCited = citedIndices.has(right.originalIndex)
    if (leftCited === rightCited) {
      return left.originalIndex - right.originalIndex
    }
    return leftCited ? -1 : 1
  })
}

