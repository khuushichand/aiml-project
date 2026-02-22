import { describe, expect, it } from "vitest"
import {
  buildNormalizedPreview,
  collapsePreviewText,
  computeNormalizedPreviewBudget
} from "../compare-normalized-preview"

describe("compare-normalized-preview", () => {
  it("collapses whitespace consistently", () => {
    expect(collapsePreviewText("  hello   world\n\nfrom\tchat  ")).toBe(
      "hello world from chat"
    )
  })

  it("computes budget from shortest non-empty response with bounds", () => {
    expect(computeNormalizedPreviewBudget(["", "   "])).toBe(180)
    expect(computeNormalizedPreviewBudget(["short", "a bit longer text"])).toBe(
      120
    )
    expect(
      computeNormalizedPreviewBudget([
        "x".repeat(150),
        "x".repeat(260),
        "x".repeat(400)
      ])
    ).toBe(150)
    expect(computeNormalizedPreviewBudget(["x".repeat(500)])).toBe(280)
  })

  it("builds ellipsized normalized previews", () => {
    expect(buildNormalizedPreview("  hi there  ", 10)).toBe("hi there")
    expect(buildNormalizedPreview("a".repeat(12), 10)).toBe("aaaaaaaaa...")
    expect(buildNormalizedPreview("", 20)).toBe("")
  })
})
