import { describe, expect, it } from "vitest"

import { stripLeadingTranscriptTimings } from "../media-transcript-display"

describe("stripLeadingTranscriptTimings", () => {
  it("strips leading bracketed and plain timestamp prefixes", () => {
    const input = "[00:12] hello\n00:01:02 - world"
    expect(stripLeadingTranscriptTimings(input)).toBe("hello\nworld")
  })

  it("does not strip mid-sentence timestamps", () => {
    const input = "Call happened at 00:12 in the recording."
    expect(stripLeadingTranscriptTimings(input)).toBe(input)
  })

  it("preserves line breaks for timestamp-only lines", () => {
    const input = "00:12\n00:13 next"
    expect(stripLeadingTranscriptTimings(input)).toBe("\nnext")
  })
})

