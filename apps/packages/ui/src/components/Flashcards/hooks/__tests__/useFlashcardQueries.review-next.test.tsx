import React from "react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import { useReviewQuery } from "../useFlashcardQueries"
import { getNextReviewCard, type Flashcard } from "@/services/flashcards"

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: { hasFlashcards: true },
    loading: false
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/services/flashcards", async () => {
  const actual = await vi.importActual<typeof import("@/services/flashcards")>(
    "@/services/flashcards"
  )
  return {
    ...actual,
    getNextReviewCard: vi.fn()
  }
})

const buildWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  })

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

const baseCard: Flashcard = {
  uuid: "card-1",
  deck_id: 7,
  front: "Front",
  back: "Back",
  notes: null,
  extra: null,
  is_cloze: false,
  tags: [],
  ef: 2.5,
  interval_days: 4,
  repetitions: 3,
  lapses: 0,
  due_at: "2026-03-12T09:59:00Z",
  created_at: "2026-03-01T00:00:00Z",
  last_reviewed_at: "2026-03-10T00:00:00Z",
  queue_state: "learning",
  step_index: 0,
  suspended_reason: null,
  last_modified: "2026-03-12T10:00:00Z",
  deleted: false,
  client_id: "test",
  version: 2,
  model_type: "basic",
  reverse: false,
  source_ref_type: "manual",
  source_ref_id: null,
  conversation_id: null,
  message_id: null,
  next_intervals: {
    again: "1 min",
    hard: "6 min",
    good: "10 min",
    easy: "4 days"
  }
}

describe("useReviewQuery", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("uses the backend-selected next-card endpoint", async () => {
    vi.mocked(getNextReviewCard).mockResolvedValue({
      card: baseCard,
      selection_reason: "learning_due"
    })

    const { result } = renderHook(() => useReviewQuery(7), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.data?.uuid).toBe("card-1")
    })

    expect(getNextReviewCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        include_workspace_items: false
      })
    )
    expect(result.current.data?.next_intervals?.again).toBe("1 min")
  })

  it("returns null when the backend reports no reviewable card", async () => {
    vi.mocked(getNextReviewCard).mockResolvedValue({
      card: null,
      selection_reason: "none"
    })

    const { result } = renderHook(() => useReviewQuery(null), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(getNextReviewCard).toHaveBeenCalledWith(
      undefined,
      expect.objectContaining({
        include_workspace_items: false
      })
    )
    expect(result.current.data).toBeNull()
  })

  it("hides workspace-owned review cards by default", async () => {
    vi.mocked(getNextReviewCard).mockResolvedValue({
      card: null,
      selection_reason: "none"
    })

    renderHook(() => useReviewQuery(7), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(getNextReviewCard).toHaveBeenCalled()
    })

    expect(getNextReviewCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        include_workspace_items: false
      })
    )
  })

  it("can force-include workspace-owned review cards for direct deck navigation", async () => {
    vi.mocked(getNextReviewCard).mockResolvedValue({
      card: baseCard,
      selection_reason: "learning_due"
    })

    renderHook(() => useReviewQuery(7, { includeWorkspaceItems: true }), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(getNextReviewCard).toHaveBeenCalled()
    })

    expect(getNextReviewCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        include_workspace_items: true
      })
    )
  })
})
