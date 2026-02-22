import type { SearchHistoryItem } from "./types"

const HISTORY_TRIM_BATCH_SIZE = 10

const isQuotaExceededError = (error: unknown): boolean => {
  const maybeError = error as {
    name?: string
    code?: number
    message?: string
  } | null

  if (!maybeError) return false
  if (maybeError.name === "QuotaExceededError") return true
  if (maybeError.code === 22 || maybeError.code === 1014) return true
  return /quota/i.test(String(maybeError.message || ""))
}

type PersistHistoryResult = {
  storedHistory: SearchHistoryItem[]
  wasTrimmed: boolean
}

export const persistKnowledgeQaHistory = (
  history: SearchHistoryItem[],
  writeSerializedHistory: (serializedHistory: string) => void
): PersistHistoryResult => {
  let candidate = [...history]
  let wasTrimmed = false

  while (true) {
    try {
      writeSerializedHistory(JSON.stringify(candidate))
      return { storedHistory: candidate, wasTrimmed }
    } catch (error) {
      if (!isQuotaExceededError(error) || candidate.length === 0) {
        throw error
      }
      wasTrimmed = true
      candidate = candidate.slice(0, Math.max(0, candidate.length - HISTORY_TRIM_BATCH_SIZE))
    }
  }
}
