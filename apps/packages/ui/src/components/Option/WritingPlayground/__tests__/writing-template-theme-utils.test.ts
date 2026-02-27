import { describe, expect, it } from "vitest"
import {
  DEFAULT_THEME_CATALOG,
  DEFAULT_TEMPLATE_CATALOG,
  buildDuplicateName
} from "../writing-template-theme-utils"

describe("writing template/theme utils", () => {
  it("builds unique duplicate names", () => {
    expect(
      buildDuplicateName("Story", ["Story", "Story (Copy)", "Story (Copy 2)"])
    ).toBe("Story (Copy 3)")
  })

  it("handles case-insensitive name collisions", () => {
    expect(
      buildDuplicateName("theme", ["Theme (Copy)", "theme (copy 2)"])
    ).toBe("theme (Copy 3)")
  })

  it("exposes default template/theme catalogs for restore actions", () => {
    expect(DEFAULT_TEMPLATE_CATALOG.length).toBeGreaterThan(0)
    expect(DEFAULT_TEMPLATE_CATALOG[0].is_default).toBe(true)
    expect(DEFAULT_THEME_CATALOG.length).toBeGreaterThan(0)
    expect(DEFAULT_THEME_CATALOG[0].is_default).toBe(true)
  })
})
