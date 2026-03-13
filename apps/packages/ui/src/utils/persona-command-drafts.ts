export type DraftAssistSuggestion = {
  id: string
  label: string
  suggestedPhrase: string
  suggestedSlotMap: Record<string, string>
}

const normalizePhrase = (phrase: string): string =>
  String(phrase || "")
    .trim()
    .replace(/\s+/g, " ")

const isDurationValue = (value: string): boolean =>
  /\b\d+\s+(?:seconds?|minutes?|hours?|days?)\b/i.test(value.trim())

const buildTrailingCueSuggestion = (
  phrase: string,
  cueWord: "for" | "about" | "with",
  placeholder: "topic" | "content",
  suggestedSlotMap: Record<string, string>
): DraftAssistSuggestion | null => {
  const token = ` ${cueWord} `
  const normalizedPhrase = normalizePhrase(phrase)
  const lowerPhrase = normalizedPhrase.toLowerCase()
  const cueIndex = lowerPhrase.lastIndexOf(token)
  if (cueIndex === -1) return null

  const value = normalizedPhrase.slice(cueIndex + token.length).trim()
  if (!value || value.startsWith("{")) return null
  if (placeholder === "topic" && isDurationValue(value)) return null

  const prefix = normalizedPhrase.slice(0, cueIndex + token.length)
  return {
    id: placeholder,
    label: `Use {${placeholder}}`,
    suggestedPhrase: `${prefix}{${placeholder}}`,
    suggestedSlotMap
  }
}

const buildDurationSuggestion = (
  phrase: string
): DraftAssistSuggestion | null => {
  const normalizedPhrase = normalizePhrase(phrase)
  const match = normalizedPhrase.match(
    /\b\d+\s+(?:seconds?|minutes?|hours?|days?)\b/i
  )
  if (!match || !match[0] || match[0].startsWith("{")) return null

  return {
    id: "duration",
    label: "Use {duration}",
    suggestedPhrase: normalizedPhrase.replace(match[0], "{duration}"),
    suggestedSlotMap: { duration: "duration" }
  }
}

export const buildDraftAssistSuggestions = (
  phrase: string
): DraftAssistSuggestion[] => {
  const normalizedPhrase = normalizePhrase(phrase)
  if (!normalizedPhrase) return []

  const suggestions = [
    buildTrailingCueSuggestion(normalizedPhrase, "for", "topic", {
      query: "topic"
    }),
    buildTrailingCueSuggestion(normalizedPhrase, "about", "topic", {
      query: "topic"
    }),
    buildTrailingCueSuggestion(normalizedPhrase, "with", "content", {
      content: "content"
    }),
    buildDurationSuggestion(normalizedPhrase)
  ].filter((value): value is DraftAssistSuggestion => Boolean(value))

  const seen = new Set<string>()
  return suggestions.filter((suggestion) => {
    const key = `${suggestion.suggestedPhrase}::${JSON.stringify(
      suggestion.suggestedSlotMap
    )}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
