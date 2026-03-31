import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args)
}))

import {
  deriveNoteStudio,
  getNoteStudioState,
  regenerateNoteStudio,
  updateNoteStudioDiagrams
} from "@/services/notes-studio"

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

  it("posts regenerate requests for a selected studio note", async () => {
    mocks.bgRequest.mockResolvedValue({ note: { id: "derived-1" } })

    await regenerateNoteStudio("derived-1")

    expect(mocks.bgRequest).toHaveBeenCalledWith({
      path: "/api/v1/notes/derived-1/studio/regenerate",
      method: "POST",
      headers: { "Content-Type": "application/json" }
    })
  })

  it("includes the current markdown companion when regenerating from unsaved edits", async () => {
    mocks.bgRequest.mockResolvedValue({ note: { id: "derived-1" } })

    await regenerateNoteStudio("derived-1", {
      current_markdown: "# Studio note\n\nUpdated local markdown"
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith({
      path: "/api/v1/notes/derived-1/studio/regenerate",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        current_markdown: "# Studio note\n\nUpdated local markdown"
      }
    })
  })

  it("sends an explicit empty markdown override when the draft has been cleared", async () => {
    mocks.bgRequest.mockResolvedValue({ note: { id: "derived-1" } })

    await regenerateNoteStudio("derived-1", {
      current_markdown: ""
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith({
      path: "/api/v1/notes/derived-1/studio/regenerate",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        current_markdown: ""
      }
    })
  })

  it("posts diagram manifest updates for a selected studio note", async () => {
    mocks.bgRequest.mockResolvedValue({ note: { id: "derived-1" } })

    await updateNoteStudioDiagrams("derived-1", {
      diagram_type: "flowchart",
      source_section_ids: ["notes-1"]
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith({
      path: "/api/v1/notes/derived-1/studio/diagrams",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        diagram_type: "flowchart",
        source_section_ids: ["notes-1"]
      }
    })
  })
})
