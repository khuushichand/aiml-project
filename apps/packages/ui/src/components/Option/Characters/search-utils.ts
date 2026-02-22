type CharacterSearchFilterOptions = {
  query?: string
  tags?: string[]
  matchAllTags?: boolean
  creator?: string
}

export type CharacterWorkspaceSortBy =
  | "name"
  | "creator"
  | "created_at"
  | "updated_at"
  | "last_used_at"
  | "conversation_count"

export type CharacterWorkspaceSortOrder = "asc" | "desc"

type CharacterSortOptions = {
  sortBy?: CharacterWorkspaceSortBy
  sortOrder?: CharacterWorkspaceSortOrder
}

type CharacterPaginationOptions = {
  page?: number
  pageSize?: number
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

const toComparableString = (value: unknown): string => normalizeText(value)

const resolveCharacterTimestamp = (
  character: Record<string, unknown>,
  keys: string[]
): number => {
  for (const key of keys) {
    const raw = character?.[key]
    if (!raw) continue
    if (typeof raw === "number" && Number.isFinite(raw)) return raw
    const parsed = new Date(String(raw)).getTime()
    if (Number.isFinite(parsed)) return parsed
  }
  return 0
}

const resolveConversationCount = (character: Record<string, unknown>): number => {
  const candidates = [
    character?.conversation_count,
    character?.conversationCount,
    character?.chat_count,
    character?.chatCount
  ]
  for (const candidate of candidates) {
    if (typeof candidate === "number" && Number.isFinite(candidate)) {
      return candidate
    }
  }
  return 0
}

const resolveNameComparable = (character: Record<string, unknown>): string =>
  toComparableString(character?.name ?? character?.title ?? character?.slug ?? "")

const resolveCreatorComparable = (character: Record<string, unknown>): string =>
  toComparableString(
    character?.creator ?? character?.created_by ?? character?.createdBy ?? ""
  )

export const hasInlineConversationCount = (
  character: Record<string, unknown>
): boolean => resolveConversationCount(character) > 0

export const sortCharactersForWorkspace = <T extends Record<string, unknown>>(
  characters: T[],
  options: CharacterSortOptions
): T[] => {
  const sortBy = options.sortBy || "name"
  const sortOrder = options.sortOrder === "desc" ? "desc" : "asc"
  const direction = sortOrder === "desc" ? -1 : 1

  return [...characters].sort((left, right) => {
    let comparison = 0
    let forceAscendingOrder = false

    switch (sortBy) {
      case "conversation_count":
        comparison =
          resolveConversationCount(left) - resolveConversationCount(right)
        break
      case "created_at":
        comparison =
          resolveCharacterTimestamp(left, [
            "created_at",
            "createdAt",
            "created"
          ]) -
          resolveCharacterTimestamp(right, [
            "created_at",
            "createdAt",
            "created"
          ])
        break
      case "updated_at":
        comparison =
          resolveCharacterTimestamp(left, [
            "updated_at",
            "updatedAt",
            "modified_at",
            "modifiedAt"
          ]) -
          resolveCharacterTimestamp(right, [
            "updated_at",
            "updatedAt",
            "modified_at",
            "modifiedAt"
          ])
        break
      case "last_used_at":
        {
          const leftTimestamp = resolveCharacterTimestamp(left, [
            "last_used_at",
            "lastUsedAt",
            "last_active",
            "lastActive"
          ])
          const rightTimestamp = resolveCharacterTimestamp(right, [
            "last_used_at",
            "lastUsedAt",
            "last_active",
            "lastActive"
          ])
          if (leftTimestamp === 0 && rightTimestamp === 0) {
            comparison = resolveNameComparable(left).localeCompare(
              resolveNameComparable(right)
            )
            forceAscendingOrder = true
          } else {
            comparison = leftTimestamp - rightTimestamp
          }
        }
        break
      case "creator":
        comparison = resolveCreatorComparable(left).localeCompare(
          resolveCreatorComparable(right)
        )
        break
      case "name":
      default:
        comparison = resolveNameComparable(left).localeCompare(
          resolveNameComparable(right)
        )
        break
    }

    if (comparison === 0) {
      comparison = resolveNameComparable(left).localeCompare(
        resolveNameComparable(right)
      )
    }

    if (forceAscendingOrder) {
      return comparison
    }

    return comparison * direction
  })
}

export const paginateCharactersForWorkspace = <T>(
  characters: T[],
  options: CharacterPaginationOptions
): {
  items: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
} => {
  const total = characters.length
  const page = Math.max(1, Number(options.page || 1))
  const pageSize = Math.max(1, Number(options.pageSize || 25))
  const start = (page - 1) * pageSize
  const end = start + pageSize
  const items = characters.slice(start, end)
  return {
    items,
    total,
    page,
    pageSize,
    hasMore: end < total
  }
}

export const filterCharactersForWorkspace = <T extends Record<string, unknown>>(
  characters: T[],
  options: CharacterSearchFilterOptions
): T[] => {
  const query = normalizeText(options.query)
  const activeTags = (options.tags || [])
    .map((tag) => normalizeText(tag))
    .filter((tag) => tag.length > 0)
  const creator = normalizeText(options.creator)

  return characters.filter((character) => {
    const tags = normalizeCharacterTags(character.tags)
    const characterCreator = normalizeText(
      character.creator ?? character.created_by ?? character.createdBy
    )
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
    const matchesCreator = creator.length === 0 || characterCreator === creator

    return matchesQuery && matchesTags && matchesCreator
  })
}
