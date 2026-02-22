import { describe, expect, it } from "vitest"
import {
  estimateEntryTokens,
  formatEntryContentStats,
  getPriorityBand,
  getPriorityTagColor,
  normalizeKeywordList,
  validateRegexKeywords
} from "../worldBookEntryUtils"

describe("worldBookEntryUtils", () => {
  it("normalizes keyword inputs from string and array values", () => {
    expect(normalizeKeywordList("alpha, beta , gamma")).toEqual(["alpha", "beta", "gamma"])
    expect(normalizeKeywordList(["alpha", " beta ", "", "gamma"])).toEqual([
      "alpha",
      "beta",
      "gamma"
    ])
  })

  it("estimates tokens and formats content stats", () => {
    expect(estimateEntryTokens("abcd")).toBe(1)
    expect(estimateEntryTokens("abcdefghij")).toBe(3)
    expect(formatEntryContentStats("abcdefghij")).toBe("10 chars / ~3 tokens")
  })

  it("maps priority to visual bands", () => {
    expect(getPriorityBand(10)).toBe("low")
    expect(getPriorityBand(34)).toBe("medium")
    expect(getPriorityBand(67)).toBe("high")
    expect(getPriorityTagColor("low")).toBe("default")
    expect(getPriorityTagColor("medium")).toBe("blue")
    expect(getPriorityTagColor("high")).toBe("green")
  })

  it("validates regex keyword syntax", () => {
    expect(validateRegexKeywords(["valid.*pattern"])).toBeNull()
    expect(validateRegexKeywords(["[broken"])).toContain("Invalid regex pattern")
  })
})
