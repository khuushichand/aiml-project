import React from "react"
import { act, render, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { KnowledgeQAProvider, useKnowledgeQA } from "../KnowledgeQAProvider"

const ragSearchMock = vi.fn()
const ragSearchStreamMock = vi.fn()
const trackMetricMock = vi.fn()

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (key: string, defaultValue: unknown) => {
    if (key === "ff_knowledgeQaStreaming") return [false]
    return [defaultValue]
  },
}))

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => ({
    open: vi.fn(),
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

describe("KnowledgeQAProvider feature flags", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    latestContext = null
    ragSearchMock.mockResolvedValue({
      results: [{ id: "fallback-doc" }],
      answer: "Fallback answer",
    })
    ragSearchStreamMock.mockImplementation(async function* () {
      yield { type: "delta", text: "stream should be disabled" }
    })
  })

  it("skips streaming path when streaming feature flag is disabled", async () => {
    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())
    await act(async () => {
      await latestContext!.selectThread("local-feature-flag")
    })
    act(() => {
      latestContext!.setQuery("run without stream")
    })

    await act(async () => {
      await latestContext!.search()
    })

    expect(ragSearchStreamMock).not.toHaveBeenCalled()
    expect(ragSearchMock).toHaveBeenCalledTimes(1)
    expect(trackMetricMock).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "search_complete",
        used_streaming: false,
      })
    )
  })
})
