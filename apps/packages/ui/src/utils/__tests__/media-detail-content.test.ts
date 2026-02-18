import { describe, expect, it } from "vitest"

import { extractMediaDetailContent } from "../media-detail-content"

describe("extractMediaDetailContent", () => {
  it("extracts text from nested content object", () => {
    const detail = {
      content: {
        text: "Nested content text"
      }
    }

    expect(extractMediaDetailContent(detail)).toBe("Nested content text")
  })

  it("falls back to latest_version and data object content", () => {
    const latestDetail = {
      latest_version: {
        content: {
          text: "Latest version nested text"
        }
      }
    }
    const dataDetail = {
      data: {
        content: {
          raw_text: "Data nested raw text"
        }
      }
    }

    expect(extractMediaDetailContent(latestDetail)).toBe(
      "Latest version nested text"
    )
    expect(extractMediaDetailContent(dataDetail)).toBe("Data nested raw text")
  })

  it("supports legacy flat response fields", () => {
    const detail = {
      raw_text: "Legacy root content"
    }

    expect(extractMediaDetailContent(detail)).toBe("Legacy root content")
  })

  it("returns empty string when no text-like fields exist", () => {
    expect(extractMediaDetailContent({ content: { metadata: { a: 1 } } })).toBe("")
  })
})
