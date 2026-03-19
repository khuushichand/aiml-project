import { describe, expect, it } from "vitest"

import { shouldRefetchDocumentQueryAfterRowSave } from "../document-cache-policy"

function makeFlashcard(overrides: Partial<import("@/services/flashcards").Flashcard> = {}) {
  return {
    uuid: "card-1",
    deck_id: 5,
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
    queue_state: "new" as const,
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

describe("shouldRefetchDocumentQueryAfterRowSave", () => {
  it("forces document query refresh when a row edit changes filter membership", () => {
    const previous = makeFlashcard({ uuid: "row-1", deck_id: 5, tags: ["bio"] })
    const next = makeFlashcard({ uuid: "row-1", deck_id: 7, tags: ["chem"] })

    expect(
      shouldRefetchDocumentQueryAfterRowSave(previous, next, {
        deckId: 5,
        tags: ["bio"],
        sortBy: "due",
        dueStatus: "all"
      })
    ).toBe(true)
  })

  it("allows in-place patching when row membership and sort position remain stable", () => {
    const previous = makeFlashcard({ uuid: "row-1", notes: "old" })
    const next = makeFlashcard({ uuid: "row-1", notes: "new" })

    expect(
      shouldRefetchDocumentQueryAfterRowSave(previous, next, {
        deckId: null,
        tags: [],
        sortBy: "due",
        dueStatus: "all"
      })
    ).toBe(false)
  })
})
