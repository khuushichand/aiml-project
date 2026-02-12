import { describe, expect, it } from "vitest"
import { resolveRedirectTarget } from "@web/components/navigation/RouteRedirect"

describe("resolveRedirectTarget", () => {
  it("preserves query params by default behavior", () => {
    expect(resolveRedirectTarget("/search?q=rag", "/knowledge", true)).toBe(
      "/knowledge?q=rag"
    )
  })

  it("preserves hash fragments", () => {
    expect(resolveRedirectTarget("/search#examples", "/knowledge", true)).toBe(
      "/knowledge#examples"
    )
  })

  it("does not append params when target already contains query", () => {
    expect(
      resolveRedirectTarget("/search?q=rag", "/knowledge?mode=hybrid", true)
    ).toBe("/knowledge?mode=hybrid")
  })

  it("can disable query/hash preservation", () => {
    expect(resolveRedirectTarget("/search?q=rag#frag", "/knowledge", false)).toBe(
      "/knowledge"
    )
  })
})
