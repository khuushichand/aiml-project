import { describe, expect, it } from "vitest"

import {
  buildMatchingPairs,
  formatMatchingAnswer,
  isMatchingAnswerCorrect,
  normalizeMatchingAnswerMap
} from "../matchingAnswer"

describe("matchingAnswer", () => {
  it("normalizes object and preserves non-empty pairs", () => {
    expect(normalizeMatchingAnswerMap({
      CPU: "Processor",
      "": "ignored",
      RAM: "Temporary memory"
    })).toEqual({
      CPU: "Processor",
      RAM: "Temporary memory"
    })
  })

  it("grades matching answers case-insensitively with full-set equality", () => {
    expect(isMatchingAnswerCorrect(
      { cpu: "processor", ram: "temporary memory" },
      { CPU: "Processor", RAM: "Temporary memory" }
    )).toBe(true)
    expect(isMatchingAnswerCorrect(
      { cpu: "processor" },
      { CPU: "Processor", RAM: "Temporary memory" }
    )).toBe(false)
  })

  it("builds ordered matching rows and formats answer text", () => {
    expect(buildMatchingPairs(
      ["RAM", "CPU"],
      { CPU: "Processor", RAM: "Temporary memory" }
    )).toEqual([
      { left: "RAM", right: "Temporary memory" },
      { left: "CPU", right: "Processor" }
    ])
    expect(formatMatchingAnswer({ CPU: "Processor", RAM: "Temporary memory" }))
      .toContain("CPU -> Processor")
  })
})
