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
  context_order?: string
  context_length?: number
  author_note_depth_mode?: "insertion" | "annotation"
}

const formatBlock = (block: WritingContextBlock): string | null => {
  if (!block.enabled) return null
  const text = block.text.trim()
  if (!text) return null
  return `${block.prefix || ""}${text}${block.suffix || ""}`.trim()
}

const DEFAULT_CONTEXT_ORDER =
  "{memPrefix}{wiPrefix}{wiText}{wiSuffix}{memText}{memSuffix}{prompt}"
const DEFAULT_CONTEXT_LENGTH = 8192
const DEFAULT_TOKEN_RATIO = 4

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

const replaceContextPlaceholders = (
  value: string,
  replacements: Record<string, string>
): string =>
  Object.entries(replacements).reduce(
    (current, [placeholder, replacement]) =>
      current.split(placeholder).join(replacement),
    value
  )

const insertAuthorNoteAtDepth = (
  prompt: string,
  authorNote: string,
  depth: number
): string => {
  const normalizedDepth = Math.max(1, Math.floor(depth || 1))
  const lines = prompt.match(/.*\n?/g) ?? [prompt]
  const promptLineCount = prompt.split("\n").length
  const injectionDepth = Math.min(promptLineCount, normalizedDepth)
  const insertionIndex = Math.max(0, lines.length - injectionDepth - 1)
  lines.splice(insertionIndex, 0, authorNote)
  return lines.join("")
}

const normalizeContextLength = (value: number | undefined): number => {
  if (!Number.isFinite(value)) return DEFAULT_CONTEXT_LENGTH
  return Math.max(0, Math.floor(value as number))
}

const normalizeTokenRatio = (value: number | undefined): number => {
  if (!Number.isFinite(value)) return DEFAULT_TOKEN_RATIO
  return Math.max(0.1, value as number)
}

export const composeContextPrompt = (
  promptText: string,
  settings: WritingContextSettings,
  options: { tokenRatio?: number } = {}
): string => {
  const basePrompt = String(promptText || "")
  const worldInfoEntries = getTriggeredWorldInfoEntries(basePrompt, settings.world_info)
  const assembledWorldInfo = worldInfoEntries
    .map((entry) => String(entry.content || "").trim())
    .filter(Boolean)
    .join("\n")

  const memoryText =
    settings.memory_block.enabled && settings.memory_block.text.trim()
      ? settings.memory_block.text.trim()
      : ""
  const hasMemoryOrWorldInfo = Boolean(memoryText || assembledWorldInfo)
  const contextReplacements: Record<string, string> = {
    "{wiPrefix}": assembledWorldInfo ? settings.world_info.prefix || "" : "",
    "{wiText}": assembledWorldInfo,
    "{wiSuffix}": assembledWorldInfo ? settings.world_info.suffix || "" : "",
    "{memPrefix}": hasMemoryOrWorldInfo ? settings.memory_block.prefix || "" : "",
    "{memText}": memoryText,
    "{memSuffix}": hasMemoryOrWorldInfo ? settings.memory_block.suffix || "" : ""
  }

  const additionalContextChars = Object.values(contextReplacements).join("").length
  const tokenRatio = normalizeTokenRatio(options.tokenRatio)
  const contextLength = normalizeContextLength(settings.context_length)
  const promptBudgetChars = Math.max(
    0,
    Math.floor(contextLength * tokenRatio) - additionalContextChars
  )
  const truncatedPrompt =
    contextLength <= 0
      ? basePrompt
      : promptBudgetChars <= 0
        ? ""
        : basePrompt.slice(-promptBudgetChars)

  const authorNote = formatBlock(settings.author_note)
  const authorDepthMode = settings.author_note_depth_mode ?? "insertion"
  const promptWithAuthorNote =
    authorNote && authorDepthMode === "insertion"
      ? insertAuthorNoteAtDepth(
          truncatedPrompt,
          authorNote,
          settings.author_note.insertion_depth
        )
      : truncatedPrompt

  contextReplacements["{prompt}"] = promptWithAuthorNote

  const rawContextOrder =
    typeof settings.context_order === "string" && settings.context_order.trim()
      ? settings.context_order
      : DEFAULT_CONTEXT_ORDER

  const composedContext = rawContextOrder
    .split("\n")
    .map((line) => replaceContextPlaceholders(line, contextReplacements))
    .filter((line) => line.trim() !== "")
    .join("\n")
    .replace(/\\n/g, "\n")

  if (!authorNote || authorDepthMode !== "annotation") {
    return composedContext
  }

  const depth = Math.max(1, Math.floor(settings.author_note.insertion_depth || 1))
  const annotation = `${authorNote}\n\n(Author note depth: ${depth})`
  return [composedContext, annotation].filter(Boolean).join("\n\n")
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
