import { clampBulkPriority } from "./worldBookBulkActionUtils"

export type WorldBookImportFormat = "tldw" | "sillytavern" | "kobold" | "unknown"

export type NormalizedWorldBookImportPayload = {
  world_book: {
    name: string
    description?: string
    scan_depth?: number
    token_budget?: number
    recursive_scanning?: boolean
    enabled?: boolean
  }
  entries: Array<{
    keywords: string[]
    content: string
    priority?: number
    enabled?: boolean
    case_sensitive?: boolean
    regex_match?: boolean
    whole_word_match?: boolean
    appendable?: boolean
  }>
}

export type WorldBookImportConversionResult = {
  format: WorldBookImportFormat
  payload?: NormalizedWorldBookImportPayload
  warnings: string[]
  error?: string
}

export const WORLD_BOOK_IMPORT_MERGE_HELP_TEXT =
  "When enabled, if a world book with the same name already exists, imported entries are added to it. Existing entries are not removed or modified."

const isRecord = (value: unknown): value is Record<string, any> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const toKeywordList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || "").trim()).filter(Boolean)
  }
  if (typeof value === "string") {
    return value
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean)
  }
  return []
}

const normalizeWorldBookDefaults = (
  worldBook: Record<string, any>,
  fallbackName: string
): NormalizedWorldBookImportPayload["world_book"] => {
  const name = String(worldBook?.name || "").trim() || fallbackName
  return {
    name,
    description:
      typeof worldBook?.description === "string" ? worldBook.description : undefined,
    scan_depth:
      typeof worldBook?.scan_depth === "number" && Number.isFinite(worldBook.scan_depth)
        ? worldBook.scan_depth
        : 3,
    token_budget:
      typeof worldBook?.token_budget === "number" && Number.isFinite(worldBook.token_budget)
        ? worldBook.token_budget
        : 500,
    recursive_scanning:
      typeof worldBook?.recursive_scanning === "boolean"
        ? worldBook.recursive_scanning
        : false,
    enabled: typeof worldBook?.enabled === "boolean" ? worldBook.enabled : true
  }
}

const normalizeEntryPayload = (entry: Record<string, any>): NormalizedWorldBookImportPayload["entries"][number] | null => {
  const keywords = toKeywordList(entry?.keywords)
  const content = typeof entry?.content === "string" ? entry.content : String(entry?.content || "")
  if (keywords.length === 0 || !content.trim()) return null

  return {
    keywords,
    content,
    priority: clampBulkPriority(entry?.priority, 50),
    enabled: typeof entry?.enabled === "boolean" ? entry.enabled : true,
    case_sensitive: Boolean(entry?.case_sensitive),
    regex_match: Boolean(entry?.regex_match),
    whole_word_match:
      typeof entry?.whole_word_match === "boolean" ? entry.whole_word_match : true,
    appendable:
      typeof entry?.appendable === "boolean" ? entry.appendable : undefined
  }
}

const normalizeSillyTavernEntry = (
  entry: Record<string, any>,
  index: number,
  warnings: string[]
): NormalizedWorldBookImportPayload["entries"][number] | null => {
  const keywords = [
    ...toKeywordList(entry?.key),
    ...toKeywordList(entry?.keys),
    ...toKeywordList(entry?.keysecondary)
  ]
  const uniqueKeywords = Array.from(new Set(keywords))
  const content = typeof entry?.content === "string" ? entry.content : ""
  if (uniqueKeywords.length === 0 || !content.trim()) {
    warnings.push(`Skipped SillyTavern entry ${index + 1}: missing keywords or content.`)
    return null
  }
  if (entry?.selective) {
    warnings.push(
      `SillyTavern entry ${index + 1} uses selective matching. Imported as standard keyword match.`
    )
  }
  return {
    keywords: uniqueKeywords,
    content,
    priority: clampBulkPriority(entry?.order ?? entry?.priority, 50),
    enabled: entry?.disable === true ? false : entry?.enabled !== false,
    case_sensitive: Boolean(entry?.case_sensitive),
    regex_match: Boolean(entry?.regex),
    whole_word_match:
      typeof entry?.match_whole_words === "boolean" ? entry.match_whole_words : true
  }
}

const normalizeKoboldEntry = (
  entry: Record<string, any>,
  index: number,
  warnings: string[]
): NormalizedWorldBookImportPayload["entries"][number] | null => {
  const keywords = [
    ...toKeywordList(entry?.key),
    ...toKeywordList(entry?.keys),
    ...toKeywordList(entry?.keyword),
    ...toKeywordList(entry?.keysecondary)
  ]
  const uniqueKeywords = Array.from(new Set(keywords))
  const content = typeof entry?.content === "string" ? entry.content : ""
  if (uniqueKeywords.length === 0 || !content.trim()) {
    warnings.push(`Skipped Kobold entry ${index + 1}: missing keywords or content.`)
    return null
  }
  if (entry?.constant === true) {
    warnings.push(
      `Kobold entry ${index + 1} is marked constant. Constant behavior is not preserved in world books.`
    )
  }
  return {
    keywords: uniqueKeywords,
    content,
    priority: clampBulkPriority(entry?.order ?? entry?.priority, 50),
    enabled: entry?.disable === true ? false : true,
    case_sensitive: Boolean(entry?.case_sensitive),
    regex_match: Boolean(entry?.regex),
    whole_word_match:
      typeof entry?.whole_word === "boolean" ? entry.whole_word : true
  }
}

export const detectWorldBookImportFormat = (raw: unknown): WorldBookImportFormat => {
  if (!isRecord(raw)) return "unknown"

  if (isRecord(raw.world_book) && Array.isArray(raw.entries)) return "tldw"

  const dataNode = isRecord(raw.data) ? raw.data : null
  const sillyBook = isRecord(dataNode?.character_book)
    ? dataNode?.character_book
    : isRecord(raw.character_book)
      ? raw.character_book
      : null
  if (
    sillyBook &&
    (Array.isArray(sillyBook.entries) || isRecord(sillyBook.entries))
  ) {
    return "sillytavern"
  }

  if (isRecord(raw.world_info) || isRecord(raw.entries) || Array.isArray(raw.entries)) {
    const worldInfoEntries = isRecord(raw.world_info) ? raw.world_info.entries : null
    if (
      isRecord(raw.entries) ||
      Array.isArray(raw.entries) ||
      isRecord(worldInfoEntries) ||
      Array.isArray(worldInfoEntries)
    ) {
      return "kobold"
    }
  }

  if (Array.isArray(raw.entries) && raw.entries.every((entry) => isRecord(entry) && "keywords" in entry)) {
    return "tldw"
  }

  return "unknown"
}

export const convertWorldBookImport = (raw: unknown): WorldBookImportConversionResult => {
  const warnings: string[] = []
  const format = detectWorldBookImportFormat(raw)
  if (!isRecord(raw) || format === "unknown") {
    return {
      format: "unknown",
      warnings: [],
      error: "Unsupported import format. Expected tldw, SillyTavern, or Kobold JSON."
    }
  }

  if (format === "tldw") {
    const sourceEntries = Array.isArray(raw.entries) ? raw.entries : []
    const normalizedEntries = sourceEntries
      .map((entry) => (isRecord(entry) ? normalizeEntryPayload(entry) : null))
      .filter((entry): entry is NonNullable<typeof entry> => entry != null)
    if (normalizedEntries.length !== sourceEntries.length) {
      warnings.push("Some entries were skipped because they were missing keywords or content.")
    }
    const worldBookSource = isRecord(raw.world_book) ? raw.world_book : raw
    const worldBook = normalizeWorldBookDefaults(worldBookSource, "Imported World Book")
    return {
      format,
      warnings,
      payload: {
        world_book: worldBook,
        entries: normalizedEntries
      }
    }
  }

  if (format === "sillytavern") {
    const dataNode = isRecord(raw.data) ? raw.data : null
    const sillyBook = isRecord(dataNode?.character_book)
      ? dataNode?.character_book
      : isRecord(raw.character_book)
        ? raw.character_book
        : {}
    const entrySource = Array.isArray(sillyBook.entries)
      ? sillyBook.entries
      : isRecord(sillyBook.entries)
        ? Object.values(sillyBook.entries)
        : []
    const entries = entrySource
      .map((entry, index) =>
        isRecord(entry) ? normalizeSillyTavernEntry(entry, index, warnings) : null
      )
      .filter((entry): entry is NonNullable<typeof entry> => entry != null)
    const worldBook = normalizeWorldBookDefaults(
      {
        name: sillyBook?.name || dataNode?.name || raw?.name,
        description: sillyBook?.description || "Imported from SillyTavern",
        scan_depth: sillyBook?.scan_depth,
        token_budget: sillyBook?.token_budget
      },
      "Imported SillyTavern Lorebook"
    )
    return { format, warnings, payload: { world_book: worldBook, entries } }
  }

  const worldInfoRoot = isRecord(raw.world_info) ? raw.world_info : raw
  const entrySourceRaw =
    isRecord(worldInfoRoot.entries) || Array.isArray(worldInfoRoot.entries)
      ? worldInfoRoot.entries
      : raw.entries

  const entrySource = Array.isArray(entrySourceRaw)
    ? entrySourceRaw
    : isRecord(entrySourceRaw)
      ? Object.values(entrySourceRaw)
      : []
  const entries = entrySource
    .map((entry, index) => (isRecord(entry) ? normalizeKoboldEntry(entry, index, warnings) : null))
    .filter((entry): entry is NonNullable<typeof entry> => entry != null)
  const worldBook = normalizeWorldBookDefaults(
    {
      name: worldInfoRoot?.name || raw?.name,
      description: "Imported from Kobold World Info"
    },
    "Imported Kobold World Info"
  )
  return { format, warnings, payload: { world_book: worldBook, entries } }
}

export const getWorldBookImportFormatLabel = (format: WorldBookImportFormat): string => {
  if (format === "tldw") return "tldw JSON"
  if (format === "sillytavern") return "SillyTavern"
  if (format === "kobold") return "Kobold World Info"
  return "Unknown"
}

export const getWorldBookImportJsonErrorMessage = (error: unknown): string => {
  const message = String((error as any)?.message || "").toLowerCase()
  if (message.includes("unexpected end")) {
    return "File is not valid JSON (it appears truncated)."
  }
  if (message.includes("unexpected token")) {
    return "File is not valid JSON (check for trailing commas or invalid characters)."
  }
  return "File is not valid JSON."
}

export const validateWorldBookImportConversion = (
  raw: unknown,
  conversion: WorldBookImportConversionResult
): string | null => {
  if (isRecord(raw)) {
    const hasWorldBookField = isRecord(raw.world_book)
    const looksLikeNativeEntriesWithoutWorldBook =
      !hasWorldBookField &&
      Array.isArray(raw.entries) &&
      raw.entries.some((entry) => isRecord(entry) && "keywords" in entry)

    if (looksLikeNativeEntriesWithoutWorldBook) {
      return "File is missing the 'world_book' field."
    }
  }

  if (!conversion.payload) {
    if (isRecord(raw)) {
      const hasWorldBookField = isRecord(raw.world_book)
      const hasSillyTavernShape =
        (isRecord(raw.data) && isRecord((raw.data as any).character_book)) ||
        isRecord(raw.character_book)
      const hasKoboldShape = isRecord(raw.world_info)

      if (!hasWorldBookField && !hasSillyTavernShape && !hasKoboldShape) {
        return "File is missing the 'world_book' field."
      }
    }
    return conversion.error || "Unsupported import format. Expected tldw, SillyTavern, or Kobold JSON."
  }

  const name = String(conversion.payload?.world_book?.name || "").trim()
  if (!name) {
    return "File is missing world_book.name."
  }

  const entries = Array.isArray(conversion.payload?.entries)
    ? conversion.payload.entries
    : []
  if (entries.length === 0) {
    return "File is missing entries (found 0 entries)."
  }

  return null
}
