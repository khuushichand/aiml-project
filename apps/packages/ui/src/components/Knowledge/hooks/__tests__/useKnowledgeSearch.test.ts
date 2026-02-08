import { describe, expect, it } from "vitest"

import {
  extractContentFromMediaDetail,
  extractMediaId,
  normalizeMediaSearchResults,
  toPinnedResult,
  type RagResult
} from "../useKnowledgeSearch"

describe("useKnowledgeSearch helpers", () => {
  it("normalizes media search responses into knowledge result cards", () => {
    const payload = {
      items: [
        {
          id: 42,
          title: "Quarterly Report",
          type: "pdf",
          url: "/api/v1/media/42"
        }
      ]
    }

    const results = normalizeMediaSearchResults(payload)

    expect(results).toHaveLength(1)
    expect(results[0].metadata?.media_id).toBe(42)
    expect(results[0].metadata?.title).toBe("Quarterly Report")
    expect(results[0].metadata?.type).toBe("pdf")
    expect(results[0].content).toContain("Library item")
  })

  it("extracts media id and carries it into pinned result metadata", () => {
    const result: RagResult = {
      content: "Snippet text",
      metadata: {
        media_id: "17",
        title: "Research Note",
        type: "note"
      }
    }

    expect(extractMediaId(result)).toBe(17)

    const pinned = toPinnedResult(result)
    expect(pinned.mediaId).toBe(17)
    expect(pinned.title).toBe("Research Note")
    expect(pinned.type).toBe("note")
  })

  it("extracts full text from nested media detail content objects", () => {
    const detail = {
      content: {
        text: "Full media transcript"
      }
    }

    expect(extractContentFromMediaDetail(detail)).toBe("Full media transcript")
  })

  it("falls back to latest_version and data content fields", () => {
    const latestVersionDetail = {
      latest_version: {
        content: "Latest version text"
      }
    }
    const dataDetail = {
      data: {
        raw_text: "Data-level text"
      }
    }

    expect(extractContentFromMediaDetail(latestVersionDetail)).toBe(
      "Latest version text"
    )
    expect(extractContentFromMediaDetail(dataDetail)).toBe("Data-level text")
  })
})
