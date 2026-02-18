import { describe, expect, it } from "vitest"
import {
  WORLD_BOOK_FORM_DEFAULTS,
  buildWorldBookFormPayload,
  buildWorldBookMutationErrorMessage,
  hasDuplicateWorldBookName,
  toWorldBookFormValues
} from "../worldBookFormUtils"

describe("worldBookFormUtils", () => {
  it("keeps frontend defaults aligned with backend schema defaults", () => {
    expect(WORLD_BOOK_FORM_DEFAULTS.scan_depth).toBe(3)
    expect(WORLD_BOOK_FORM_DEFAULTS.token_budget).toBe(500)
    expect(WORLD_BOOK_FORM_DEFAULTS.enabled).toBe(true)
  })

  it("detects duplicate world-book names case-insensitively", () => {
    const worldBooks = [
      { id: 1, name: "Lore Core" },
      { id: 2, name: "Side Notes" }
    ]
    expect(hasDuplicateWorldBookName("lore core", worldBooks)).toBe(true)
    expect(hasDuplicateWorldBookName("Lore Core", worldBooks, { excludeId: 1 })).toBe(false)
    expect(hasDuplicateWorldBookName("New Book", worldBooks)).toBe(false)
  })

  it("normalizes create payload with defaults and trimmed values", () => {
    const payload = buildWorldBookFormPayload({ name: "  Arcana  " }, "create")
    expect(payload.name).toBe("Arcana")
    expect(payload.scan_depth).toBe(3)
    expect(payload.token_budget).toBe(500)
    expect(payload.recursive_scanning).toBe(false)
  })

  it("strips transport suffix and preserves conflict message details", () => {
    const error = {
      status: 409,
      message: "World book with name 'Arcana' already exists (POST /api/v1/characters/world-books)"
    }
    expect(buildWorldBookMutationErrorMessage(error)).toBe(
      "World book with name 'Arcana' already exists"
    )
  })

  it("falls back to attempted name for conflict errors without detail", () => {
    expect(
      buildWorldBookMutationErrorMessage({ status: 409 }, { attemptedName: "Arcana" })
    ).toBe('A world book named "Arcana" already exists.')
  })

  it("hydrates edit form values with safe defaults", () => {
    const values = toWorldBookFormValues({ id: 10, name: "Arcana", token_budget: 900 })
    expect(values.name).toBe("Arcana")
    expect(values.scan_depth).toBe(3)
    expect(values.token_budget).toBe(900)
    expect(values.enabled).toBe(true)
  })
})
