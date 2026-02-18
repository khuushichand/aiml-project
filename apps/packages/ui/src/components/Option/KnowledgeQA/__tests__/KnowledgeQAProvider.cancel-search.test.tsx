import React from "react"
import { act, render, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { KnowledgeQAProvider, useKnowledgeQA } from "../KnowledgeQAProvider"

const ragSearchMock = vi.fn()
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
  },
}))

let latestContext: ReturnType<typeof useKnowledgeQA> | null = null

function ContextProbe() {
  latestContext = useKnowledgeQA()
  return null
}

describe("KnowledgeQAProvider search cancellation", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    latestContext = null
    trackMetricMock.mockResolvedValue(undefined)
    ragSearchMock.mockImplementation((_query: string, options: { signal?: AbortSignal }) => {
      return new Promise((_resolve, reject) => {
        options.signal?.addEventListener("abort", () => {
          const abortError = new Error("Aborted")
          ;(abortError as Error & { name: string }).name = "AbortError"
          reject(abortError)
        })
      })
    })
  })

  it("passes AbortSignal to ragSearch and supports cancelSearch", async () => {
    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())

    await act(async () => {
      await latestContext!.selectThread("local-test-thread")
    })

    act(() => {
      latestContext!.setQuery("cancel this query")
    })

    act(() => {
      void latestContext!.search()
    })

    await waitFor(() => expect(ragSearchMock).toHaveBeenCalledTimes(1))
    expect(trackMetricMock).toHaveBeenCalledWith({
      type: "search_submit",
      query_length: "cancel this query".length,
    })

    const ragSearchOptions = ragSearchMock.mock.calls[0][1] as {
      signal?: AbortSignal
    }
    expect(ragSearchOptions.signal).toBeInstanceOf(AbortSignal)

    act(() => {
      latestContext!.cancelSearch()
    })

    await waitFor(() => {
      expect(latestContext!.isSearching).toBe(false)
      expect(latestContext!.error).toBe("Search cancelled")
    })

    expect(messageOpenMock).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "info",
        content: "Search cancelled.",
      })
    )
    expect(trackMetricMock).toHaveBeenCalledWith({ type: "search_cancel" })
  })

  it("tracks clear-full actions and keeps clear aborts status-neutral", async () => {
    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())

    await act(async () => {
      await latestContext!.selectThread("local-test-thread")
    })

    act(() => {
      latestContext!.setQuery("query to clear")
    })

    act(() => {
      void latestContext!.search()
    })

    await waitFor(() => expect(ragSearchMock).toHaveBeenCalledTimes(1))

    act(() => {
      latestContext!.clearResults()
    })

    await waitFor(() => {
      expect(latestContext!.isSearching).toBe(false)
      expect(latestContext!.error).toBeNull()
    })

    expect(trackMetricMock).toHaveBeenCalledWith({ type: "search_clear_full" })
    expect(trackMetricMock).not.toHaveBeenCalledWith({ type: "search_cancel" })
  })
})
