import { estimateEntryTokens, normalizeKeywordList } from "./worldBookEntryUtils"

export type GlobalKeywordConflict = {
  keyword: string
  worldBookIds: number[]
  worldBookNames: string[]
  affectedBooks: Array<{ id: number; name: string }>
  variantCount: number
  occurrenceCount: number
}

export type GlobalWorldBookStatistics = {
  totalBooks: number
  totalEntries: number
  totalKeywords: number
  totalEstimatedTokens: number
  totalTokenBudget: number
  sharedKeywordCount: number
  conflictKeywordCount: number
  conflicts: GlobalKeywordConflict[]
}

type KeywordAccumulator = {
  keyword: string
  worldBookIds: Set<number>
  worldBookNames: Set<string>
  bookNamesById: Map<number, string>
  contentVariants: Set<string>
  occurrenceCount: number
}

export const buildGlobalWorldBookStatistics = (
  worldBooks: unknown,
  entriesByBook: Record<number, unknown>
): GlobalWorldBookStatistics => {
  const books = Array.isArray(worldBooks) ? worldBooks : []
  const keywordMap = new Map<string, KeywordAccumulator>()
  let totalEntries = 0
  let totalKeywords = 0
  let totalEstimatedTokens = 0
  let totalTokenBudget = 0

  for (const rawBook of books as any[]) {
    const worldBookId = Number(rawBook?.id)
    if (!Number.isFinite(worldBookId) || worldBookId <= 0) continue
    const worldBookName = String(rawBook?.name || `World Book ${worldBookId}`)
    const tokenBudget = Number(rawBook?.token_budget)
    if (Number.isFinite(tokenBudget) && tokenBudget > 0) {
      totalTokenBudget += tokenBudget
    }

    const bookEntriesRaw = entriesByBook?.[worldBookId]
    const bookEntries = Array.isArray(bookEntriesRaw) ? bookEntriesRaw : []
    totalEntries += bookEntries.length

    for (const entry of bookEntries as any[]) {
      const keywords = normalizeKeywordList(entry?.keywords)
      const content = String(entry?.content || "")
      totalEstimatedTokens += estimateEntryTokens(content)
      totalKeywords += keywords.length

      for (const keyword of keywords) {
        const normalizedKeyword = keyword.trim().toLowerCase()
        if (!normalizedKeyword) continue
        const current =
          keywordMap.get(normalizedKeyword) ||
          {
            keyword: keyword.trim(),
            worldBookIds: new Set<number>(),
            worldBookNames: new Set<string>(),
            bookNamesById: new Map<number, string>(),
            contentVariants: new Set<string>(),
            occurrenceCount: 0
          }
        current.worldBookIds.add(worldBookId)
        current.worldBookNames.add(worldBookName)
        current.bookNamesById.set(worldBookId, worldBookName)
        current.contentVariants.add(content.trim())
        current.occurrenceCount += 1
        keywordMap.set(normalizedKeyword, current)
      }
    }
  }

  const keywordRows = Array.from(keywordMap.values())
  const sharedKeywords = keywordRows.filter((row) => row.worldBookIds.size > 1)
  const conflicts = keywordRows
    .filter((row) => row.worldBookIds.size > 1 && row.contentVariants.size > 1)
    .map((row) => ({
      keyword: row.keyword,
      worldBookIds: Array.from(row.worldBookIds).sort((a, b) => a - b),
      worldBookNames: Array.from(row.worldBookNames).sort((a, b) => a.localeCompare(b)),
      affectedBooks: Array.from(row.bookNamesById.entries())
        .map(([id, name]) => ({ id, name }))
        .sort((a, b) => a.name.localeCompare(b.name)),
      variantCount: row.contentVariants.size,
      occurrenceCount: row.occurrenceCount
    }))
    .sort((a, b) => {
      if (b.worldBookIds.length !== a.worldBookIds.length) {
        return b.worldBookIds.length - a.worldBookIds.length
      }
      if (b.variantCount !== a.variantCount) {
        return b.variantCount - a.variantCount
      }
      return a.keyword.localeCompare(b.keyword)
    })

  return {
    totalBooks: books.length,
    totalEntries,
    totalKeywords,
    totalEstimatedTokens,
    totalTokenBudget,
    sharedKeywordCount: sharedKeywords.length,
    conflictKeywordCount: conflicts.length,
    conflicts
  }
}
