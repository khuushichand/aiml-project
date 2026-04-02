import { beforeEach, describe, expect, it, vi } from "vitest"

const useInfiniteQueryMock = vi.fn()
const listFlashcardsMock = vi.fn()

vi.mock("@tanstack/react-query", () => ({
  useInfiniteQuery: (options: unknown) => useInfiniteQueryMock(options)
}))

vi.mock("@/services/flashcards", () => {
  const noopAsync = vi.fn()
  return {
    listDecks: noopAsync,
    listFlashcards: (...args: unknown[]) => listFlashcardsMock(...args),
    createFlashcard: noopAsync,
    createFlashcardsBulk: noopAsync,
    updateFlashcardsBulk: noopAsync,
    createDeck: noopAsync,
    updateFlashcard: noopAsync,
    deleteFlashcard: noopAsync,
    resetFlashcardScheduling: noopAsync,
    reviewFlashcard: noopAsync,
    generateFlashcards: noopAsync,
    getFlashcard: noopAsync,
    importFlashcards: noopAsync,
    previewStructuredQaImport: noopAsync,
    importFlashcardsJson: noopAsync,
    importFlashcardsApkg: noopAsync,
    getFlashcardsAnalyticsSummary: noopAsync,
    exportFlashcards: noopAsync,
    exportFlashcardsFile: noopAsync,
    getFlashcardsImportLimits: noopAsync
  }
})

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: { hasFlashcards: true },
    loading: false
  })
}))

import { useFlashcardDocumentQuery } from "../useFlashcardDocumentQuery"

function makeFlashcard(overrides: Partial<import("@/services/flashcards").Flashcard> = {}) {
  return {
    uuid: "card-1",
    deck_id: 1,
    front: "Front",
    back: "Back",
    notes: null,
    extra: null,
    is_cloze: false,
    tags: [],
    ef: 2.5,
    interval_days: 0,
    repetitions: 0,
    lapses: 0,
    due_at: "2026-03-13T00:00:00Z",
    created_at: "2026-03-12T00:00:00Z",
    last_reviewed_at: null,
    last_modified: "2026-03-12T00:00:00Z",
    deleted: false,
    client_id: "test-client",
    version: 1,
    model_type: "basic" as const,
    reverse: false,
    source_ref_type: "manual" as const,
    source_ref_id: null,
    conversation_id: null,
    message_id: null,
    ...overrides
  }
}

describe("useFlashcardDocumentQuery", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useInfiniteQueryMock.mockImplementation((options: any) => ({
      data: { pages: [] },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      ...options
    }))
  })

  it("limits document-mode sorts to due and created and reports truncation for capped multi-tag scans", async () => {
    let options: any
    useInfiniteQueryMock.mockImplementation((input: any) => {
      options = input
      return {
        data: { pages: [] },
        fetchNextPage: vi.fn(),
        hasNextPage: false,
        isFetchingNextPage: false
      }
    })

    listFlashcardsMock.mockResolvedValue({
      items: [makeFlashcard({ uuid: "a", tags: ["one", "two"] })],
      count: 1,
      total: 20000
    })

    const result = useFlashcardDocumentQuery({
      deckId: null,
      tags: ["one", "two"],
      dueStatus: "all",
      sortBy: "due"
    })

    const firstPage = await options.queryFn({ pageParam: 0 })

    expect(result.supportedSorts).toEqual(["due", "created"])
    expect(firstPage.items).toHaveLength(1)
    expect(firstPage.isTruncated).toBe(true)
  })

  it("fetches the next page for stable server-backed sorts", async () => {
    let options: any
    useInfiniteQueryMock.mockImplementation((input: any) => {
      options = input
      return {
        data: { pages: [] },
        fetchNextPage: vi.fn(),
        hasNextPage: true,
        isFetchingNextPage: false
      }
    })

    listFlashcardsMock
      .mockResolvedValueOnce({
        items: [makeFlashcard({ uuid: "a" }), makeFlashcard({ uuid: "b" })],
        count: 2,
        total: 4
      })
      .mockResolvedValueOnce({
        items: [makeFlashcard({ uuid: "c" }), makeFlashcard({ uuid: "d" })],
        count: 2,
        total: 4
      })

    useFlashcardDocumentQuery({
      deckId: null,
      dueStatus: "all",
      sortBy: "created",
      pageSize: 2
    })

    const firstPage = await options.queryFn({ pageParam: 0 })
    const nextPageParam = options.getNextPageParam(firstPage)
    const secondPage = await options.queryFn({ pageParam: nextPageParam })

    expect(firstPage.items.map((card: any) => card.uuid)).toEqual(["a", "b"])
    expect(secondPage.items.map((card: any) => card.uuid)).toEqual(["c", "d"])
    expect(listFlashcardsMock).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        offset: 2,
        limit: 2,
        order_by: "created_at"
      })
    )
  })

  it("keeps document queries workspace-hidden by default", async () => {
    let options: any
    useInfiniteQueryMock.mockImplementation((input: any) => {
      options = input
      return {
        data: { pages: [] },
        fetchNextPage: vi.fn(),
        hasNextPage: false,
        isFetchingNextPage: false
      }
    })

    listFlashcardsMock.mockResolvedValue({
      items: [makeFlashcard({ uuid: "workspace-card", deck_id: 9 })],
      count: 1,
      total: 1
    })

    useFlashcardDocumentQuery({
      deckId: null,
      dueStatus: "all",
      sortBy: "due"
    })

    await options.queryFn({ pageParam: 0 })

    expect(listFlashcardsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        include_workspace_items: false
      })
    )
  })
})
