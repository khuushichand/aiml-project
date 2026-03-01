import { describe, expect, it } from "vitest"
import {
  computeTokensPerSecond,
  estimateTokenCountFromText
} from "../writing-generation-stats-utils"

describe("writing generation stats utils", () => {
  it("returns 0 for invalid or empty inputs", () => {
    expect(computeTokensPerSecond(0, 500)).toBe(0)
    expect(computeTokensPerSecond(10, 0)).toBe(0)
    expect(computeTokensPerSecond(10, -50)).toBe(0)
  })

  it("computes tokens per second from token count and elapsed ms", () => {
    expect(computeTokensPerSecond(15, 3000)).toBeCloseTo(5, 5)
    expect(computeTokensPerSecond(3, 500)).toBeCloseTo(6, 5)
  })

  it("estimates token count from text segments", () => {
    expect(estimateTokenCountFromText("")).toBe(0)
    expect(estimateTokenCountFromText("hello")).toBe(1)
    expect(estimateTokenCountFromText("hello world")).toBe(2)
    expect(estimateTokenCountFromText("hello\nworld\tagain")).toBe(3)
  })
})
