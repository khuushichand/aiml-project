import { describe, expect, it } from "vitest"
import { resolveWritingLayoutMode } from "../writing-layout-utils"

describe("writing layout utils", () => {
  it("returns compact mode under narrow width", () => {
    expect(resolveWritingLayoutMode(720)).toBe("compact")
    expect(resolveWritingLayoutMode(1099)).toBe("compact")
  })

  it("returns expanded mode above desktop threshold", () => {
    expect(resolveWritingLayoutMode(1100)).toBe("expanded")
    expect(resolveWritingLayoutMode(1280)).toBe("expanded")
  })
})
