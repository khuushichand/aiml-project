import { describe, expect, it } from "vitest"
import { getHeaderShortcutGroups } from "../header-shortcut-items"

describe("header shortcut safety group", () => {
  const groups = getHeaderShortcutGroups()

  it("has a 'safety' group", () => {
    const safety = groups.find((g) => g.id === "safety")
    expect(safety).toBeDefined()
    expect(safety!.titleDefault).toBe("Safety")
  })

  it("safety group contains family-guardrails, moderation-playground, and guardian", () => {
    const safety = groups.find((g) => g.id === "safety")!
    const ids = safety.items.map((i) => i.id)
    expect(ids).toContain("family-guardrails")
    expect(ids).toContain("moderation-playground")
    expect(ids).toContain("guardian")
  })

  it("moderation-playground is no longer in the tools group", () => {
    const tools = groups.find((g) => g.id === "tools")
    if (tools) {
      const ids = tools.items.map((i) => i.id)
      expect(ids).not.toContain("moderation-playground")
    }
  })

  it("each safety item has a distinct icon", () => {
    const safety = groups.find((g) => g.id === "safety")!
    const iconNames = safety.items.map(
      (i) => i.icon.displayName || i.icon.name || String(i.icon)
    )
    const uniqueIcons = new Set(iconNames)
    expect(uniqueIcons.size).toBe(safety.items.length)
  })
})
