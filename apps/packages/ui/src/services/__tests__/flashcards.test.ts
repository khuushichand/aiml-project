import { beforeEach, describe, expect, it, vi } from "vitest"

const mockBgRequest = vi.hoisted(() => vi.fn())

vi.mock("@/services/background-proxy", () => ({
  bgRequest: mockBgRequest
}))

vi.mock("@/services/resource-client", () => ({
  buildQuery: vi.fn(() => ""),
  createResourceClient: vi.fn(() => ({
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn()
  }))
}))

import {
  FLASHCARD_GENERATION_TIMEOUT_MS,
  generateFlashcards
} from "@/services/flashcards"

describe("flashcards service", () => {
  beforeEach(() => {
    mockBgRequest.mockReset()
    mockBgRequest.mockResolvedValue({ flashcards: [] })
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
})
