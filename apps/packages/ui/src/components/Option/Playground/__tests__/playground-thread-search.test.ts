import { describe, expect, it } from "vitest"

import {
  collectThreadSearchMatches,
  getWrappedMatchIndex,
  normalizeThreadSearchQuery
} from "../playground-thread-search"

describe("playground thread search helpers", () => {
  it("normalizes query by trimming and lowercasing", () => {
    expect(normalizeThreadSearchQuery("  HeLLo  ")).toBe("hello")
  })

  it("collects case-insensitive message matches", () => {
    const matches = collectThreadSearchMatches(
      [
        { message: "Hello world" },
        { message: "second turn" },
        { message: "HELLO again" },
        { message: null }
      ],
      "hello"
    )

    expect(matches).toEqual([0, 2])
  })

  it("returns no matches for blank query", () => {
    expect(collectThreadSearchMatches([{ message: "test" }], "   ")).toEqual([])
  })

  it("wraps next/previous match indexes", () => {
    expect(getWrappedMatchIndex(0, 3, 1)).toBe(1)
    expect(getWrappedMatchIndex(2, 3, 1)).toBe(0)
    expect(getWrappedMatchIndex(0, 3, -1)).toBe(2)
  })
})
