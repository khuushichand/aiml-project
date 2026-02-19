import type {
  FilterAction,
  FilterType,
  PreviewItem,
  WatchlistFilter
} from "@/types/watchlists"

type FilterWithIndex = {
  filter: WatchlistFilter
  index: number
}

export interface EvaluatedPreviewItem extends PreviewItem {
  preview_decision: "ingest" | "filtered"
  preview_action: FilterAction | null
  preview_filter_key: string | null
  preview_filter_type: FilterType | null
  preview_flagged: boolean
}

export interface FilterPreviewOutcome {
  items: EvaluatedPreviewItem[]
  total: number
  ingestable: number
  filtered: number
}

const normalize = (value: string | null | undefined): string =>
  String(value || "").trim().toLowerCase()

const buildSearchCorpus = (item: PreviewItem): string => {
  const pieces = [item.title, item.summary, item.url]
  return normalize(pieces.filter(Boolean).join(" "))
}

const toStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
    .filter((entry) => entry.length > 0)
}

const getRegexFlags = (flags: unknown): string => {
  if (typeof flags !== "string") return "i"
  const normalized = flags.replace(/[^dgimsuvy]/g, "")
  return normalized || "i"
}

const safeRegex = (pattern: unknown, flags: unknown): RegExp | null => {
  if (typeof pattern !== "string" || !pattern.trim()) return null
  try {
    return new RegExp(pattern, getRegexFlags(flags))
  } catch {
    return null
  }
}

const parseDate = (value: unknown): number | null => {
  if (typeof value !== "string" || !value.trim()) return null
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : null
}

const resolveFilterKey = (entry: FilterWithIndex): string => {
  const raw = entry.filter.value as Record<string, unknown>
  const explicitKey = raw.key
  if (typeof explicitKey === "string" && explicitKey.trim().length > 0) {
    return explicitKey.trim()
  }
  return `filter_${entry.index + 1}`
}

const matchesFilter = (entry: FilterWithIndex, item: PreviewItem): boolean => {
  const { filter } = entry
  const value = (filter.value || {}) as Record<string, unknown>

  if (filter.type === "keyword") {
    const corpus = buildSearchCorpus(item)
    const keywords = toStringArray(value.keywords).map((keyword) => keyword.toLowerCase())
    if (keywords.length === 0) return false
    const mode = String(value.match || value.mode || "any").toLowerCase()
    return mode === "all"
      ? keywords.every((keyword) => corpus.includes(keyword))
      : keywords.some((keyword) => corpus.includes(keyword))
  }

  if (filter.type === "author") {
    const author = normalize((item as Record<string, unknown>).author as string | undefined)
    const names = toStringArray(value.names).concat(toStringArray(value.authors))
    if (!author || names.length === 0) return false
    return names.some((name) => author.includes(name.toLowerCase()))
  }

  if (filter.type === "regex") {
    const field = String(value.field || "title")
    const candidateFieldValue = normalize((item as Record<string, unknown>)[field] as string | undefined)
    const regex = safeRegex(value.pattern, value.flags)
    if (!regex) return false
    return regex.test(candidateFieldValue)
  }

  if (filter.type === "date_range") {
    const publishedAt = parseDate(item.published_at)
    if (publishedAt == null) return false
    const since = parseDate(value.since || value.start || value.start_date)
    const until = parseDate(value.until || value.end || value.end_date)
    if (since != null && publishedAt < since) return false
    if (until != null && publishedAt > until) return false
    return since != null || until != null
  }

  return false
}

const orderFilters = (filters: WatchlistFilter[]): FilterWithIndex[] =>
  filters
    .map((filter, index) => ({ filter, index }))
    .filter((entry) => entry.filter.is_active !== false)
    .sort((a, b) => {
      const priorityA = typeof a.filter.priority === "number" ? a.filter.priority : 0
      const priorityB = typeof b.filter.priority === "number" ? b.filter.priority : 0
      if (priorityA === priorityB) return a.index - b.index
      return priorityB - priorityA
    })

export const evaluatePreviewItems = (
  items: PreviewItem[],
  filters: WatchlistFilter[]
): FilterPreviewOutcome => {
  const ordered = orderFilters(filters)
  const includeFilters = ordered.filter((entry) => entry.filter.action === "include")
  let ingestable = 0
  let filtered = 0

  const evaluatedItems = items.map((item) => {
    const matches = ordered
      .map((entry) => ({ entry, matched: matchesFilter(entry, item) }))
      .filter((result) => result.matched)

    const firstExclude = matches.find((result) => result.entry.filter.action === "exclude")?.entry
    const firstInclude = matches.find((result) => result.entry.filter.action === "include")?.entry
    const firstFlag = matches.find((result) => result.entry.filter.action === "flag")?.entry
    const includeGatingActive = includeFilters.length > 0
    const hasIncludeMatch = Boolean(firstInclude)

    let previewDecision: "ingest" | "filtered" = "ingest"
    let previewAction: FilterAction | null = null
    let matchedFilter: FilterWithIndex | null = null

    if (firstExclude) {
      previewDecision = "filtered"
      previewAction = "exclude"
      matchedFilter = firstExclude
    } else if (includeGatingActive && !hasIncludeMatch) {
      previewDecision = "filtered"
      previewAction = null
      matchedFilter = null
    } else if (firstInclude) {
      previewDecision = "ingest"
      previewAction = "include"
      matchedFilter = firstInclude
    } else if (firstFlag) {
      previewDecision = "ingest"
      previewAction = "flag"
      matchedFilter = firstFlag
    }

    if (previewDecision === "ingest") {
      ingestable += 1
    } else {
      filtered += 1
    }

    return {
      ...item,
      preview_decision: previewDecision,
      preview_action: previewAction,
      preview_filter_key: matchedFilter ? resolveFilterKey(matchedFilter) : null,
      preview_filter_type: matchedFilter ? matchedFilter.filter.type : null,
      preview_flagged: previewAction === "flag"
    }
  })

  return {
    items: evaluatedItems,
    total: evaluatedItems.length,
    ingestable,
    filtered
  }
}
