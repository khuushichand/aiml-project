import { describe, expect, it } from "vitest"

import { DEFAULT_RAG_SETTINGS, buildRagSearchRequest } from "@/services/rag/unified-rag"

describe("buildRagSearchRequest", () => {
  it("includes enable_text_late_chunking when enabled", () => {
    const req = buildRagSearchRequest({
      ...DEFAULT_RAG_SETTINGS,
      query: "q",
      enable_text_late_chunking: true,
    })

    expect((req.options as Record<string, unknown>).enable_text_late_chunking).toBe(true)
  })

  it("includes text late chunking knobs when configured", () => {
    const req = buildRagSearchRequest({
      ...DEFAULT_RAG_SETTINGS,
      query: "q",
      enable_text_late_chunking: true,
      chunk_method: "words",
      chunk_size: 240,
      chunk_overlap: 24,
      chunk_language: "en",
    })

    expect((req.options as Record<string, unknown>).chunk_method).toBe("words")
    expect((req.options as Record<string, unknown>).chunk_size).toBe(240)
    expect((req.options as Record<string, unknown>).chunk_overlap).toBe(24)
    expect((req.options as Record<string, unknown>).chunk_language).toBe("en")
  })
})
