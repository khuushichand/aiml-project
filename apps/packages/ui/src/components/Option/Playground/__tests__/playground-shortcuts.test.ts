// @vitest-environment jsdom
import { describe, expect, it } from "vitest"
import { resolvePlaygroundShortcutAction } from "../playground-shortcuts"

describe("playground-shortcuts", () => {
  it("maps Alt+Shift shortcuts to actions", () => {
    expect(
      resolvePlaygroundShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "a"
      })
    ).toBe("toggle_artifacts")
    expect(
      resolvePlaygroundShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "c"
      })
    ).toBe("toggle_compare")
    expect(
      resolvePlaygroundShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "m"
      })
    ).toBe("toggle_modes")
  })

  it("ignores shortcuts while typing in editable controls", () => {
    const input = document.createElement("input")
    expect(
      resolvePlaygroundShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "a",
        target: input
      })
    ).toBeNull()
  })

  it("rejects conflicting modifier combinations and repeats", () => {
    expect(
      resolvePlaygroundShortcutAction({
        altKey: true,
        shiftKey: true,
        ctrlKey: true,
        key: "a"
      })
    ).toBeNull()
    expect(
      resolvePlaygroundShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "a",
        repeat: true
      })
    ).toBeNull()
  })
})
