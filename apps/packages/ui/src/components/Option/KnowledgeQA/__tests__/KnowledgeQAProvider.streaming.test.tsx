import React from "react"
import { act, render, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { KnowledgeQAProvider, useKnowledgeQA } from "../KnowledgeQAProvider"

const ragSearchMock = vi.fn()
const ragSearchStreamMock = vi.fn()
const messageOpenMock = vi.fn()
const trackMetricMock = vi.fn()

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: () => [undefined],
}))

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => ({
    open: messageOpenMock,
  }),
}))

vi.mock("@/utils/knowledge-qa-search-metrics", () => ({
  trackKnowledgeQaSearchMetric: (...args: unknown[]) => trackMetricMock(...args),
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    initialize: vi.fn().mockResolvedValue(undefined),
    fetchWithAuth: vi.fn().mockResolvedValue({
      ok: false,
      json: async () => [],
      text: async () => "",
    }),
    ragSearch: (...args: unknown[]) => ragSearchMock(...args),
    ragSearchStream: (...args: unknown[]) => ragSearchStreamMock(...args),
  },
}))

let latestContext: ReturnType<typeof useKnowledgeQA> | null = null

function ContextProbe() {
  latestContext = useKnowledgeQA()
  return null
}

describe("KnowledgeQAProvider streaming search", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    latestContext = null
    trackMetricMock.mockResolvedValue(undefined)
    ragSearchMock.mockResolvedValue({
      results: [{ id: "fallback-doc" }],
      answer: "Fallback answer",
    })
  })

  it("applies streamed contexts/deltas incrementally and finalizes answer", async () => {
    let releaseFinalDelta: (() => void) | null = null
    ragSearchStreamMock.mockImplementation(async function* () {
      yield {
        type: "contexts",
        contexts: [
          {
            id: "doc-1",
            title: "Doc One",
            score: 0.92,
            url: "https://example.com/doc-1",
            source: "media_db",
          },
        ],
        why: {
          topicality: 0.88,
          diversity: 0.42,
          freshness: null,
        },
      }
      yield { type: "delta", text: "Hello" }
      await new Promise<void>((resolve) => {
        releaseFinalDelta = resolve
      })
      yield { type: "delta", text: " world" }
    })

    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())
    await act(async () => {
      await latestContext!.selectThread("local-stream-test")
    })

    act(() => {
      latestContext!.setQuery("stream this")
    })

    let searchPromise: Promise<void> | null = null
    act(() => {
      searchPromise = latestContext!.search()
    })

    await waitFor(() => expect(latestContext!.results.length).toBe(1))
    await waitFor(() => {
      expect(latestContext!.answer).toBe("Hello")
      expect(latestContext!.isSearching).toBe(true)
    })

    act(() => {
      releaseFinalDelta?.()
    })

    await act(async () => {
      await searchPromise
    })

    expect(latestContext!.answer).toBe("Hello world")
    expect(latestContext!.isSearching).toBe(false)
    expect(latestContext!.searchDetails).toEqual(
      expect.objectContaining({
        rerankingEnabled: true,
        averageRelevance: 0.92,
        whyTheseSources: expect.objectContaining({
          topicality: 0.88,
          diversity: 0.42,
        }),
      })
    )
    expect(ragSearchStreamMock).toHaveBeenCalledTimes(1)
    expect(ragSearchMock).not.toHaveBeenCalled()
    expect(trackMetricMock).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "search_complete",
        used_streaming: true,
        has_answer: true,
      })
    )
  })

  it("falls back to non-stream rag search when stream path fails", async () => {
    ragSearchStreamMock.mockImplementation(async function* () {
      throw new Error("stream endpoint unavailable")
    })
    ragSearchMock.mockResolvedValue({
      results: [{ id: "fallback-doc", metadata: { title: "Fallback" } }],
      answer: "Fallback answer",
      expanded_queries: ["fallback path alt"],
      metadata: {
        web_fallback: {
          triggered: true,
          engine_used: "duckduckgo",
        },
      },
    })

    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())
    await act(async () => {
      await latestContext!.selectThread("local-stream-fallback")
    })

    act(() => {
      latestContext!.setQuery("fallback path")
    })

    await act(async () => {
      await latestContext!.search()
    })

    expect(ragSearchStreamMock).toHaveBeenCalledTimes(1)
    expect(ragSearchMock).toHaveBeenCalledTimes(1)
    expect(latestContext!.answer).toBe("Fallback answer")
    expect(latestContext!.isSearching).toBe(false)
    expect(latestContext!.searchDetails).toEqual(
      expect.objectContaining({
        expandedQueries: ["fallback path alt"],
        webFallbackTriggered: true,
        webFallbackEngine: "duckduckgo",
      })
    )
    expect(trackMetricMock).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "search_complete",
        used_streaming: false,
        has_answer: true,
      })
    )
  })
})
