import { normalizeKeywordList } from "./worldBookEntryUtils"

export type ReferencedBySignal = {
  sourceEntryId: number
  matchedKeyword: string
}

export type ReferencedBySignalMap = Record<number, ReferencedBySignal[]>

type RelationshipEntryInput = {
  entry_id?: unknown
  keywords?: unknown
  content?: unknown
}

export const buildReferencedBySignalMap = (
  entries: RelationshipEntryInput[]
): ReferencedBySignalMap => {
  const normalized = (Array.isArray(entries) ? entries : [])
    .map((entry) => {
      const id = Number((entry as any)?.entry_id)
      const keywords = normalizeKeywordList((entry as any)?.keywords)
      return {
        id,
        keywords,
        contentLower: String((entry as any)?.content || "").toLowerCase()
      }
    })
    .filter((entry) => Number.isFinite(entry.id) && entry.id > 0)

  const result: ReferencedBySignalMap = {}
  const seenPairs = new Set<string>()

  normalized.forEach((source) => {
    if (!source.contentLower.trim()) return

    normalized.forEach((target) => {
      if (target.id === source.id) return

      const matchedKeyword = target.keywords.find((keyword) => {
        const normalizedKeyword = String(keyword || "").trim().toLowerCase()
        if (normalizedKeyword.length < 2) return false
        return source.contentLower.includes(normalizedKeyword)
      })
      if (!matchedKeyword) return

      const pairKey = `${target.id}:${source.id}`
      if (seenPairs.has(pairKey)) return
      seenPairs.add(pairKey)

      const next = result[target.id] || []
      next.push({
        sourceEntryId: source.id,
        matchedKeyword
      })
      result[target.id] = next
    })
  })

  Object.values(result).forEach((signals) => {
    signals.sort((a, b) => a.sourceEntryId - b.sourceEntryId)
  })

  return result
}
