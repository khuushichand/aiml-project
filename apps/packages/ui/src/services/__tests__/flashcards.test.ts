import { beforeEach, describe, expect, it, vi } from "vitest"

const mockBgRequest = vi.hoisted(() => vi.fn())
const listSpy = vi.hoisted(() => vi.fn())

vi.mock("@/services/background-proxy", () => ({
  bgRequest: mockBgRequest
}))

vi.mock("@/services/resource-client", () => ({
  buildQuery: vi.fn(() => ""),
  createResourceClient: vi.fn(() => ({
    list: listSpy,
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn()
  }))
}))

import {
  FLASHCARD_GENERATION_TIMEOUT_MS,
  generateFlashcards,
  listFlashcardTagSuggestions
} from "@/services/flashcards"

describe("flashcards service", () => {
  beforeEach(() => {
    mockBgRequest.mockReset()
    listSpy.mockReset()
    mockBgRequest.mockResolvedValue({ flashcards: [] })
    listSpy.mockResolvedValue({ items: [], count: 0 })
  })

  it("uses extended timeout by default for flashcard generation", async () => {
    await generateFlashcards({ text: "ATP powers the cell." })

    expect(mockBgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/flashcards/generate",
        method: "POST",
        timeoutMs: FLASHCARD_GENERATION_TIMEOUT_MS
      })
    )
  })

  it("calls the global tag suggestions endpoint with q and limit", async () => {
    const signal = new AbortController().signal

    await listFlashcardTagSuggestions({
      q: "bio",
      limit: 25,
      signal
    })

    expect(listSpy).toHaveBeenCalledWith(
      {
        q: "bio",
        limit: 25
      },
      {
        abortSignal: signal
      }
    )
  })

  it("omits blank q values when requesting global tag suggestions", async () => {
    await listFlashcardTagSuggestions({
      q: "   ",
      limit: 10
    })

    expect(listSpy).toHaveBeenCalledWith(
      {
        limit: 10
      },
      {
        abortSignal: undefined
      }
    )
  })
})
