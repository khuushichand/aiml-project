import { describe, expect, it } from "vitest"
import {
  applyManageClientSort,
  cardHasAllTags,
  getManageServerOrderBy,
  normalizeManageTags
} from "../useFlashcardQueries"
import type { Flashcard } from "@/services/flashcards"

const baseCard: Flashcard = {
  uuid: "card",
  deck_id: 1,
  front: "",
  back: "Back",
  notes: null,
  extra: null,
  is_cloze: false,
  tags: [],
  ef: 2.5,
  interval_days: 0,
  repetitions: 0,
  lapses: 0,
  due_at: null,
  created_at: null,
  last_reviewed_at: null,
  last_modified: null,
  deleted: false,
  client_id: "test",
  version: 1,
  model_type: "basic",
  reverse: false
}

const cards: Flashcard[] = [
  {
    ...baseCard,
    uuid: "c-1",
    front: "banana",
    ef: 2.9,
    due_at: "2026-02-22T00:00:00Z",
    created_at: "2026-02-03T00:00:00Z",
    last_reviewed_at: "2026-02-15T00:00:00Z"
  },
  {
    ...baseCard,
    uuid: "c-2",
    front: "Apple",
    ef: 1.7,
    due_at: "2026-02-20T00:00:00Z",
    created_at: "2026-02-01T00:00:00Z",
    last_reviewed_at: "2026-02-10T00:00:00Z"
  },
  {
    ...baseCard,
    uuid: "c-3",
    front: "carrot",
    ef: 2.2,
    due_at: null,
    created_at: "2026-02-02T00:00:00Z",
    last_reviewed_at: null
  }
]

describe("flashcard manage sorting helpers", () => {
  it("maps sort choices to supported backend order_by values", () => {
    expect(getManageServerOrderBy("due")).toBe("due_at")
    expect(getManageServerOrderBy("created")).toBe("created_at")
    expect(getManageServerOrderBy("ease")).toBe("due_at")
    expect(getManageServerOrderBy("last_reviewed")).toBe("due_at")
    expect(getManageServerOrderBy("front_alpha")).toBe("due_at")
  })

  it("applies client-side sort for due date and puts unscheduled cards last", () => {
    const sorted = applyManageClientSort(cards, "due")
    expect(sorted.map((card) => card.uuid)).toEqual(["c-2", "c-1", "c-3"])
  })

  it("applies client-side sort for created date", () => {
    const sorted = applyManageClientSort(cards, "created")
    expect(sorted.map((card) => card.uuid)).toEqual(["c-2", "c-3", "c-1"])
  })

  it("applies client-side sort for ease factor", () => {
    const sorted = applyManageClientSort(cards, "ease")
    expect(sorted.map((card) => card.uuid)).toEqual(["c-2", "c-3", "c-1"])
  })

  it("applies client-side sort for last reviewed with never-reviewed cards last", () => {
    const sorted = applyManageClientSort(cards, "last_reviewed")
    expect(sorted.map((card) => card.uuid)).toEqual(["c-1", "c-2", "c-3"])
  })

  it("applies client-side sort for front text alphabetically", () => {
    const sorted = applyManageClientSort(cards, "front_alpha")
    expect(sorted.map((card) => card.uuid)).toEqual(["c-2", "c-1", "c-3"])
  })

  it("normalizes and deduplicates multi-tag filters", () => {
    expect(normalizeManageTags(["Biology", "  chemistry "], "BIOLOGY")).toEqual([
      "biology",
      "chemistry"
    ])
  })

  it("checks whether a card contains all selected tags", () => {
    const candidate = { ...cards[0], tags: ["biology", "chapter-1", "review"] }
    expect(cardHasAllTags(candidate, ["biology", "review"])).toBe(true)
    expect(cardHasAllTags(candidate, ["biology", "physics"])).toBe(false)
  })
})
