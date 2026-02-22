import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundMessage keyboard shortcut guard", () => {
  it("keeps message-level keyboard shortcuts for variants, branch, and regenerate", () => {
    const sourcePath = path.resolve(__dirname, "../Message.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("resolvePlaygroundMessageShortcutAction")
    expect(source).toContain("hasMessageKeyboardShortcuts")
    expect(source).toContain("tabIndex={hasMessageKeyboardShortcuts ? 0 : undefined}")
    expect(source).toContain("onKeyDown={hasMessageKeyboardShortcuts ? handleMessageShortcut : undefined}")
    expect(source).toContain("variant_prev")
    expect(source).toContain("variant_next")
    expect(source).toContain("new_branch")
    expect(source).toContain("regenerate")
    expect(source).toContain("articleRef.current?.focus()")
    expect(source).toContain("event.preventDefault()")
  })
})
