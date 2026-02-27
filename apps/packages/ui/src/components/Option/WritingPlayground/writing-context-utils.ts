import type { ChatMessage } from "@/services/tldw/TldwApiClient"

export type WritingContextBlock = {
  enabled: boolean
  prefix: string
  text: string
  suffix: string
}

export type WritingAuthorNote = WritingContextBlock & {
  insertion_depth: number
}

export type WritingWorldInfoEntry = {
  id: string
  enabled: boolean
  keys: string[]
  content: string
  use_regex: boolean
  case_sensitive: boolean
  search_range?: number
}

export type WritingWorldInfoSettings = {
  enabled: boolean
  search_range: number
  prefix: string
  suffix: string
  entries: WritingWorldInfoEntry[]
}

export type WritingContextSettings = {
  memory_block: WritingContextBlock
  author_note: WritingAuthorNote
  world_info: WritingWorldInfoSettings
}

const formatBlock = (block: WritingContextBlock): string | null => {
  if (!block.enabled) return null
  const text = block.text.trim()
  if (!text) return null
  return `${block.prefix || ""}${text}${block.suffix || ""}`.trim()
}

const normalizeSearchRange = (value: number): number =>
  Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0

const matchWorldInfoKey = (
  haystack: string,
  key: string,
  useRegex: boolean,
  caseSensitive: boolean
): boolean => {
  const needle = String(key || "").trim()
  if (!needle) return false
  if (useRegex) {
    try {
      const regex = new RegExp(needle, caseSensitive ? "" : "i")
      return regex.test(haystack)
    } catch {
      return false
    }
  }
  if (!caseSensitive) {
    return haystack.toLowerCase().includes(needle.toLowerCase())
  }
  return haystack.includes(needle)
}

export const getTriggeredWorldInfoEntries = (
  promptText: string,
  worldInfo: WritingWorldInfoSettings
): WritingWorldInfoEntry[] => {
  if (!worldInfo.enabled || !Array.isArray(worldInfo.entries)) return []
  const baseText = String(promptText || "")
  if (!baseText.trim()) return []
  const defaultSearchRange = normalizeSearchRange(worldInfo.search_range)

  return worldInfo.entries.filter((entry) => {
    if (!entry?.enabled) return false
    const content = String(entry.content || "").trim()
    if (!content) return false
    const entrySearchRange =
      entry.search_range == null
        ? defaultSearchRange
        : normalizeSearchRange(entry.search_range)
    if (entrySearchRange <= 0) return false
    const haystack =
      entrySearchRange > 0 && baseText.length > entrySearchRange
        ? baseText.slice(-entrySearchRange)
        : baseText
    if (!haystack.trim()) return false
    const keys = Array.isArray(entry.keys)
      ? entry.keys.map((key) => String(key || "").trim()).filter(Boolean)
      : []
    if (keys.length === 0) return false
    return keys.some((key) =>
      matchWorldInfoKey(haystack, key, entry.use_regex, entry.case_sensitive)
    )
  })
}

export const buildContextSystemMessages = (
  promptText: string,
  settings: WritingContextSettings
): ChatMessage[] => {
  const messages: ChatMessage[] = []
  const memory = formatBlock(settings.memory_block)
  if (memory) {
    messages.push({ role: "system", content: memory })
  }

  const triggeredWorldInfo = getTriggeredWorldInfoEntries(
    promptText,
    settings.world_info
  )
  if (triggeredWorldInfo.length > 0) {
    const worldInfoPrefix = settings.world_info.prefix || ""
    const worldInfoSuffix = settings.world_info.suffix || ""
    const body = triggeredWorldInfo
      .map((entry, index) => {
        const keys = entry.keys.join(", ")
        const content = entry.content.trim()
        const withAffixes = `${worldInfoPrefix}${content}${worldInfoSuffix}`.trim()
        return `${index + 1}. Keys: ${keys}\n${withAffixes}`
      })
      .join("\n\n")
    messages.push({
      role: "system",
      content: `World info context:\n${body}`
    })
  }

  const authorNoteText = formatBlock(settings.author_note)
  if (authorNoteText) {
    const depth = Math.max(1, Math.floor(settings.author_note.insertion_depth || 1))
    messages.push({
      role: "system",
      content: `${authorNoteText}\n\n(Author note depth: ${depth})`
    })
  }

  return messages
}

export const injectSystemMessages = (
  baseMessages: ChatMessage[],
  extraSystemMessages: ChatMessage[]
): ChatMessage[] => {
  if (extraSystemMessages.length === 0) return baseMessages
  const firstNonSystem = baseMessages.findIndex((msg) => msg.role !== "system")
  if (firstNonSystem <= 0) {
    return [...extraSystemMessages, ...baseMessages]
  }
  return [
    ...baseMessages.slice(0, firstNonSystem),
    ...extraSystemMessages,
    ...baseMessages.slice(firstNonSystem)
  ]
}

export const parseWorldInfoKeysInput = (value: string): string[] =>
  value
    .split(/[\n,]+/)
    .map((entry) => entry.trim())
    .filter(Boolean)
