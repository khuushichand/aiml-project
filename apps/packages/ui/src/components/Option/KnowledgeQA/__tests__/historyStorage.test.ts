import { describe, expect, it, vi } from "vitest"
import { persistKnowledgeQaHistory } from "../historyStorage"
import type { SearchHistoryItem } from "../types"

const makeHistory = (count: number): SearchHistoryItem[] =>
  Array.from({ length: count }).map((_, index) => ({
    id: `h-${index + 1}`,
    query: `query-${index + 1}`,
    timestamp: new Date().toISOString(),
    sourcesCount: 1,
    hasAnswer: true,
  }))

describe("persistKnowledgeQaHistory", () => {
  it("persists full history when storage write succeeds", () => {
    const history = makeHistory(5)
    const writer = vi.fn()

    const result = persistKnowledgeQaHistory(history, writer)

    expect(writer).toHaveBeenCalledTimes(1)
    expect(result.wasTrimmed).toBe(false)
    expect(result.storedHistory).toHaveLength(5)
  })

  it("trims oldest items and retries when storage quota is exceeded", () => {
    const history = makeHistory(25)
    const writer = vi
      .fn()
      .mockImplementationOnce(() => {
        const error = new Error("quota exceeded")
        ;(error as Error & { name: string }).name = "QuotaExceededError"
        throw error
      })
      .mockImplementationOnce(() => undefined)

    const result = persistKnowledgeQaHistory(history, writer)

    expect(writer).toHaveBeenCalledTimes(2)
    expect(result.wasTrimmed).toBe(true)
    expect(result.storedHistory).toHaveLength(15)
    expect(result.storedHistory[0]?.id).toBe("h-1")
    expect(result.storedHistory[result.storedHistory.length - 1]?.id).toBe("h-15")
  })
})
