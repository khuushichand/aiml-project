import { describe, expect, it } from "vitest"
import {
  formatFillBlankAcceptedAnswers,
  isFillBlankAnswerCorrect
} from "../fillBlankAnswer"

describe("fillBlankAnswer", () => {
  it("matches exact answers case-insensitively", () => {
    expect(isFillBlankAnswerCorrect("Mitochondrion", "mitochondrion")).toBe(true)
    expect(isFillBlankAnswerCorrect("  ATP  ", "atp")).toBe(true)
    expect(isFillBlankAnswerCorrect("nucleus", "mitochondrion")).toBe(false)
  })

  it("supports multiple accepted answers via || delimiter", () => {
    expect(isFillBlankAnswerCorrect("colour", "color || colour")).toBe(true)
    expect(isFillBlankAnswerCorrect("color", "color || colour")).toBe(true)
    expect(isFillBlankAnswerCorrect("hue", "color || colour")).toBe(false)
  })

  it("supports fuzzy tokens with optional threshold", () => {
    expect(isFillBlankAnswerCorrect("mitocondrion", "~mitochondrion")).toBe(true)
    expect(isFillBlankAnswerCorrect("mitocondrion", "~0.93:mitochondrion")).toBe(false)
    expect(isFillBlankAnswerCorrect("cell wall", "~0.75:cell walls")).toBe(true)
  })

  it("supports JSON answer config with fuzzy matching", () => {
    const config = JSON.stringify({
      accepted_answers: ["sulfur", "sulphur"],
      fuzzy: true,
      fuzzy_threshold: 0.85
    })
    expect(isFillBlankAnswerCorrect("sulfur", config)).toBe(true)
    expect(isFillBlankAnswerCorrect("sulphor", config)).toBe(true)
    expect(isFillBlankAnswerCorrect("oxygen", config)).toBe(false)
  })

  it("formats accepted answers for learner-facing correct-answer display", () => {
    expect(formatFillBlankAcceptedAnswers("color || ~colour")).toEqual([
      "color",
      "colour"
    ])
  })
})

