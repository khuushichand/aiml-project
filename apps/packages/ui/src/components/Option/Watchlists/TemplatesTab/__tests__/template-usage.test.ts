import { describe, expect, it } from "vitest"
import { findActiveTemplateUsage } from "../template-usage"

describe("template usage detector", () => {
  it("finds active monitor usage across nested and legacy output_prefs fields", () => {
    const usage = findActiveTemplateUsage(
      [
        {
          id: 1,
          name: "Daily Brief",
          active: true,
          output_prefs: {
            template: { default_name: "brief-template" }
          }
        },
        {
          id: 2,
          name: "Weekly Digest",
          active: true,
          output_prefs: {
            template_name: "BRIEF-template"
          }
        },
        {
          id: 3,
          name: "Inactive Monitor",
          active: false,
          output_prefs: {
            template_name: "brief-template"
          }
        }
      ] as any,
      "brief-template"
    )

    expect(usage).toEqual([
      { id: 1, name: "Daily Brief" },
      { id: 2, name: "Weekly Digest" }
    ])
  })

  it("returns empty when no active monitor references the template", () => {
    const usage = findActiveTemplateUsage(
      [
        {
          id: 10,
          name: "No Template",
          active: true,
          output_prefs: {}
        }
      ] as any,
      "missing-template"
    )
    expect(usage).toEqual([])
  })
})
