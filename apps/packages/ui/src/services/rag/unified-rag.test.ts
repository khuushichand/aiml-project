import { describe, expect, it } from "vitest"

import { DEFAULT_RAG_SETTINGS, buildRagSearchRequest } from "./unified-rag"


describe("buildRagSearchRequest rag_profile", () => {
  it("omits rag_profile when set to none", () => {
    const req = buildRagSearchRequest({
      ...DEFAULT_RAG_SETTINGS,
      query: "q",
      rag_profile: "none"
    })

    expect((req.options as Record<string, unknown>).rag_profile).toBeUndefined()
  })

  it("includes rag_profile when set to fast", () => {
    const req = buildRagSearchRequest({
      ...DEFAULT_RAG_SETTINGS,
      query: "q",
      rag_profile: "fast"
    })

    expect((req.options as Record<string, unknown>).rag_profile).toBe("fast")
  })
})
