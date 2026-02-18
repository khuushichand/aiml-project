export type CharacterTagOperation = "rename" | "merge" | "delete"

const normalizeTag = (value: unknown): string =>
  typeof value === "string" ? value.trim() : ""

const dedupeTags = (tags: string[]): string[] => {
  const seen = new Set<string>()
  const result: string[] = []

  for (const tag of tags) {
    const normalized = normalizeTag(tag)
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    result.push(normalized)
  }

  return result
}

export const parseCharacterTags = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return dedupeTags(value.map((tag) => normalizeTag(tag)))
  }

  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return []

    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        return dedupeTags(parsed.map((tag) => normalizeTag(tag)))
      }
    } catch {
      // Fall back to treating the raw string as a single tag.
    }

    return dedupeTags([trimmed])
  }

  return []
}

export const buildTagUsage = (
  characters: Array<{ tags?: unknown }>
): Array<{ tag: string; count: number }> => {
  const counts: Record<string, number> = {}

  for (const character of characters) {
    const tags = parseCharacterTags(character?.tags)
    for (const tag of tags) {
      counts[tag] = (counts[tag] || 0) + 1
    }
  }

  return Object.entries(counts)
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => {
      if (b.count !== a.count) return b.count - a.count
      return a.tag.localeCompare(b.tag)
    })
}

export const characterHasTag = (
  character: { tags?: unknown },
  sourceTag: string
): boolean => {
  const source = normalizeTag(sourceTag)
  if (!source) return false
  return parseCharacterTags(character?.tags).includes(source)
}

export const applyTagOperationToTags = (
  existingTags: unknown,
  operation: CharacterTagOperation,
  sourceTag: string,
  targetTag?: string
): string[] => {
  const source = normalizeTag(sourceTag)
  const target = normalizeTag(targetTag)
  const tags = parseCharacterTags(existingTags)

  if (!source) return tags

  if (operation === "delete") {
    return dedupeTags(tags.filter((tag) => tag !== source))
  }

  if (!target) return tags

  return dedupeTags(tags.map((tag) => (tag === source ? target : tag)))
}
