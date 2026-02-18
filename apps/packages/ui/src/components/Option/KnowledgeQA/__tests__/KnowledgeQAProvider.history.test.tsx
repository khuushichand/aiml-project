import React from "react"
import { act, render, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { KnowledgeQAProvider, useKnowledgeQA } from "../KnowledgeQAProvider"
import type { SearchHistoryItem } from "../types"

const fetchWithAuthMock = vi.fn()
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
    fetchWithAuth: (...args: unknown[]) => fetchWithAuthMock(...args),
    ragSearch: vi.fn(),
    addChatMessage: vi.fn(),
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

const baseHistoryItem: SearchHistoryItem = {
  id: "history-1",
  query: "Hydrate this thread",
  timestamp: "2026-02-18T10:00:00.000Z",
  sourcesCount: 1,
  hasAnswer: true,
  preset: "fast",
  keywords: ["__knowledge_QA__"],
  conversationId: "remote-thread-1",
}

describe("KnowledgeQAProvider history hydration", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    latestContext = null
    trackMetricMock.mockResolvedValue(undefined)
    localStorage.clear()

    fetchWithAuthMock.mockImplementation(async (path: string) => {
      if (path.includes("/messages-with-context")) {
        return {
          ok: true,
          status: 200,
          json: async () => [],
          text: async () => "",
        }
      }
      return {
        ok: false,
        status: 404,
        json: async () => [],
        text: async () => "",
      }
    })
  })

  it("restores query, answer, sources, and citations when selecting history", async () => {
    localStorage.setItem("knowledge_qa_history", JSON.stringify([baseHistoryItem]))
    fetchWithAuthMock.mockImplementation(async (path: string) => {
      if (path.includes("/messages-with-context")) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: "msg-user",
              role: "user",
              content: "How did findings change?",
              created_at: "2026-02-18T10:00:00.000Z",
            },
            {
              id: "msg-assistant",
              role: "assistant",
              content: "Fallback answer",
              created_at: "2026-02-18T10:00:02.000Z",
              rag_context: {
                search_query: "How did findings change?",
                generated_answer: "Final answer [1]",
                retrieved_documents: [
                  {
                    id: "doc-1",
                    title: "Spec",
                    source_type: "media_db",
                    excerpt: "Evidence snippet",
                    score: 0.91,
                    page_number: 2,
                  },
                ],
              },
            },
          ],
          text: async () => "",
        }
      }
      return {
        ok: false,
        status: 404,
        json: async () => [],
        text: async () => "",
      }
    })

    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())

    await act(async () => {
      await latestContext!.restoreFromHistory(baseHistoryItem)
    })

    await waitFor(() => {
      expect(latestContext!.preset).toBe("fast")
      expect(latestContext!.query).toBe("How did findings change?")
      expect(latestContext!.answer).toBe("Final answer [1]")
      expect(latestContext!.results).toHaveLength(1)
      expect(latestContext!.citations).toEqual(
        expect.arrayContaining([expect.objectContaining({ index: 1 })])
      )
      expect(latestContext!.messages).toHaveLength(2)
    })
  })

  it("hydrates partial payloads without failing and clears stale results", async () => {
    localStorage.setItem("knowledge_qa_history", JSON.stringify([baseHistoryItem]))
    fetchWithAuthMock.mockImplementation(async (path: string) => {
      if (path.includes("/messages-with-context")) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: "msg-user-2",
              role: "user",
              content: "Question with no context payload",
              created_at: "2026-02-18T10:01:00.000Z",
            },
            {
              id: "msg-assistant-2",
              role: "assistant",
              content: "Answer without rag context",
              created_at: "2026-02-18T10:01:02.000Z",
            },
          ],
          text: async () => "",
        }
      }
      return {
        ok: false,
        status: 404,
        json: async () => [],
        text: async () => "",
      }
    })

    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())

    await act(async () => {
      await latestContext!.selectThread("remote-thread-1")
    })

    await waitFor(() => {
      expect(latestContext!.query).toBe("Question with no context payload")
      expect(latestContext!.answer).toBe("Answer without rag context")
      expect(latestContext!.results).toHaveLength(0)
      expect(latestContext!.citations).toHaveLength(0)
    })
  })

  it("toggles pin state and persists to localStorage", async () => {
    render(
      <KnowledgeQAProvider>
        <ContextProbe />
      </KnowledgeQAProvider>
    )

    await waitFor(() => expect(latestContext).not.toBeNull())
    localStorage.setItem("knowledge_qa_history", JSON.stringify([baseHistoryItem]))
    await act(async () => {
      await latestContext!.loadSearchHistory()
    })
    await waitFor(() => expect(latestContext!.searchHistory).toHaveLength(1))

    act(() => {
      latestContext!.toggleHistoryPin("history-1")
    })

    await waitFor(() => {
      expect(latestContext!.searchHistory[0]?.pinned).toBe(true)
      const persisted = JSON.parse(localStorage.getItem("knowledge_qa_history") || "[]")
      expect(persisted[0]?.pinned).toBe(true)
    })
  })
})
