import { describe, expect, it } from "vitest"
import {
  mapKnowledgeQaExportErrorMessage,
  mapKnowledgeQaSearchErrorMessage,
} from "../errorMessages"

describe("Knowledge QA error message mapping", () => {
  it("maps search timeout and connection failures to actionable copy", () => {
    expect(mapKnowledgeQaSearchErrorMessage(new Error("request timed out"))).toBe(
      "Search timed out. Try the Fast preset or reduce sources."
    )
    expect(mapKnowledgeQaSearchErrorMessage(new Error("network unreachable"))).toBe(
      "Cannot reach server. Check your connection and try again."
    )
  })

  it("maps export failures to chatbook-specific messaging", () => {
    expect(mapKnowledgeQaExportErrorMessage(new Error("404 not found"))).toBe(
      "Chatbook export failed. Thread was not found."
    )
    expect(
      mapKnowledgeQaExportErrorMessage(new Error("HTTP 401 unauthorized"))
    ).toBe("Chatbook export failed. You are not authorized to export this thread.")
    expect(
      mapKnowledgeQaExportErrorMessage(new Error("HTTP 403 forbidden"))
    ).toBe("Chatbook export failed. You do not have permission to export this thread.")
    expect(
      mapKnowledgeQaExportErrorMessage(
        new Error("HTTP 422: validation failed: content_selections is required")
      )
    ).toBe(
      "Chatbook export failed. Export request is invalid. Check the selected thread and try again."
    )
    expect(
      mapKnowledgeQaExportErrorMessage(new Error("Failed to fetch"))
    ).toBe("Chatbook export failed. Cannot reach server.")
    expect(
      mapKnowledgeQaExportErrorMessage(new Error("HTTP 500: internal server error"))
    ).toBe("Chatbook export failed due to a server error. Please try again.")
    expect(
      mapKnowledgeQaExportErrorMessage(new Error("HTTP 429: too many requests"))
    ).toBe(
      "Chatbook export failed. Too many export requests. Please wait and try again."
    )
  })
})
