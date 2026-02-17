type CharacterSearchFilterOptions = {
  query?: string
  tags?: string[]
  matchAllTags?: boolean
}

const normalizeText = (value: unknown): string =>
  typeof value === "string" ? value.trim().toLowerCase() : ""

const normalizeCharacterTags = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value
      .map((tag) => normalizeText(tag))
      .filter((tag) => tag.length > 0)
  }

  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return []
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        return parsed
          .map((tag) => normalizeText(tag))
          .filter((tag) => tag.length > 0)
      }
    } catch {
      // Use the raw string as a single tag when it is not JSON.
    }
    return [trimmed.toLowerCase()]
  }

  return []
}

export const filterCharactersForWorkspace = <T extends Record<string, unknown>>(
  characters: T[],
  options: CharacterSearchFilterOptions
): T[] => {
  const query = normalizeText(options.query)
  const activeTags = (options.tags || [])
    .map((tag) => normalizeText(tag))
    .filter((tag) => tag.length > 0)

  return characters.filter((character) => {
    const tags = normalizeCharacterTags(character.tags)
    const searchable = [
      normalizeText(character.name),
      normalizeText(character.title),
      normalizeText(character.slug),
      normalizeText(character.description),
      tags.join(" ")
    ]

    const matchesQuery =
      query.length === 0 || searchable.some((value) => value.includes(query))

    const matchesTags =
      activeTags.length === 0 ||
      (options.matchAllTags
        ? activeTags.every((tag) => tags.includes(tag))
        : activeTags.some((tag) => tags.includes(tag)))

    return matchesQuery && matchesTags
  })
}

