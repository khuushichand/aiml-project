// @vitest-environment jsdom
import { describe, expect, it } from "vitest"
import { resolvePlaygroundMessageShortcutAction } from "../playground-message-shortcuts"

describe("playground-message-shortcuts", () => {
  it("maps Alt+Shift keys to message actions", () => {
    expect(
      resolvePlaygroundMessageShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "ArrowLeft"
      })
    ).toBe("variant_prev")
    expect(
      resolvePlaygroundMessageShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "ArrowRight"
      })
    ).toBe("variant_next")
    expect(
      resolvePlaygroundMessageShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "b"
      })
    ).toBe("new_branch")
    expect(
      resolvePlaygroundMessageShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "r"
      })
    ).toBe("regenerate")
  })

  it("ignores editable targets and conflicting modifiers", () => {
    const textarea = document.createElement("textarea")
    expect(
      resolvePlaygroundMessageShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "b",
        target: textarea
      })
    ).toBeNull()
    expect(
      resolvePlaygroundMessageShortcutAction({
        altKey: true,
        shiftKey: true,
        ctrlKey: true,
        key: "r"
      })
    ).toBeNull()
  })

  it("ignores repeat key events", () => {
    expect(
      resolvePlaygroundMessageShortcutAction({
        altKey: true,
        shiftKey: true,
        key: "ArrowLeft",
        repeat: true
      })
    ).toBeNull()
  })
})
