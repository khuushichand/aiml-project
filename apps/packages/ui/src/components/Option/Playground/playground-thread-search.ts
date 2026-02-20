export type ThreadSearchDirection = 1 | -1

export type ThreadSearchMessage = {
  message?: string | null
}

export const normalizeThreadSearchQuery = (value: string): string =>
  value.trim().toLowerCase()

export const collectThreadSearchMatches = (
  messages: ThreadSearchMessage[],
  query: string
): number[] => {
  const needle = normalizeThreadSearchQuery(query)
  if (!needle) return []

  const matches: number[] = []
  messages.forEach((entry, index) => {
    const content =
      typeof entry?.message === "string" ? entry.message.toLowerCase() : ""
    if (content.includes(needle)) {
      matches.push(index)
    }
  })
  return matches
}

export const getWrappedMatchIndex = (
  currentIndex: number,
  totalMatches: number,
  direction: ThreadSearchDirection
): number => {
  if (totalMatches <= 0) return 0
  const normalizedCurrent =
    currentIndex >= 0 && currentIndex < totalMatches ? currentIndex : 0
  return (normalizedCurrent + direction + totalMatches) % totalMatches
}
