import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  DEFAULT_RAG_SETTINGS,
  buildRagSearchRequest
} from "@/services/rag/unified-rag"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { useQASearch } from "../useQASearch"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    initialize: vi.fn(),
    ragSearch: vi.fn()
  }
}))

vi.mock("@/services/rag/unified-rag", async () => {
  const actual = await vi.importActual<
    typeof import("@/services/rag/unified-rag")
  >("@/services/rag/unified-rag")
  return {
    ...actual,
    buildRagSearchRequest: vi.fn()
  }
})

describe("useQASearch", () => {
  const baseSettings = {
    ...DEFAULT_RAG_SETTINGS
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(tldwClient.initialize).mockResolvedValue(undefined)
    vi.mocked(buildRagSearchRequest).mockImplementation((settings) => ({
      query: settings.query || "default query",
      options: { strategy: settings.strategy },
      timeoutMs: 1000
    }))
  })

  const createHook = (resolvedQuery = "knowledge query") => {
    const applySettings = vi.fn()
    const onInsert = vi.fn()
    const onPin = vi.fn()

    const hook = renderHook(() =>
      useQASearch({
        resolvedQuery,
        draftSettings: baseSettings,
        applySettings,
        onInsert,
        pinnedResults: [],
        onPin
      })
    )

    return { ...hook, applySettings, onInsert, onPin }
  }

  it("normalizes responses that return documents in `results`", async () => {
    vi.mocked(tldwClient.ragSearch).mockResolvedValue({
      query: "normalized query",
      generated_answer: "Generated answer",
      results: [
        {
          id: "doc-1",
          content: "Result document content",
          score: "0.87",
          relevance: 0.51,
          media_id: "123",
          metadata: { title: "Document Title" }
        }
      ],
      citations: [{ source: "doc-1", score: "0.42", chunk_index: "2" }],
      timings: { retrieval: "0.23" },
      total_time: "1.7",
      cache_hit: true,
      feedback_id: "fb-1",
      errors: ["warning"],
      expanded_queries: ["knowledge query variant"]
    })

    const { result } = createHook()

    await act(async () => {
      await result.current.runQASearch()
    })

    expect(result.current.response).not.toBeNull()
    expect(result.current.response?.query).toBe("normalized query")
    expect(result.current.response?.generatedAnswer).toBe("Generated answer")
    expect(result.current.response?.documents).toHaveLength(1)
    expect(result.current.response?.documents[0].content).toBe(
      "Result document content"
    )
    expect(result.current.response?.documents[0].score).toBe(0.87)
    expect(result.current.response?.documents[0].media_id).toBe(123)
    expect(result.current.response?.citations[0].score).toBe(0.42)
    expect(result.current.response?.citations[0].chunk_index).toBe(2)
    expect(result.current.response?.timings).toEqual({ retrieval: 0.23 })
    expect(result.current.response?.totalTime).toBe(1.7)
    expect(result.current.response?.cacheHit).toBe(true)
    expect(result.current.response?.feedbackId).toBe("fb-1")
    expect(result.current.response?.expandedQueries).toEqual([
      "knowledge query variant"
    ])
  })

  it("falls back to `docs` and legacy answer/cache field names", async () => {
    vi.mocked(tldwClient.ragSearch).mockResolvedValue({
      documents: [],
      docs: [{ chunk: "Chunk from docs payload", relevance: "0.66" }],
      answer: "Legacy answer field",
      cacheHit: true,
      totalTime: 2.4,
      feedbackId: "feedback-legacy"
    })

    const { result } = createHook()

    await act(async () => {
      await result.current.runQASearch()
    })

    expect(result.current.response?.generatedAnswer).toBe("Legacy answer field")
    expect(result.current.response?.documents).toHaveLength(1)
    expect(result.current.response?.documents[0].chunk).toBe(
      "Chunk from docs payload"
    )
    expect(result.current.response?.documents[0].relevance).toBe(0.66)
    expect(result.current.response?.cacheHit).toBe(true)
    expect(result.current.response?.totalTime).toBe(2.4)
    expect(result.current.response?.feedbackId).toBe("feedback-legacy")
  })

  it("keeps `documents` precedence when multiple document arrays are present", async () => {
    vi.mocked(tldwClient.ragSearch).mockResolvedValue({
      documents: [{ content: "From documents" }],
      results: [{ content: "From results" }],
      docs: [{ content: "From docs" }]
    })

    const { result } = createHook()

    await act(async () => {
      await result.current.runQASearch()
    })

    expect(result.current.response?.documents).toHaveLength(1)
    expect(result.current.response?.documents[0].content).toBe("From documents")
  })

  it("returns safe defaults for partial payloads", async () => {
    vi.mocked(tldwClient.ragSearch).mockResolvedValue({})

    const { result } = createHook("fallback query")

    await act(async () => {
      await result.current.runQASearch()
    })

    expect(result.current.response).toEqual({
      generatedAnswer: null,
      documents: [],
      citations: [],
      academicCitations: [],
      timings: {},
      totalTime: 0,
      cacheHit: false,
      feedbackId: null,
      errors: [],
      query: "fallback query",
      expandedQueries: []
    })
  })

  it("sets timedOut for timeout failures and clears response", async () => {
    vi.mocked(tldwClient.ragSearch).mockRejectedValue(
      new Error("request timed out")
    )

    const { result } = createHook()

    await act(async () => {
      await result.current.runQASearch()
    })

    expect(result.current.response).toBeNull()
    expect(result.current.timedOut).toBe(true)
    expect(result.current.loading).toBe(false)
  })

  it("handles non-timeout failures without marking timedOut", async () => {
    vi.mocked(tldwClient.ragSearch).mockRejectedValue(
      new Error("backend unavailable")
    )

    const { result } = createHook()

    await act(async () => {
      await result.current.runQASearch()
    })

    expect(result.current.response).toBeNull()
    expect(result.current.timedOut).toBe(false)
    expect(result.current.loading).toBe(false)
  })
})
