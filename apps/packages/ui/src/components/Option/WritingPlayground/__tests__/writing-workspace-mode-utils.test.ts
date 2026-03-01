import { describe, expect, it } from "vitest"
import {
  DEFAULT_WRITING_WORKSPACE_MODE,
  WRITING_WORKSPACE_SECTIONS,
  getVisibleWritingWorkspaceSections
} from "../writing-workspace-mode-utils"

describe("writing workspace mode utils", () => {
  it("defaults to draft mode", () => {
    expect(DEFAULT_WRITING_WORKSPACE_MODE).toBe("draft")
  })

  it("keeps drafting sections hidden from manage-only set", () => {
    const draftIds = getVisibleWritingWorkspaceSections("draft").map((s) => s.id)
    expect(draftIds).toContain("draft-editor")
    expect(draftIds).not.toContain("manage-analysis")
  })

  it("declares stable section ids", () => {
    expect(WRITING_WORKSPACE_SECTIONS.map((s) => s.id)).toEqual([
      "sessions",
      "draft-editor",
      "draft-inspector",
      "manage-styling",
      "manage-generation",
      "manage-context",
      "manage-analysis"
    ])
  })
})
