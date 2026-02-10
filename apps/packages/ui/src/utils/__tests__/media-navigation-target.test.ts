import { describe, expect, it } from "vitest"

import {
  describeMediaNavigationTarget,
  formatMediaNavigationTimecode
} from "@/utils/media-navigation-target"

describe("media-navigation-target", () => {
  it("formats timecodes", () => {
    expect(formatMediaNavigationTimecode(0)).toBe("00:00")
    expect(formatMediaNavigationTimecode(65)).toBe("01:05")
    expect(formatMediaNavigationTimecode(3661)).toBe("01:01:01")
  })

  it("describes time-range targets", () => {
    expect(
      describeMediaNavigationTarget({
        target_type: "time_range",
        target_start: 12,
        target_end: 27,
        target_href: null
      })
    ).toBe("Time 00:12 - 00:27")
  })

  it("describes page and char-range targets", () => {
    expect(
      describeMediaNavigationTarget({
        target_type: "page",
        target_start: 5,
        target_end: null,
        target_href: null
      })
    ).toBe("Page 5")

    expect(
      describeMediaNavigationTarget({
        target_type: "char_range",
        target_start: 100,
        target_end: 250,
        target_href: null
      })
    ).toBe("Chars 100-250")
  })

  it("describes internal anchors and rejects invalid href targets", () => {
    expect(
      describeMediaNavigationTarget({
        target_type: "href",
        target_start: null,
        target_end: null,
        target_href: "#section-2"
      })
    ).toBe("Anchor #section-2")

    expect(
      describeMediaNavigationTarget({
        target_type: "href",
        target_start: null,
        target_end: null,
        target_href: "https://example.com"
      })
    ).toBeNull()
  })
})

