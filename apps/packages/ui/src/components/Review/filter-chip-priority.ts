const normalizeKeywords = (keywords: string[]): string[] => {
  return Array.from(
    new Set(
      keywords
        .map((keyword) => keyword.trim())
        .filter(Boolean)
    )
  )
}

export const rankKeywordSuggestions = (keywords: string[], query: string): string[] => {
  const normalized = normalizeKeywords(keywords)
  const normalizedQuery = query.trim().toLowerCase()

  if (!normalizedQuery) {
    return normalized.sort((left, right) => left.localeCompare(right))
  }

  const rank = (value: string): number => {
    const lowered = value.toLowerCase()
    if (lowered.startsWith(normalizedQuery)) return 0
    if (lowered.includes(normalizedQuery)) return 1
    return 2
  }

  return normalized.sort((left, right) => {
    const rankDelta = rank(left) - rank(right)
    if (rankDelta !== 0) return rankDelta
    return left.localeCompare(right)
  })
}

