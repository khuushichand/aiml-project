import { describe, expect, it } from "vitest"
import { HEADER_SHORTCUT_IDS } from "@/services/settings/ui-settings"
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
    expect(shortcuts).toEqual(HEADER_SHORTCUT_IDS)
  })

  it("null persona returns all shortcuts", () => {
    const shortcuts = getDefaultShortcutsForPersona(null)
    expect(shortcuts).toEqual(HEADER_SHORTCUT_IDS)
  })

  it("returns a cloned array for persona defaults", () => {
    const expected = [...PERSONA_SHORTCUT_DEFAULTS.family]
    const shortcuts = getDefaultShortcutsForPersona("family")
    shortcuts.pop()

    expect(getDefaultShortcutsForPersona("family")).toEqual(
      expected
    )
  })

  it("family persona has fewer items than researcher", () => {
    const family = getDefaultShortcutsForPersona("family")
    const researcher = getDefaultShortcutsForPersona("researcher")
    expect(family.length).toBeLessThan(researcher.length)
  })

  it("all persona defaults include required shortcut IDs", () => {
    const required = [
      "workflows",
      "acp-playground",
      "integrations",
      "scheduled-tasks",
      "admin-integrations"
    ]
    for (const persona of ["family", "researcher", "explorer", "default"] as const) {
      const shortcuts = PERSONA_SHORTCUT_DEFAULTS[persona]
      for (const id of required) {
        expect(shortcuts).toContain(id)
      }
    }
  })
})
