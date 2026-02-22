import { describe, expect, it } from "vitest"
import {
  getPromptImportNotificationCopy,
  normalizePromptImportCounts
} from "../prompt-import-utils"

describe("prompt-import-utils", () => {
  it("normalizes import counts with safe defaults", () => {
    expect(
      normalizePromptImportCounts(
        {
          imported: 3,
          skipped: 1,
          failed: 2
        },
        10
      )
    ).toEqual({
      imported: 3,
      skipped: 1,
      failed: 2
    })

    expect(normalizePromptImportCounts(undefined, 7)).toEqual({
      imported: 7,
      skipped: 0,
      failed: 0
    })

    expect(
      normalizePromptImportCounts(
        {
          imported: -5,
          skipped: -2,
          failed: -3
        },
        4
      )
    ).toEqual({
      imported: 0,
      skipped: 0,
      failed: 0
    })
  })

  it("builds replace-mode notification copy", () => {
    const copy = getPromptImportNotificationCopy("replace", {
      imported: 9,
      skipped: 2,
      failed: 1
    })

    expect(copy.key).toBe(
      "managePrompts.notification.replaceSuccessDetailedDesc"
    )
    expect(copy.defaultValue).toContain("backup file")
    expect(copy.values).toEqual({
      imported: 9,
      skipped: 2,
      failed: 1
    })
  })

  it("builds merge-mode notification copy", () => {
    const copy = getPromptImportNotificationCopy("merge", {
      imported: 5,
      skipped: 0,
      failed: 0
    })

    expect(copy.key).toBe("managePrompts.notification.addSuccessDetailedDesc")
    expect(copy.defaultValue).toContain("Imported")
    expect(copy.values).toEqual({
      imported: 5,
      skipped: 0,
      failed: 0
    })
  })
})
