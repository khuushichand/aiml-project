import { describe, expect, it } from "vitest"
import {
  getDefaultShortcutsForPersona,
  PERSONA_SHORTCUT_DEFAULTS
} from "../header-shortcut-items"

describe("persona shortcut defaults", () => {
  it("family persona includes safety tools", () => {
    const shortcuts = getDefaultShortcutsForPersona("family")
    expect(shortcuts).toContain("family-guardrails")
    expect(shortcuts).toContain("moderation-playground")
    expect(shortcuts).toContain("chat")
    expect(shortcuts).toContain("settings")
  })

  it("researcher persona includes research tools", () => {
    const shortcuts = getDefaultShortcutsForPersona("researcher")
    expect(shortcuts).toContain("deep-research")
    expect(shortcuts).toContain("knowledge-qa")
    expect(shortcuts).toContain("media")
    expect(shortcuts).toContain("workspace-playground")
    expect(shortcuts).toContain("chat")
  })

  it("explorer persona returns all shortcuts", () => {
    const shortcuts = getDefaultShortcutsForPersona("explorer")
    expect(shortcuts.length).toBeGreaterThan(30) // all items
  })

  it("null persona returns all shortcuts", () => {
    const shortcuts = getDefaultShortcutsForPersona(null)
    expect(shortcuts.length).toBeGreaterThan(30)
  })

  it("family persona has fewer items than researcher", () => {
    const family = getDefaultShortcutsForPersona("family")
    const researcher = getDefaultShortcutsForPersona("researcher")
    expect(family.length).toBeLessThan(researcher.length)
  })

  it("family persona does not include admin/automation items (coercion handles them)", () => {
    const adminItems = [
      "workflows",
      "acp-playground",
      "integrations",
      "scheduled-tasks",
      "admin-integrations"
    ]
    const family = PERSONA_SHORTCUT_DEFAULTS.family
    for (const id of adminItems) {
      expect(family).not.toContain(id)
    }
  })

  it("explorer and default personas include all shortcut IDs", () => {
    for (const persona of ["explorer", "default"] as const) {
      const shortcuts = PERSONA_SHORTCUT_DEFAULTS[persona]
      expect(shortcuts.length).toBeGreaterThan(30)
    }
  })
})
