import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args)
}))

import { deriveNoteStudio, getNoteStudioState } from "@/services/notes-studio"

describe("notes-studio service", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("posts derive requests to the notes studio endpoint", async () => {
    mocks.bgRequest.mockResolvedValue({ note: { id: "derived-1" } })

    await deriveNoteStudio({
      source_note_id: "source-1",
      excerpt_text: "Key excerpt",
      template_type: "cornell",
      handwriting_mode: "off"
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith({
      path: "/api/v1/notes/studio/derive",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        source_note_id: "source-1",
        excerpt_text: "Key excerpt",
        template_type: "cornell",
        handwriting_mode: "off"
      }
    })
  })

  it("fetches studio state for a selected note", async () => {
    mocks.bgRequest.mockResolvedValue({ studio_document: { note_id: "derived-1" } })

    await getNoteStudioState("derived-1")

    expect(mocks.bgRequest).toHaveBeenCalledWith({
      path: "/api/v1/notes/derived-1/studio",
      method: "GET"
    })
  })
})
