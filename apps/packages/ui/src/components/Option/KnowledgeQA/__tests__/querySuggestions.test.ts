import { describe, expect, it } from "vitest"
import {
  buildLocalQuerySuggestions,
  shouldShowSuggestionPrototype,
} from "../querySuggestions"

describe("querySuggestions", () => {
  it("returns no suggestions when query is below minimum length", () => {
    const suggestions = buildLocalQuerySuggestions({
      query: "a",
      historyQueries: ["alpha report"],
      exampleQueries: ["Analyze alpha findings"],
      sourceTitles: ["Alpha source"],
    })

    expect(suggestions).toEqual([])
    expect(shouldShowSuggestionPrototype("a")).toBe(false)
  })

  it("prioritizes history matches and deduplicates candidates", () => {
    const suggestions = buildLocalQuerySuggestions({
      query: "compare",
      historyQueries: [
        "Compare quarterly earnings",
        "compare quarterly earnings",
      ],
      exampleQueries: ["Compare citations across sources"],
      sourceTitles: ["Comparison table (2025)"],
      limit: 5,
    })

    expect(suggestions.length).toBeGreaterThan(0)
    expect(suggestions[0].source).toBe("history")
    expect(
      suggestions.filter(
        (item) => item.text.toLowerCase() === "compare quarterly earnings"
      )
    ).toHaveLength(1)
  })

  it("enforces suggestion limit bounds", () => {
    const suggestions = buildLocalQuerySuggestions({
      query: "source",
      historyQueries: ["Source one", "Source two", "Source three", "Source four"],
      exampleQueries: ["Source five", "Source six"],
      sourceTitles: ["Source seven", "Source eight"],
      limit: 3,
    })

    expect(suggestions).toHaveLength(3)
  })
})
