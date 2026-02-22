import { describe, expect, it } from "vitest"
import {
  buildTemplateSavePayload,
  hasTemplateAdvancedContext,
  shouldWarnOnTemplateModeChange
} from "../template-mode"

describe("template mode helpers", () => {
  it("detects advanced context only for editing sessions", () => {
    expect(
      hasTemplateAdvancedContext({
        isEditing: false,
        selectedVersion: 2,
        activeTab: "docs",
        hasVersionDrift: true,
        validationErrorCount: 1
      })
    ).toBe(false)

    expect(
      hasTemplateAdvancedContext({
        isEditing: true,
        selectedVersion: 2,
        activeTab: "editor",
        hasVersionDrift: false,
        validationErrorCount: 0
      })
    ).toBe(true)

    expect(
      hasTemplateAdvancedContext({
        isEditing: true,
        activeTab: "docs",
        hasVersionDrift: false,
        validationErrorCount: 0
      })
    ).toBe(true)
  })

  it("warns only when switching from advanced to basic with advanced context", () => {
    expect(
      shouldWarnOnTemplateModeChange({
        currentMode: "advanced",
        nextMode: "basic",
        hasAdvancedContext: true
      })
    ).toBe(true)

    expect(
      shouldWarnOnTemplateModeChange({
        currentMode: "advanced",
        nextMode: "basic",
        hasAdvancedContext: false
      })
    ).toBe(false)

    expect(
      shouldWarnOnTemplateModeChange({
        currentMode: "basic",
        nextMode: "advanced",
        hasAdvancedContext: true
      })
    ).toBe(false)
  })

  it("builds identical content payload regardless mode while toggling overwrite by edit state", () => {
    const baseValues = {
      name: "daily-template",
      description: "Daily digest",
      content: "# {{ title }}",
      format: "md" as const
    }

    expect(buildTemplateSavePayload(baseValues, false)).toEqual({
      ...baseValues,
      overwrite: false
    })

    expect(buildTemplateSavePayload(baseValues, true)).toEqual({
      ...baseValues,
      overwrite: true
    })
  })
})
