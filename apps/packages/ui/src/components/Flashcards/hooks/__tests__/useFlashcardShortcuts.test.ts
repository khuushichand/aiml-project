import { describe, expect, it } from "vitest"
import { getFlashcardShortcutResult } from "../useFlashcardShortcuts"

describe("getFlashcardShortcutResult", () => {
  it("maps E to edit action", () => {
    const result = getFlashcardShortcutResult("e", false, false)
    expect(result?.preventDefault).toBe(true)
    expect(result?.action).toEqual({ type: "edit" })
  })

  it("maps Ctrl/Cmd+Z to undo action", () => {
    const result = getFlashcardShortcutResult("z", true, true)
    expect(result?.preventDefault).toBe(true)
    expect(result?.action).toEqual({ type: "undo" })
  })
})
