import { describe, expect, it } from "vitest"
import { buildGlobalWorldBookStatistics } from "../worldBookGlobalStatsUtils"

describe("worldBookGlobalStatsUtils", () => {
  it("aggregates totals and cross-book conflicts", () => {
    const worldBooks = [
      { id: 1, name: "Arcana", token_budget: 100 },
      { id: 2, name: "Bestiary", token_budget: 150 }
    ]
    const entriesByBook = {
      1: [
        { keywords: ["dragon", "magic"], content: "Arcana dragon lore" },
        { keywords: ["city"], content: "Arcana city lore" }
      ],
      2: [
        { keywords: ["dragon"], content: "Bestiary dragon taxonomy" },
        { keywords: ["forest"], content: "Bestiary forest lore" }
      ]
    }

    const stats = buildGlobalWorldBookStatistics(worldBooks, entriesByBook)
    expect(stats.totalBooks).toBe(2)
    expect(stats.totalEntries).toBe(4)
    expect(stats.totalKeywords).toBe(5)
    expect(stats.totalTokenBudget).toBe(250)
    expect(stats.sharedKeywordCount).toBe(1)
    expect(stats.conflictKeywordCount).toBe(1)
    expect(stats.conflicts[0]).toEqual(
      expect.objectContaining({
        keyword: "dragon",
        worldBookIds: [1, 2],
        variantCount: 2
      })
    )
    expect(stats.conflicts[0].affectedBooks).toEqual([
      { id: 1, name: "Arcana" },
      { id: 2, name: "Bestiary" }
    ])
  })

  it("handles large datasets in a performance sanity bound", () => {
    const worldBooks = Array.from({ length: 200 }, (_, index) => ({
      id: index + 1,
      name: `Book ${index + 1}`,
      token_budget: 500
    }))

    const entriesByBook: Record<number, unknown> = {}
    worldBooks.forEach((book, index) => {
      entriesByBook[book.id] = Array.from({ length: 80 }, (_, entryIndex) => ({
        keywords: [
          `kw-${entryIndex % 20}`,
          `kw-shared-${entryIndex % 10}`,
          `kw-book-${index}`
        ],
        content: `Lore ${index}-${entryIndex} ${"x".repeat(120)}`
      }))
    })

    const start = Date.now()
    const stats = buildGlobalWorldBookStatistics(worldBooks, entriesByBook)
    const elapsedMs = Date.now() - start

    expect(stats.totalBooks).toBe(200)
    expect(stats.totalEntries).toBe(16000)
    expect(stats.totalKeywords).toBe(48000)
    expect(stats.conflictKeywordCount).toBeGreaterThan(0)
    expect(elapsedMs).toBeLessThan(3000)
  })
})
