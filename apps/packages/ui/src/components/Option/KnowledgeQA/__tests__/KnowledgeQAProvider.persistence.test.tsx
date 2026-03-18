import React from "react"
import { act, render, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { KnowledgeQAProvider, useKnowledgeQA } from "../KnowledgeQAProvider"

const ragSearchMock = vi.fn()
const addChatMessageMock = vi.fn()
const fetchWithAuthMock = vi.fn()
const messageOpenMock = vi.fn()
const trackMetricMock = vi.fn()
let storedPresetValue: unknown = undefined
let storedSettingsValue: unknown = undefined
let storedStreamingFlagValue: unknown = undefined

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (key: string) => {
    if (key === "ragSearchPreset") return [storedPresetValue]
    if (key === "ragSearchSettingsV2") return [storedSettingsValue]
    if (key === "ff_knowledgeQaStreaming") return [storedStreamingFlagValue]
    return [undefined]
  },
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
    fetchWithAuth: (...args: unknown[]) => fetchWithAuthMock(...args),
    ragSearch: (...args: unknown[]) => ragSearchMock(...args),
    addChatMessage: (...args: unknown[]) => addChatMessageMock(...args),
    searchCharacters: vi.fn().mockResolvedValue([]),
    listCharacters: vi.fn().mockResolvedValue([]),
    createChat: vi.fn().mockResolvedValue({ id: "thread-1", version: 1 }),
    getChat: vi.fn().mockResolvedValue({ version: 1 }),
  },
}))

let latestContext: ReturnType<typeof useKnowledgeQA> | null = null

function ContextProbe() {
  latestContext = useKnowledgeQA()
  return null
}

describe("KnowledgeQAProvider persistence safeguards", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    latestContext = null
    storedPresetValue = undefined
    storedSettingsValue = undefined
    storedStreamingFlagValue = undefined
    trackMetricMock.mockResolvedValue(undefined)
    ragSearchMock.mockResolvedValue({
      results: [],
      generated_answer: null,
    })
    addChatMessageMock.mockResolvedValue({ id: "msg-1" })
    fetchWithAuthMock.mockImplementation(async (path: string) => {
      if (path.includes("/messages-with-context")) {
        return {
          ok: true,
          json: async () => [],
          text: async () => "",
        }
      }
      return {
        ok: false,
        json: async () => [],
        text: async () => "",
      }
    })
  })

  it("switches into local-only mode when thread creation falls back to local ids", async () => {
    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())

    act(() => {
      latestContext!.setQuery("query that triggers local fallback")
    })
    act(() => {
      void latestContext!.search()
    })

    await waitFor(() => {
      expect(latestContext!.isSearching).toBe(false)
      expect(latestContext!.currentThreadId).toMatch(/^local-/)
      expect(latestContext!.isLocalOnlyThread).toBe(true)
    })
  })

  it("shows persistence warning only on first chat message save failure", async () => {
    addChatMessageMock.mockRejectedValue(new Error("save failed"))

    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())

    await act(async () => {
      await latestContext!.selectThread("remote-thread")
    })
    await waitFor(() => expect(latestContext!.isLocalOnlyThread).toBe(false))

    act(() => {
      latestContext!.setQuery("first attempt")
    })
    act(() => {
      void latestContext!.search()
    })

    await waitFor(() => expect(latestContext!.isSearching).toBe(false))

    act(() => {
      latestContext!.setQuery("second attempt")
    })
    act(() => {
      void latestContext!.search()
    })

    await waitFor(() => expect(latestContext!.isSearching).toBe(false))

    const warningCalls = messageOpenMock.mock.calls.filter((args) => {
      const payload = args[0] as { type?: string; content?: string }
      return (
        payload?.type === "warning" &&
        payload?.content ===
          "Unable to save conversation. Results are available but may not persist."
      )
    })
    expect(warningCalls).toHaveLength(1)
  })

  it("preserves legacy numeric note ids when hydrating persisted settings", async () => {
    storedSettingsValue = {
      include_note_ids: [101, "note-legacy-string", 202.9, null],
    }

    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())

    await waitFor(() => {
      expect(latestContext!.settings.include_note_ids).toEqual([
        "101",
        "note-legacy-string",
        "202",
      ])
    })
  })
})
