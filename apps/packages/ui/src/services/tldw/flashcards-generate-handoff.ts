export type FlashcardsGenerateSourceType = "media" | "note" | "message" | "manual"

export type FlashcardsGenerateIntent = {
  text: string
  sourceType?: FlashcardsGenerateSourceType
  sourceId?: string
  sourceTitle?: string
  conversationId?: string
  messageId?: string
}

const MAX_GENERATE_PREFILL_CHARS = 12_000

const toNonEmptyString = (value: unknown): string | undefined => {
  if (typeof value !== "string") return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

const clampGenerateText = (text: string): string => text.slice(0, MAX_GENERATE_PREFILL_CHARS)

const normalizeSourceType = (value: unknown): FlashcardsGenerateSourceType | undefined => {
  if (
    value === "media" ||
    value === "note" ||
    value === "message" ||
    value === "manual"
  ) {
    return value
  }
  return undefined
}

const extractSearchFromHash = (hash: string): string => {
  const questionMarkIndex = hash.indexOf("?")
  if (questionMarkIndex < 0) return ""
  return hash.slice(questionMarkIndex)
}

const toSearchParams = (search: string): URLSearchParams => {
  const normalized = search.startsWith("?") ? search.slice(1) : search
  return new URLSearchParams(normalized)
}

export const parseFlashcardsGenerateIntentFromSearch = (
  search: string
): FlashcardsGenerateIntent | null => {
  const params = toSearchParams(search)
  const hasGenerateSignal = params.get("generate") === "1" || params.has("generate_text")
  if (!hasGenerateSignal) return null

  const text = toNonEmptyString(params.get("generate_text"))
  if (!text) return null

  const sourceType = normalizeSourceType(params.get("generate_source_type")) || "manual"
  const sourceId = toNonEmptyString(params.get("generate_source_id"))
  const sourceTitle = toNonEmptyString(params.get("generate_source_title"))
  const conversationId = toNonEmptyString(params.get("generate_conversation_id"))
  const messageId = toNonEmptyString(params.get("generate_message_id"))

  return {
    text: clampGenerateText(text),
    sourceType,
    sourceId,
    sourceTitle,
    conversationId,
    messageId
  }
}

export const parseFlashcardsGenerateIntentFromLocation = (locationLike: {
  search?: string
  hash?: string
}): FlashcardsGenerateIntent | null => {
  const fromSearch = parseFlashcardsGenerateIntentFromSearch(locationLike.search || "")
  if (fromSearch) return fromSearch

  return parseFlashcardsGenerateIntentFromSearch(
    extractSearchFromHash(locationLike.hash || "")
  )
}

export const buildFlashcardsGenerateRoute = (intent: FlashcardsGenerateIntent): string => {
  const text = toNonEmptyString(intent.text)
  if (!text) {
    return "/flashcards?tab=importExport"
  }

  const params = new URLSearchParams()
  params.set("tab", "importExport")
  params.set("generate", "1")
  params.set("generate_text", clampGenerateText(text))

  const sourceType = normalizeSourceType(intent.sourceType)
  if (sourceType && sourceType !== "manual") {
    params.set("generate_source_type", sourceType)
  }
  const sourceId = toNonEmptyString(intent.sourceId)
  if (sourceId) params.set("generate_source_id", sourceId)

  const sourceTitle = toNonEmptyString(intent.sourceTitle)
  if (sourceTitle) params.set("generate_source_title", sourceTitle)

  const conversationId = toNonEmptyString(intent.conversationId)
  if (conversationId) params.set("generate_conversation_id", conversationId)

  const messageId = toNonEmptyString(intent.messageId)
  if (messageId) params.set("generate_message_id", messageId)

  return `/flashcards?${params.toString()}`
}
