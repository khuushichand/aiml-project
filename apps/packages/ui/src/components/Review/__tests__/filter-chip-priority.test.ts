import { describe, expect, it } from "vitest"
import { rankKeywordSuggestions } from "../filter-chip-priority"

describe("filter-chip-priority", () => {
  it("ranks startsWith matches before contains matches and non-matches", () => {
    const ranked = rankKeywordSuggestions(
      ["alpha", "beta alpha", "gamma", "alphabet"],
      "alp"
    )

    expect(ranked).toEqual(["alpha", "alphabet", "beta alpha", "gamma"])
  })

  it("deduplicates, trims, and falls back to alphabetical order without query", () => {
    const ranked = rankKeywordSuggestions(
      ["  zeta ", "alpha", "alpha", "beta "],
      ""
    )

    expect(ranked).toEqual(["alpha", "beta", "zeta"])
  })
})

