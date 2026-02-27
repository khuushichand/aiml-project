import type {
  WritingWorldInfoEntry,
  WritingWorldInfoSettings
} from "./writing-context-utils"

export type WritingWorldInfoImportMode = "replace" | "append"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const toString = (value: unknown): string =>
  typeof value === "string" ? value : ""

const toBoolean = (value: unknown, fallback: boolean): boolean => {
  if (typeof value === "boolean") return value
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase()
    if (normalized === "true") return true
    if (normalized === "false") return false
  }
  return fallback
}

const toSearchRange = (value: unknown): number | undefined => {
  if (value == null || value === "") return undefined
  const parsed = typeof value === "number" ? value : Number(value)
  if (!Number.isFinite(parsed)) return undefined
  return Math.max(0, Math.floor(parsed))
}

const parseKeys = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((entry) => String(entry || "").trim()).filter(Boolean)
  }
  if (typeof value === "string") {
    return value
      .split(/[\n,]+/)
      .map((entry) => entry.trim())
      .filter(Boolean)
  }
  return []
}

const normalizeEntry = (
  raw: unknown,
  index: number
): WritingWorldInfoEntry | null => {
  if (!isRecord(raw)) return null

  const keys = [
    ...parseKeys(raw.keys ?? raw.key),
    ...parseKeys(raw.keysecondary ?? raw.keys_secondary)
  ].filter(Boolean)
  const content = toString(raw.content ?? raw.text).trim()
  if (!content || keys.length === 0) return null

  const disableFlag = toBoolean(raw.disable, false)
  const enabled = toBoolean(raw.enabled, !disableFlag)

  return {
    id:
      toString(raw.id).trim() ||
      toString(raw.uid).trim() ||
      `imported-${index + 1}`,
    enabled,
    keys,
    content,
    use_regex: toBoolean(raw.use_regex ?? raw.useRegex ?? raw.regex, false),
    case_sensitive: toBoolean(
      raw.case_sensitive ?? raw.caseSensitive,
      false
    ),
    search_range: toSearchRange(raw.search_range ?? raw.searchRange ?? raw.search ?? raw.scanDepth)
  }
}

const buildUniqueEntryId = (
  existingIds: Set<string>,
  preferred: string,
  fallbackIndex: number
): string => {
  const base = preferred.trim() || `imported-${fallbackIndex + 1}`
  if (!existingIds.has(base)) {
    existingIds.add(base)
    return base
  }
  let suffix = 2
  let next = `${base}-${suffix}`
  while (existingIds.has(next)) {
    suffix += 1
    next = `${base}-${suffix}`
  }
  existingIds.add(next)
  return next
}

const extractEntriesSource = (value: unknown): unknown[] => {
  if (Array.isArray(value)) return value
  if (!isRecord(value)) return []

  if (isRecord(value.world_info)) {
    const nestedEntries = value.world_info.entries
    if (Array.isArray(nestedEntries)) return nestedEntries
    if (isRecord(nestedEntries)) {
      return Object.values(nestedEntries).map((entry) => {
        if (!isRecord(entry)) return entry
        return {
          content: entry.content,
          keys: entry.key,
          search: entry.scanDepth
        }
      })
    }
  }

  const entries = value.entries
  if (Array.isArray(entries)) return entries
  if (isRecord(entries)) {
    return Object.values(entries).map((entry) => {
      if (!isRecord(entry)) return entry
      return {
        uid: entry.uid,
        id: entry.id,
        content: entry.content,
        keys: entry.key,
        keysecondary: entry.keysecondary,
        search: entry.scanDepth,
        disable: entry.disable,
        enabled: entry.enabled,
        use_regex: entry.use_regex,
        case_sensitive: entry.case_sensitive
      }
    })
  }

  return []
}

export const parseWorldInfoImportPayload = (
  value: unknown
): {
  value: Partial<WritingWorldInfoSettings> | null
  error: string | null
} => {
  if (!isRecord(value) && !Array.isArray(value)) {
    return {
      value: null,
      error: "World info import payload must be an object or array."
    }
  }

  const root = isRecord(value)
    ? isRecord(value.world_info)
      ? value.world_info
      : value
    : {}

  const entries = extractEntriesSource(value)
    .map((entry, index) => normalizeEntry(entry, index))
    .filter(Boolean) as WritingWorldInfoEntry[]

  if (entries.length === 0) {
    return {
      value: null,
      error: "No valid world info entries found in import payload."
    }
  }

  return {
    value: {
      entries,
      prefix: toString(root.prefix),
      suffix: toString(root.suffix),
      search_range: toSearchRange(root.search_range ?? root.searchRange)
    },
    error: null
  }
}

export const buildWorldInfoExportPayload = (
  worldInfo: WritingWorldInfoSettings
): {
  version: 1
  world_info: {
    enabled: boolean
    prefix: string
    suffix: string
    search_range: number
    entries: Array<{
      id: string
      enabled: boolean
      keys: string[]
      content: string
      use_regex: boolean
      case_sensitive: boolean
      search_range?: number
    }>
  }
} => {
  return {
    version: 1,
    world_info: {
      enabled: Boolean(worldInfo.enabled),
      prefix: toString(worldInfo.prefix),
      suffix: toString(worldInfo.suffix),
      search_range: Math.max(0, Math.floor(worldInfo.search_range || 0)),
      entries: (Array.isArray(worldInfo.entries) ? worldInfo.entries : []).map(
        (entry, index) => ({
          id: toString(entry.id).trim() || `entry-${index + 1}`,
          enabled: Boolean(entry.enabled),
          keys: parseKeys(entry.keys),
          content: toString(entry.content),
          use_regex: Boolean(entry.use_regex),
          case_sensitive: Boolean(entry.case_sensitive),
          search_range: toSearchRange(entry.search_range)
        })
      )
    }
  }
}

export const applyWorldInfoImport = (
  current: WritingWorldInfoSettings,
  imported: Partial<WritingWorldInfoSettings>,
  mode: WritingWorldInfoImportMode
): WritingWorldInfoSettings => {
  const currentEntries = Array.isArray(current.entries) ? current.entries : []
  const importedEntries = Array.isArray(imported.entries) ? imported.entries : []

  const seedEntries = mode === "append" ? currentEntries : []
  const existingIds = new Set(seedEntries.map((entry) => String(entry.id || "")))
  const normalizedImportedEntries = importedEntries.map((entry, index) => {
    const preferredId = String(entry.id || "").trim()
    return {
      ...entry,
      id: buildUniqueEntryId(existingIds, preferredId, index)
    }
  })

  return {
    ...current,
    enabled: true,
    prefix:
      typeof imported.prefix === "string" ? imported.prefix : current.prefix,
    suffix:
      typeof imported.suffix === "string" ? imported.suffix : current.suffix,
    search_range:
      typeof imported.search_range === "number"
        ? Math.max(0, Math.floor(imported.search_range))
        : current.search_range,
    entries:
      mode === "append"
        ? [...seedEntries, ...normalizedImportedEntries]
        : normalizedImportedEntries
  }
}
