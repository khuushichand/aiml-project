import { describe, expect, it } from "vitest"

import {
  buildContextMenuAddPayload,
  buildContextMenuProcessPayload,
  resolveContextMenuTargetUrl
} from "@/entries/shared/ingest-payloads"

describe("ingest payload helpers", () => {
  describe("resolveContextMenuTargetUrl", () => {
    it("prefers linkUrl when both page and link are present", () => {
      const target = resolveContextMenuTargetUrl(
        {
          pageUrl: "https://example.com/page",
          linkUrl: "https://example.com/video.mp4"
        },
        { url: "https://fallback.example.com" }
      )

      expect(target).toBe("https://example.com/video.mp4")
    })

    it("falls back to tab URL when page/link URLs are not valid http", () => {
      const target = resolveContextMenuTargetUrl(
        {
          pageUrl: "chrome://extensions",
          linkUrl: "ftp://example.com/file"
        },
        { url: "https://example.com/article" }
      )

      expect(target).toBe("https://example.com/article")
    })
  })

  it("builds /media/add payload with inferred media_type", () => {
    const payload = buildContextMenuAddPayload(
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    expect(payload).toEqual({
      path: "/api/v1/media/add",
      method: "POST",
      fields: {
        media_type: "video",
        urls: ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
      }
    })
  })

  it("builds process payload with process-web-scraping path for web pages", () => {
    const payload = buildContextMenuProcessPayload("https://example.com/article")

    expect(payload).toEqual({
      path: "/api/v1/media/process-web-scraping",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: { url: "https://example.com/article" }
    })
  })
})

