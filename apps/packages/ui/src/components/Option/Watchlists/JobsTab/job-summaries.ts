import type { JobScope, WatchlistFilter } from "@/types/watchlists"

type Translator = (
  key: string,
  defaultValue: string,
  options?: Record<string, unknown>
) => string

export interface ScopeNameCatalog {
  sources: Record<number, string>
  groups: Record<number, string>
}

export interface OverflowSummary {
  visible: string[]
  hiddenCount: number
  text: string
}

const pluralize = (count: number, singular: string): string =>
  `${count} ${singular}${count === 1 ? "" : "s"}`

const asStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
    .filter((entry) => entry.length > 0)
}

const summarizeValueList = (values: string[], maxVisible = 2): OverflowSummary => {
  const visible = values.slice(0, maxVisible)
  const hiddenCount = Math.max(0, values.length - visible.length)
  const text = hiddenCount > 0 ? `${visible.join(", ")} +${hiddenCount}` : visible.join(", ")
  return { visible, hiddenCount, text }
}

const extractFilterValueSummary = (filter: WatchlistFilter): string | null => {
  const value = filter.value || {}

  if (filter.type === "keyword") {
    const keywords = asStringArray((value as Record<string, unknown>).keywords)
    return keywords.length ? summarizeValueList(keywords).text : null
  }

  if (filter.type === "author") {
    const authors = asStringArray((value as Record<string, unknown>).authors)
    return authors.length ? summarizeValueList(authors).text : null
  }

  if (filter.type === "regex") {
    const pattern = (value as Record<string, unknown>).pattern
    if (typeof pattern === "string" && pattern.trim()) return pattern.trim()
    return null
  }

  if (filter.type === "date_range") {
    const start = (value as Record<string, unknown>).start_date
    const end = (value as Record<string, unknown>).end_date
    const from = typeof start === "string" && start.trim() ? start.trim() : "..."
    const to = typeof end === "string" && end.trim() ? end.trim() : "..."
    if (from === "..." && to === "...") return null
    return `${from} - ${to}`
  }

  const valueStrings = Object.values(value as Record<string, unknown>)
    .flatMap((entry) => (Array.isArray(entry) ? entry : [entry]))
    .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
    .filter((entry) => entry.length > 0)

  return valueStrings.length ? summarizeValueList(valueStrings).text : null
}

const filterTypeLabel = (type: WatchlistFilter["type"], t: Translator): string => {
  const map: Record<WatchlistFilter["type"], string> = {
    keyword: t("watchlists:jobs.filters.type.keyword", "keyword"),
    author: t("watchlists:jobs.filters.type.author", "author"),
    date_range: t("watchlists:jobs.filters.type.dateRange", "date range"),
    regex: t("watchlists:jobs.filters.type.regex", "regex"),
    all: t("watchlists:jobs.filters.type.all", "all")
  }
  return map[type]
}

const filterActionLabel = (action: WatchlistFilter["action"], t: Translator): string => {
  const map: Record<WatchlistFilter["action"], string> = {
    include: t("watchlists:jobs.filters.action.include", "Include"),
    exclude: t("watchlists:jobs.filters.action.exclude", "Exclude"),
    flag: t("watchlists:jobs.filters.action.flag", "Flag")
  }
  return map[action]
}

const resolveNames = (
  ids: number[] | undefined,
  catalog: Record<number, string>,
  fallbackPrefix = "#"
): string[] => {
  if (!Array.isArray(ids)) return []
  return ids.map((id) => catalog[id] || `${fallbackPrefix}${id}`)
}

export const summarizeScopeCounts = (scope: JobScope, t: Translator): string => {
  const parts: string[] = []
  if (scope.sources?.length) {
    parts.push(
      pluralize(
        scope.sources.length,
        t("watchlists:jobs.scope.summary.feed", "feed")
      )
    )
  }
  if (scope.groups?.length) {
    parts.push(
      pluralize(
        scope.groups.length,
        t("watchlists:jobs.scope.summary.group", "group")
      )
    )
  }
  if (scope.tags?.length) {
    parts.push(
      pluralize(scope.tags.length, t("watchlists:jobs.scope.summary.tag", "tag"))
    )
  }
  return parts.length > 0 ? parts.join(", ") : t("watchlists:jobs.noFeeds", "No feeds selected")
}

export const summarizeOverflowList = (
  values: string[],
  maxVisible = 3
): OverflowSummary => summarizeValueList(values, maxVisible)

export const buildScopeTooltipLines = (
  scope: JobScope,
  catalog: ScopeNameCatalog,
  t: Translator,
  maxVisiblePerSection = 3
): string[] => {
  const lines: string[] = []

  const sourceNames = resolveNames(scope.sources, catalog.sources)
  const groupNames = resolveNames(scope.groups, catalog.groups)
  const tagNames = scope.tags || []

  if (sourceNames.length > 0) {
    const summary = summarizeOverflowList(sourceNames, maxVisiblePerSection)
    lines.push(`${t("watchlists:jobs.scope.sources", "Feeds")}: ${summary.text}`)
  }
  if (groupNames.length > 0) {
    const summary = summarizeOverflowList(groupNames, maxVisiblePerSection)
    lines.push(`${t("watchlists:jobs.scope.groups", "Groups")}: ${summary.text}`)
  }
  if (tagNames.length > 0) {
    const summary = summarizeOverflowList(tagNames, maxVisiblePerSection)
    lines.push(`${t("watchlists:jobs.scope.tags", "Tags")}: ${summary.text}`)
  }

  if (lines.length === 0) {
    lines.push(t("watchlists:jobs.noFeeds", "No feeds selected"))
  }

  return lines
}

export interface FilterSummary {
  count: number
  preview: string
  tooltipLines: string[]
}

export const summarizeFilters = (
  filters: WatchlistFilter[] | undefined,
  t: Translator
): FilterSummary => {
  const list = Array.isArray(filters) ? filters : []
  if (list.length === 0) {
    return { count: 0, preview: "-", tooltipLines: [] }
  }

  const tooltipLines = list.map((filter) => {
    const actionLabel = filterActionLabel(filter.action, t)
    const typeLabel = filterTypeLabel(filter.type, t)
    const valueSummary = extractFilterValueSummary(filter)
    return valueSummary
      ? `${actionLabel} ${typeLabel}: ${valueSummary}`
      : `${actionLabel} ${typeLabel}`
  })

  const preview =
    list.length === 1
      ? tooltipLines[0]
      : `${tooltipLines[0]} (${list.length - 1} more)`

  return {
    count: list.length,
    preview,
    tooltipLines
  }
}
