import { beforeEach, describe, expect, it, vi } from "vitest"

const mockBgRequest = vi.hoisted(() => vi.fn())

vi.mock("@/services/background-proxy", () => ({
  bgRequest: mockBgRequest
}))

vi.mock("@/services/resource-client", () => ({
  createResourceClient: vi.fn(() => ({
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn()
  }))
}))

import {
  generateQuiz,
  QUIZ_GENERATION_TIMEOUT_MS
} from "@/services/quizzes"

describe("quizzes service", () => {
  beforeEach(() => {
    mockBgRequest.mockReset()
    mockBgRequest.mockResolvedValue({ quiz: { id: 1 }, questions: [] })
  })

  it("uses extended timeout by default for quiz generation", async () => {
    await generateQuiz({ media_id: 42 })

    expect(mockBgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/quizzes/generate",
        method: "POST",
        timeoutMs: QUIZ_GENERATION_TIMEOUT_MS
      })
    )
  })

  it("respects explicit timeout override for quiz generation", async () => {
    const controller = new AbortController()

    await generateQuiz(
      { media_id: 42 },
      { signal: controller.signal, timeoutMs: 180000 }
    )

    expect(mockBgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/quizzes/generate",
        method: "POST",
        abortSignal: controller.signal,
        timeoutMs: 180000
      })
    )
  })
})
