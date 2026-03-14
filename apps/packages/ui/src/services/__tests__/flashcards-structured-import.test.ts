import { beforeEach, describe, expect, it, vi } from "vitest"

const mockBgRequest = vi.hoisted(() => vi.fn())
const mockBgUpload = vi.hoisted(() => vi.fn())

vi.mock("@/services/background-proxy", () => ({
  bgRequest: mockBgRequest,
  bgUpload: mockBgUpload
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
  createFlashcardsBulk,
  previewStructuredQaImport
} from "@/services/flashcards"

describe("flashcards structured import service", () => {
  beforeEach(() => {
    mockBgRequest.mockReset()
    mockBgUpload.mockReset()
    mockBgRequest.mockResolvedValue({
      drafts: [],
      errors: [],
      detected_format: "qa_labels",
      skipped_blocks: 0
    })
  })

  it("calls the structured preview endpoint", async () => {
    await previewStructuredQaImport({ content: "Q: ATP\nA: Energy" })

    expect(mockBgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/flashcards/import/structured/preview",
        method: "POST",
        body: { content: "Q: ATP\nA: Energy" }
      })
    )
  })

  it("calls the bulk create endpoint for approved structured drafts", async () => {
    await createFlashcardsBulk([
      {
        front: "What is ATP?",
        back: "Primary energy currency.",
        model_type: "basic",
        is_cloze: false,
        reverse: false
      }
    ])

    expect(mockBgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/flashcards/bulk",
        method: "POST",
      })
    )
  })
})
